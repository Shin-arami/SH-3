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
        now=instant + timedelta(seconds=7),
    )
    reopened = SQLiteReplayClaimStore(database).claim(
        "learning-cycle:recover",
        "sha256:input",
        now=instant + timedelta(seconds=7),
    )

    assert reopened.status is ReplayClaimStatus.COMPLETED
    assert reopened.evidence_id == "learning-closed-loop:terminal"



def test_replay_claim_lease_renewal_extends_deadline_without_changing_generation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "evidence.sqlite3"
    instant = datetime(2026, 10, 14, tzinfo=UTC)
    owner_store = SQLiteReplayClaimStore(database)
    owner = owner_store.claim(
        "learning-cycle:renew",
        "sha256:renew-input",
        lease_seconds=5.0,
        now=instant,
    )
    assert owner.owner_token is not None

    renewed = owner_store.renew(
        owner.cycle_id,
        owner.fingerprint,
        owner.owner_token,
        owner.generation,
        lease_seconds=10.0,
        now=instant + timedelta(seconds=4),
    )
    assert renewed.generation == owner.generation
    assert renewed.attempts == owner.attempts
    assert renewed.lease_expires_at == instant.timestamp() + 14.0
    unchanged_deadline = owner_store.renew(
        owner.cycle_id,
        owner.fingerprint,
        owner.owner_token,
        owner.generation,
        lease_seconds=2.0,
        now=instant + timedelta(seconds=5),
    )
    assert unchanged_deadline.lease_expires_at == renewed.lease_expires_at

    contender_store = SQLiteReplayClaimStore(database)
    contender = contender_store.claim(
        owner.cycle_id,
        owner.fingerprint,
        now=instant + timedelta(seconds=6),
    )
    assert contender.status is ReplayClaimStatus.BUSY

    recovered = contender_store.claim(
        owner.cycle_id,
        owner.fingerprint,
        now=instant + timedelta(seconds=15),
    )
    assert recovered.status is ReplayClaimStatus.CLAIMED
    assert recovered.generation == owner.generation + 1
    with pytest.raises(ReplayClaimOwnershipError):
        owner_store.complete(
            owner.cycle_id,
            owner.fingerprint,
            owner.owner_token,
            owner.generation,
            "learning-closed-loop:stale-owner",
            now=instant + timedelta(seconds=15),
        )


def test_expired_lease_cannot_be_renewed_completed_or_released(
    tmp_path: Path,
) -> None:
    store = SQLiteReplayClaimStore(tmp_path / "evidence.sqlite3")
    instant = datetime(2026, 10, 14, tzinfo=UTC)
    claim = store.claim(
        "learning-cycle:expired",
        "sha256:expired-input",
        lease_seconds=2.0,
        now=instant,
    )
    assert claim.owner_token is not None
    expired_at = instant + timedelta(seconds=3)

    with pytest.raises(ReplayClaimOwnershipError, match="lease expired"):
        store.renew(
            claim.cycle_id,
            claim.fingerprint,
            claim.owner_token,
            claim.generation,
            lease_seconds=5.0,
            now=expired_at,
        )
    with pytest.raises(ReplayClaimOwnershipError, match="lease expired"):
        store.complete(
            claim.cycle_id,
            claim.fingerprint,
            claim.owner_token,
            claim.generation,
            "learning-closed-loop:expired-owner",
            now=expired_at,
        )
    assert not store.release(
        claim.cycle_id,
        claim.owner_token,
        claim.generation,
        now=expired_at,
    )

    takeover = store.claim(
        claim.cycle_id,
        claim.fingerprint,
        lease_seconds=5.0,
        now=expired_at,
    )
    assert takeover.status is ReplayClaimStatus.CLAIMED
    assert takeover.generation == claim.generation + 1


def test_replay_claim_renewal_rejects_wrong_identity_and_owner(
    tmp_path: Path,
) -> None:
    store = SQLiteReplayClaimStore(tmp_path / "evidence.sqlite3")
    instant = datetime(2026, 10, 14, tzinfo=UTC)
    claim = store.claim(
        "learning-cycle:renew-owner",
        "sha256:renew-owner-input",
        lease_seconds=30.0,
        now=instant,
    )
    assert claim.owner_token is not None

    with pytest.raises(ReplayClaimConflictError, match="fingerprint conflicts"):
        store.renew(
            claim.cycle_id,
            "sha256:different-input",
            claim.owner_token,
            claim.generation,
            now=instant + timedelta(seconds=1),
        )
    with pytest.raises(ReplayClaimOwnershipError, match="ownership was lost"):
        store.renew(
            claim.cycle_id,
            claim.fingerprint,
            "not-the-owner",
            claim.generation,
            now=instant + timedelta(seconds=1),
        )
    with pytest.raises(ReplayClaimOwnershipError, match="ownership was lost"):
        store.renew(
            claim.cycle_id,
            claim.fingerprint,
            claim.owner_token,
            claim.generation + 1,
            now=instant + timedelta(seconds=1),
        )


def test_replay_claim_rejects_changed_fingerprint(tmp_path: Path) -> None:
    store = SQLiteReplayClaimStore(tmp_path / "evidence.sqlite3")
    store.claim("learning-cycle:identity", "sha256:original")

    with pytest.raises(ReplayClaimConflictError, match="fingerprint conflicts"):
        store.claim("learning-cycle:identity", "sha256:different")
