from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from foundation.utils.hash import short_id
from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import main
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _database_with_pending_evidence(tmp_path: Path) -> tuple[Path, str, str]:
    database = tmp_path / "pending-policy-gate.sqlite3"
    cycle_id = "learning-cycle:policy-gate-private-result"
    result_id = "result:policy-gate-private-result"
    SQLiteReplayClaimStore(database).claim(
        cycle_id,
        "sha256:policy-gate-input",
        lease_seconds=300.0,
        now=datetime.now(UTC),
    )
    evidence = EvidenceRecord.create(
        evidence_id=short_id(cycle_id, prefix="learning-closed-loop:"),
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id=result_id,
        version="1.1.0",
        trace_id=f"trace:{cycle_id}",
        collected_at=datetime.now(UTC).isoformat(),
        payload={"cycle_id": cycle_id, "result_id": result_id, "status": "completed"},
    )
    SQLiteEvidenceStore(database).register(evidence)
    return database, cycle_id, evidence.evidence_id


def test_policy_gate_is_opt_in_and_pending_state_is_allowed_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database, cycle_id, evidence_id = _database_with_pending_evidence(tmp_path)

    assert main(["check", "--database", str(database)]) == 0
    captured = capsys.readouterr()

    assert "CHECK: PASS" in captured.out
    assert "pending_evidence_reconciliation=1" in captured.out
    assert "PENDING_RECONCILIATION_GATE" not in captured.out + captured.err
    assert cycle_id not in captured.out + captured.err
    assert evidence_id not in captured.out + captured.err


def test_policy_gate_returns_distinct_nonzero_code_for_pending_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database, cycle_id, evidence_id = _database_with_pending_evidence(tmp_path)

    exit_code = main(
        [
            "check",
            "--database",
            str(database),
            "--fail-on-pending-reconciliation",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "CHECK: PASS" in captured.out
    assert "PENDING_RECONCILIATION_GATE: FAIL" in captured.err
    assert "found 1" in captured.err
    assert cycle_id not in captured.out + captured.err
    assert evidence_id not in captured.out + captured.err


def test_policy_gate_passes_when_there_is_no_pending_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "empty-policy-gate.sqlite3"
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)

    assert main(
        [
            "check",
            "--database",
            str(database),
            "--fail-on-pending-reconciliation",
        ]
    ) == 0
    captured = capsys.readouterr()

    assert "PENDING_RECONCILIATION_GATE: PASS" in captured.out
    assert "PENDING_RECONCILIATION_GATE: FAIL" not in captured.err
