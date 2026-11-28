from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from foundation.utils.hash import short_id
from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import (
    PersistentReplayReadinessError,
    check_database,
    main,
)
from infrastructure.security.persistent_store import (
    ReplayClaimStatus,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _terminal_evidence(
    cycle_id: str,
    *,
    result_id: str = "result:pending-reconciliation",
    kind: str = "learning.closed_loop",
    source: str = "kernel.learning_feedback_loop",
) -> EvidenceRecord:
    return EvidenceRecord.create(
        evidence_id=short_id(cycle_id, prefix="learning-closed-loop:"),
        kind=kind,
        source=source,
        subject_id=result_id,
        version="1.1.0",
        trace_id=f"trace:{cycle_id}",
        collected_at=datetime.now(UTC).isoformat(),
        payload={"cycle_id": cycle_id, "result_id": result_id},
    )


def _claimed_cycle(
    database: Path,
    cycle_id: str,
) -> tuple[SQLiteEvidenceStore, SQLiteReplayClaimStore, datetime]:
    evidence_store = SQLiteEvidenceStore(database)
    claim_store = SQLiteReplayClaimStore(database)
    instant = datetime.now(UTC)
    claim = claim_store.claim(
        cycle_id,
        f"sha256:{cycle_id}",
        lease_seconds=300.0,
        now=instant,
    )
    assert claim.status is ReplayClaimStatus.CLAIMED
    return evidence_store, claim_store, instant


def test_check_reports_evidence_pending_claim_completion_without_mutating_it(
    tmp_path: Path,
) -> None:
    database = tmp_path / "pending-claimed.sqlite3"
    cycle_id = "learning-cycle:pending-claimed"
    evidence_store, claim_store, _ = _claimed_cycle(database, cycle_id)
    evidence = _terminal_evidence(cycle_id)
    evidence_store.register(evidence)

    report = check_database(database)

    assert report.pending_evidence_reconciliation_count == 1
    claim = claim_store.get(cycle_id)
    assert claim is not None
    assert claim.status is ReplayClaimStatus.CLAIMED
    assert claim.evidence_id is None
    persisted = evidence_store.get(evidence.evidence_id)
    assert persisted is not None and persisted.verify()


def test_check_reports_evidence_pending_released_claim_reconciliation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "pending-released.sqlite3"
    cycle_id = "learning-cycle:pending-released"
    evidence_store, claim_store, instant = _claimed_cycle(database, cycle_id)
    claim = claim_store.get(cycle_id)
    assert claim is not None and claim.owner_token is not None
    assert claim_store.release(
        cycle_id,
        claim.owner_token,
        claim.generation,
        now=instant + timedelta(seconds=1),
    )
    evidence_store.register(_terminal_evidence(cycle_id))

    report = check_database(database)

    assert report.pending_evidence_reconciliation_count == 1
    released = claim_store.get(cycle_id)
    assert released is not None
    assert released.status is ReplayClaimStatus.RELEASED
    assert released.evidence_id is None


def test_check_rejects_invalid_evidence_for_pending_claim_reconciliation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "pending-invalid-evidence.sqlite3"
    cycle_id = "learning-cycle:pending-invalid-evidence"
    evidence_store, _, _ = _claimed_cycle(database, cycle_id)
    evidence_store.register(
        _terminal_evidence(
            cycle_id,
            kind="cognition.result",
            source="cognition",
        )
    )

    with pytest.raises(
        PersistentReplayReadinessError,
        match="does not reference terminal closed-loop evidence",
    ):
        check_database(database)


def test_check_cli_surfaces_pending_evidence_reconciliation_warning(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "pending-cli.sqlite3"
    cycle_id = "learning-cycle:pending-cli"
    evidence_store, _, _ = _claimed_cycle(database, cycle_id)
    evidence_store.register(_terminal_evidence(cycle_id))

    exit_code = main(["check", "--database", str(database)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "CHECK: PASS" in output
    assert "pending_evidence_reconciliation=1" in output
    assert "warning=canonical terminal evidence exists" in output
