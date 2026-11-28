from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from foundation.utils.hash import short_id
from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import (
    PendingEvidenceReconciliation,
    check_database,
    main,
)
from infrastructure.security.persistent_store import (
    ReplayClaimStatus,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _terminal_evidence(cycle_id: str, result_id: str) -> EvidenceRecord:
    return EvidenceRecord.create(
        evidence_id=short_id(cycle_id, prefix="learning-closed-loop:"),
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id=result_id,
        version="1.1.0",
        trace_id=f"trace:{cycle_id}",
        collected_at=datetime.now(UTC).isoformat(),
        payload={"cycle_id": cycle_id, "result_id": result_id},
    )


def _claimed_with_evidence(
    database: Path,
    cycle_id: str,
    *,
    lease_seconds: float = 300.0,
    claim_time: datetime | None = None,
) -> tuple[SQLiteEvidenceStore, SQLiteReplayClaimStore, EvidenceRecord, datetime]:
    evidence_store = SQLiteEvidenceStore(database)
    claim_store = SQLiteReplayClaimStore(database)
    instant = claim_time or datetime.now(UTC)
    claim_store.claim(
        cycle_id,
        f"sha256:{cycle_id}",
        lease_seconds=lease_seconds,
        now=instant,
    )
    result_id = f"result:{cycle_id}"
    evidence = _terminal_evidence(cycle_id, result_id)
    evidence_store.register(evidence)
    return evidence_store, claim_store, evidence, instant


def test_readiness_report_exposes_active_pending_reconciliation_details(
    tmp_path: Path,
) -> None:
    database = tmp_path / "active-pending-details.sqlite3"
    cycle_id = "learning-cycle:active-details"
    _, claim_store, evidence, _ = _claimed_with_evidence(database, cycle_id)

    report = check_database(database)

    assert report.pending_evidence_reconciliation_count == 1
    assert len(report.pending_evidence_reconciliations) == 1
    detail = report.pending_evidence_reconciliations[0]
    assert isinstance(detail, PendingEvidenceReconciliation)
    assert detail.cycle_id == cycle_id
    assert detail.claim_state == "claimed"
    assert detail.generation == 1
    assert detail.attempts == 1
    assert detail.evidence_id == evidence.evidence_id
    assert detail.lease_expires_at is not None
    assert detail.lease_expired is False
    assert cycle_id not in repr(report)
    assert cycle_id not in repr(report.pending_evidence_reconciliations)
    claim = claim_store.get(cycle_id)
    assert claim is not None and claim.status is ReplayClaimStatus.CLAIMED


def test_readiness_report_marks_expired_pending_lease(
    tmp_path: Path,
) -> None:
    database = tmp_path / "expired-pending-details.sqlite3"
    cycle_id = "learning-cycle:expired-details"
    old_time = datetime.now(UTC) - timedelta(seconds=60)
    _, claim_store, evidence, _ = _claimed_with_evidence(
        database,
        cycle_id,
        lease_seconds=5.0,
        claim_time=old_time,
    )

    report = check_database(database)

    assert report.expired_claim_count == 1
    assert report.pending_evidence_reconciliation_count == 1
    detail = report.pending_evidence_reconciliations[0]
    assert detail.cycle_id == cycle_id
    assert detail.evidence_id == evidence.evidence_id
    assert detail.claim_state == "claimed"
    assert detail.lease_expired is True
    persisted = claim_store.get(cycle_id)
    assert persisted is not None and persisted.status is ReplayClaimStatus.CLAIMED


def test_readiness_report_marks_released_pending_claim_without_lease(
    tmp_path: Path,
) -> None:
    database = tmp_path / "released-pending-details.sqlite3"
    cycle_id = "learning-cycle:released-details"
    _, claim_store, evidence, instant = _claimed_with_evidence(database, cycle_id)
    claim = claim_store.get(cycle_id)
    assert claim is not None and claim.owner_token is not None
    assert claim_store.release(
        cycle_id,
        claim.owner_token,
        claim.generation,
        now=instant + timedelta(seconds=1),
    )

    report = check_database(database)

    assert report.pending_evidence_reconciliation_count == 1
    detail = report.pending_evidence_reconciliations[0]
    assert detail.cycle_id == cycle_id
    assert detail.claim_state == "released"
    assert detail.evidence_id == evidence.evidence_id
    assert detail.lease_expires_at is None
    assert detail.lease_expired is None
    persisted = claim_store.get(cycle_id)
    assert persisted is not None and persisted.status is ReplayClaimStatus.RELEASED


def test_pending_details_are_hidden_by_default_and_opt_in_on_cli(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "pending-detail-cli.sqlite3"
    cycle_id = "learning-cycle:private-result-identifier"
    _, _, evidence, _ = _claimed_with_evidence(database, cycle_id)

    assert main(["check", "--database", str(database)]) == 0
    default_output = capsys.readouterr().out
    assert "pending_evidence_reconciliation=1" in default_output
    assert cycle_id not in default_output
    assert evidence.evidence_id not in default_output

    assert main(
        [
            "check",
            "--database",
            str(database),
            "--include-pending-cycle-ids",
        ]
    ) == 0
    detailed_output = capsys.readouterr().out
    assert cycle_id in detailed_output
    assert evidence.evidence_id in detailed_output
    assert "pending[1].claim_state=claimed" in detailed_output
    assert "pending[1].lease_expired=false" in detailed_output
    assert "owner_token" not in detailed_output
    assert "fingerprint" not in detailed_output


def test_pending_detail_rejects_inconsistent_lease_fields() -> None:
    with pytest.raises(ValueError, match="claimed detail requires lease information"):
        PendingEvidenceReconciliation(
            cycle_id="learning-cycle:invalid-detail",
            claim_state="claimed",
            generation=1,
            attempts=1,
            evidence_id="learning-closed-loop:invalid-detail",
            lease_expires_at=None,
            lease_expired=None,
        )

    with pytest.raises(
        ValueError,
        match="released detail cannot contain lease information",
    ):
        PendingEvidenceReconciliation(
            cycle_id="learning-cycle:invalid-released-detail",
            claim_state="released",
            generation=1,
            attempts=1,
            evidence_id="learning-closed-loop:invalid-released-detail",
            lease_expires_at=1.0,
            lease_expired=False,
        )
