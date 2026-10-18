from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from foundation.utils.hash import short_id
from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import (
    PersistentReplayReadinessError,
    check_database,
)
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _terminal_evidence(
    cycle_id: str,
    *,
    evidence_id: str | None = None,
    kind: str = "learning.closed_loop",
    source: str = "kernel.learning_feedback_loop",
    subject_id: str = "result:link-check",
    result_id: str = "result:link-check",
) -> EvidenceRecord:
    return EvidenceRecord.create(
        evidence_id=evidence_id or short_id(cycle_id, prefix="learning-closed-loop:"),
        kind=kind,
        source=source,
        subject_id=subject_id,
        version="1.1.0",
        trace_id=f"trace:{cycle_id}",
        collected_at=datetime(2026, 10, 18, tzinfo=UTC).isoformat(),
        payload={"cycle_id": cycle_id, "result_id": result_id},
    )


def _complete_claim(
    store: SQLiteReplayClaimStore,
    cycle_id: str,
    evidence_id: str,
) -> None:
    fingerprint = f"sha256:{cycle_id}"
    claim = store.claim(cycle_id, fingerprint, lease_seconds=60.0)
    assert claim.owner_token is not None
    store.complete(
        cycle_id,
        fingerprint,
        claim.owner_token,
        claim.generation,
        evidence_id,
    )


def _stores(database: Path) -> tuple[SQLiteEvidenceStore, SQLiteReplayClaimStore]:
    return SQLiteEvidenceStore(database), SQLiteReplayClaimStore(database)


def test_check_accepts_completed_claim_with_matching_terminal_evidence(
    tmp_path: Path,
) -> None:
    database = tmp_path / "linked.sqlite3"
    evidence_store, claim_store = _stores(database)
    cycle_id = "learning-cycle:link-valid"
    evidence = _terminal_evidence(cycle_id)
    evidence_store.register(evidence)
    _complete_claim(claim_store, cycle_id, evidence.evidence_id)

    report = check_database(database)

    assert report.evidence_count == 1
    assert report.replay_claim_count == 1
    assert report.expired_claim_count == 0


def test_check_rejects_completed_claim_with_missing_evidence(tmp_path: Path) -> None:
    database = tmp_path / "missing-link.sqlite3"
    _stores(database)
    cycle_id = "learning-cycle:link-missing"
    missing_evidence_id = short_id(cycle_id, prefix="learning-closed-loop:")
    _complete_claim(SQLiteReplayClaimStore(database), cycle_id, missing_evidence_id)

    with pytest.raises(PersistentReplayReadinessError, match="references missing evidence"):
        check_database(database)


def test_check_rejects_completed_claim_linked_to_another_cycle(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wrong-cycle.sqlite3"
    evidence_store, claim_store = _stores(database)
    evidence = _terminal_evidence("learning-cycle:other")
    evidence_store.register(evidence)
    _complete_claim(claim_store, "learning-cycle:requested", evidence.evidence_id)

    with pytest.raises(PersistentReplayReadinessError, match="cycle identity mismatch"):
        check_database(database)


def test_check_rejects_completed_claim_linked_to_non_terminal_evidence(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wrong-kind.sqlite3"
    evidence_store, claim_store = _stores(database)
    cycle_id = "learning-cycle:wrong-kind"
    evidence = _terminal_evidence(cycle_id, kind="cognition.result", source="cognition")
    evidence_store.register(evidence)
    _complete_claim(claim_store, cycle_id, evidence.evidence_id)

    with pytest.raises(PersistentReplayReadinessError, match="does not reference terminal"):
        check_database(database)


def test_check_rejects_completed_claim_with_noncanonical_evidence_identifier(
    tmp_path: Path,
) -> None:
    database = tmp_path / "noncanonical.sqlite3"
    evidence_store, claim_store = _stores(database)
    cycle_id = "learning-cycle:noncanonical"
    evidence = _terminal_evidence(cycle_id, evidence_id="learning-closed-loop:wrong-id")
    evidence_store.register(evidence)
    _complete_claim(claim_store, cycle_id, evidence.evidence_id)

    with pytest.raises(PersistentReplayReadinessError, match="identifier is not canonical"):
        check_database(database)


def test_check_rejects_completed_claim_with_subject_result_mismatch(
    tmp_path: Path,
) -> None:
    database = tmp_path / "subject-mismatch.sqlite3"
    evidence_store, claim_store = _stores(database)
    cycle_id = "learning-cycle:subject-mismatch"
    evidence = _terminal_evidence(
        cycle_id,
        subject_id="result:subject",
        result_id="result:payload",
    )
    evidence_store.register(evidence)
    _complete_claim(claim_store, cycle_id, evidence.evidence_id)

    with pytest.raises(PersistentReplayReadinessError, match="result identity mismatch"):
        check_database(database)
