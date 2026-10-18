from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from foundation.utils.hash import short_id
from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import main
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _database_with_expired_claim(
    database: Path,
    *,
    include_terminal_evidence: bool = False,
) -> tuple[str, str | None]:
    SQLiteEvidenceStore(database)
    claim_store = SQLiteReplayClaimStore(database)
    cycle_id = "learning-cycle:expired-claim-policy"
    result_id = "result:expired-claim-policy"
    claim_time = datetime.now(UTC) - timedelta(seconds=60)
    claim_store.claim(
        cycle_id,
        "sha256:expired-claim-policy-input",
        lease_seconds=5.0,
        now=claim_time,
    )
    evidence_id: str | None = None
    if include_terminal_evidence:
        evidence_id = short_id(cycle_id, prefix="learning-closed-loop:")
        evidence = EvidenceRecord.create(
            evidence_id=evidence_id,
            kind="learning.closed_loop",
            source="kernel.learning_feedback_loop",
            subject_id=result_id,
            version="1.1.0",
            trace_id=f"trace:{cycle_id}",
            collected_at=datetime.now(UTC).isoformat(),
            payload={"cycle_id": cycle_id, "result_id": result_id, "status": "completed"},
        )
        SQLiteEvidenceStore(database).register(evidence)
    return cycle_id, evidence_id


def test_expired_claim_gate_is_opt_in_and_default_behavior_is_unchanged(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "expired-default.sqlite3"
    _database_with_expired_claim(database)

    assert main(["check", "--database", str(database)]) == 0
    captured = capsys.readouterr()

    assert "CHECK: PASS" in captured.out
    assert "expired_claims=1" in captured.out
    assert "EXPIRED_CLAIM_GATE" not in captured.out + captured.err


def test_expired_claim_gate_fails_with_distinct_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "expired-fail.sqlite3"
    _database_with_expired_claim(database)

    exit_code = main(
        ["check", "--database", str(database), "--fail-on-expired-claims"]
    )
    captured = capsys.readouterr()

    assert exit_code == 3
    assert "EXPIRED_CLAIM_GATE: FAIL" in captured.err
    assert "found 1" in captured.err


def test_expired_claim_gate_passes_for_an_active_lease(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "active-lease.sqlite3"
    SQLiteEvidenceStore(database)
    claim_store = SQLiteReplayClaimStore(database)
    claim_store.claim(
        "learning-cycle:active-lease-policy",
        "sha256:active-lease-policy-input",
        lease_seconds=300.0,
        now=datetime.now(UTC),
    )

    assert main(
        ["check", "--database", str(database), "--fail-on-expired-claims"]
    ) == 0
    captured = capsys.readouterr()

    assert "expired_claims=0" in captured.out
    assert "EXPIRED_CLAIM_GATE: PASS" in captured.out
    assert "EXPIRED_CLAIM_GATE: FAIL" not in captured.err


def test_pending_gate_has_exit_code_precedence_when_both_gates_fail(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "both-gates-fail.sqlite3"
    _database_with_expired_claim(database, include_terminal_evidence=True)

    exit_code = main(
        [
            "check",
            "--database",
            str(database),
            "--fail-on-pending-reconciliation",
            "--fail-on-expired-claims",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "PENDING_RECONCILIATION_GATE: FAIL" in captured.err
    assert "EXPIRED_CLAIM_GATE: FAIL" in captured.err
    assert "cycle_id=" not in captured.out + captured.err
