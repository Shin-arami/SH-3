from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from infrastructure.security import EvidenceRecord, EvidenceStore
from infrastructure.security.persistent_store import (
    PersistentEvidenceIntegrityError,
    ReplayClaim,
    ReplayClaimConflictError,
    ReplayClaimOwnershipError,
    ReplayClaimStatus,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _evidence(
    evidence_id: str = "learning-closed-loop:test-persistent",
    *,
    payload: dict[str, object] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord.create(
        evidence_id=evidence_id,
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id="result:persistent",
        version="1.1.0",
        trace_id="trace:persistent",
        collected_at="2026-10-14T00:00:00+00:00",
        payload=payload or {"cycle_id": "learning-cycle:result:persistent", "status": "completed"},
    )


def test_sqlite_evidence_store_is_a_compatible_store_and_survives_reopen(
    tmp_path: Path,
) -> None:
    database = tmp_path / "evidence.sqlite3"
    evidence = _evidence()

    first = SQLiteEvidenceStore(database)
    assert isinstance(first, EvidenceStore)
    assert first.register(evidence).integrity == evidence.integrity

    second = SQLiteEvidenceStore(database)
    restored = second.get(evidence.evidence_id)

    assert restored is not None
    assert restored.to_dict() == evidence.to_dict()
    assert restored.verify()
    assert second.records() == (restored,)
    assert second.contains(evidence.evidence_id)
    assert second.count() == 1


def test_sqlite_evidence_store_is_idempotent_and_rejects_identity_conflicts(
    tmp_path: Path,
) -> None:
    store = SQLiteEvidenceStore(tmp_path / "evidence.sqlite3")
    evidence = _evidence()

    first = store.register(evidence)
    duplicate = store.register(evidence)

    assert duplicate.to_dict() == first.to_dict()
    with pytest.raises(ValueError, match="identifier conflicts"):
        store.register(_evidence(payload={"cycle_id": "different", "status": "failed"}))


def test_sqlite_evidence_store_fails_closed_on_tampered_payload(tmp_path: Path) -> None:
    database = tmp_path / "evidence.sqlite3"
    store = SQLiteEvidenceStore(database)
    evidence = _evidence()
    store.register(evidence)

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT record_json FROM sh3_evidence_records WHERE evidence_id = ?",
            (evidence.evidence_id,),
        ).fetchone()
        assert row is not None
        record = json.loads(row[0])
        record["payload"]["status"] = "tampered"
        connection.execute(
            "UPDATE sh3_evidence_records SET record_json = ? WHERE evidence_id = ?",
            (json.dumps(record, sort_keys=True, separators=(",", ":")), evidence.evidence_id),
        )

    with pytest.raises(PersistentEvidenceIntegrityError):
        store.get(evidence.evidence_id)


def test_replay_claim_is_atomic_across_threads(tmp_path: Path) -> None:
    database = tmp_path / "evidence.sqlite3"
    claim_stores = [SQLiteReplayClaimStore(database) for _ in range(12)]

    def attempt(index: int) -> ReplayClaim:
        return claim_stores[index].claim(
            "learning-cycle:parallel",
            "sha256:stable-inputs",
            lease_seconds=60.0,
        )

    with ThreadPoolExecutor(max_workers=len(claim_stores)) as executor:
        claims = tuple(executor.map(attempt, range(len(claim_stores))))

    assert sum(item.status is ReplayClaimStatus.CLAIMED for item in claims) == 1
    assert sum(item.status is ReplayClaimStatus.BUSY for item in claims) == 11


def test_expired_replay_claim_is_fenced_and_completed_claim_is_durable(
    tmp_path: Path,
) -> None:
    database = tmp_path / "evidence.sqlite3"
    instant = datetime(2026, 10, 14, tzinfo=UTC)
    first_store = SQLiteReplayClaimStore(database)
    first = first_store.claim(
        "learning-cycle:recover",
        "sha256:input",
        lease_seconds=5.0,
        now=instant,
    )
    assert first.status is ReplayClaimStatus.CLAIMED
    assert first.owner_token is not None

    second_store = SQLiteReplayClaimStore(database)
    second = second_store.claim(
        "learning-cycle:recover",
        "sha256:input",
        lease_seconds=5.0,
        now=instant + timedelta(seconds=6),
    )
    assert second.status is ReplayClaimStatus.CLAIMED
    assert second.owner_token is not None
    assert second.generation == first.generation + 1

    with pytest.raises(ReplayClaimOwnershipError):
        first_store.complete(
            first.cycle_id,
            first.fingerprint,
            first.owner_token,
            first.generation,
            "learning-closed-loop:stale",
        )

    second_store.complete(
        second.cycle_id,
        second.fingerprint,
        second.owner_token,
        second.generation,
        "learning-closed-loop:terminal",
    )
    reopened = SQLiteReplayClaimStore(database).claim(
        "learning-cycle:recover",
        "sha256:input",
        now=instant + timedelta(seconds=7),
    )

    assert reopened.status is ReplayClaimStatus.COMPLETED
    assert reopened.evidence_id == "learning-closed-loop:terminal"


def test_replay_claim_rejects_changed_fingerprint(tmp_path: Path) -> None:
    store = SQLiteReplayClaimStore(tmp_path / "evidence.sqlite3")
    store.claim("learning-cycle:identity", "sha256:original")

    with pytest.raises(ReplayClaimConflictError, match="fingerprint conflicts"):
        store.claim("learning-cycle:identity", "sha256:different")
