from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from foundation.utils.hash import short_id
from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import main
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _database_with_expired_pending_evidence(database: Path) -> tuple[str, str]:
    SQLiteEvidenceStore(database)
    claims = SQLiteReplayClaimStore(database)
    cycle_id = "learning-cycle:json-redaction"
    result_id = "result:json-redaction"
    claims.claim(
        cycle_id,
        "sha256:json-redaction-input",
        lease_seconds=5.0,
        now=datetime.now(UTC) - timedelta(seconds=60),
    )
    evidence_id = short_id(cycle_id, prefix="learning-closed-loop:")
    record = EvidenceRecord.create(
        evidence_id=evidence_id,
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id=result_id,
        version="1.1.0",
        trace_id=f"trace:{cycle_id}",
        collected_at=datetime.now(UTC).isoformat(),
        payload={"cycle_id": cycle_id, "result_id": result_id, "status": "completed"},
    )
    SQLiteEvidenceStore(database).register(record)
    return cycle_id, evidence_id


def _database_with_active_claim(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database).claim(
        "learning-cycle:json-active-claim",
        "sha256:json-active-claim-input",
        lease_seconds=300.0,
        now=datetime.now(UTC),
    )


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def test_json_report_is_parseable_and_redacts_identifiers_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "json-default.sqlite3"
    cycle_id, evidence_id = _database_with_expired_pending_evidence(database)

    assert main(["check", "--database", str(database), "--json"]) == 0
    captured = capsys.readouterr()
    report = _read_report(captured.out)

    assert report["schema_version"] == 1
    assert report["action"] == "check"
    assert report["integrity_status"] == "pass"
    assert report["evidence_records"] == 1
    assert report["replay_claims"] == 1
    assert report["expired_claims"] == 1
    assert report["pending_evidence_reconciliation"] == 1
    assert report["policy_gates"] == {}
    assert report["exit_code"] == 0
    assert cycle_id not in captured.out
    assert evidence_id not in captured.out
    assert "pending_reconciliations" not in report


def test_json_report_includes_pending_details_only_with_explicit_opt_in(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "json-details.sqlite3"
    cycle_id, evidence_id = _database_with_expired_pending_evidence(database)

    assert main(
        [
            "check",
            "--database",
            str(database),
            "--json",
            "--include-pending-cycle-ids",
        ]
    ) == 0
    report = _read_report(capsys.readouterr().out)
    details = report["pending_reconciliations"]

    assert len(details) == 1
    assert details[0]["cycle_id"] == cycle_id
    assert details[0]["evidence_id"] == evidence_id
    assert details[0]["lease_expired"] is True


def test_json_report_records_expired_claim_gate_failure_and_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "json-expired-gate.sqlite3"
    _database_with_expired_pending_evidence(database)

    exit_code = main(
        [
            "check",
            "--database",
            str(database),
            "--json",
            "--fail-on-expired-claims",
        ]
    )
    captured = capsys.readouterr()
    report = _read_report(captured.out)

    assert exit_code == 3
    assert report["policy_gates"] == {"expired_claims": "fail"}
    assert report["exit_code"] == 3
    assert "EXPIRED_CLAIM_GATE: FAIL" in captured.err


def test_json_report_preserves_both_gate_results_and_precedence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "json-both-gates.sqlite3"
    cycle_id, evidence_id = _database_with_expired_pending_evidence(database)

    exit_code = main(
        [
            "check",
            "--database",
            str(database),
            "--json",
            "--fail-on-pending-reconciliation",
            "--fail-on-expired-claims",
        ]
    )
    captured = capsys.readouterr()
    report = _read_report(captured.out)

    assert exit_code == 2
    assert report["policy_gates"] == {
        "pending_reconciliation": "fail",
        "expired_claims": "fail",
    }
    assert report["exit_code"] == 2
    assert "PENDING_RECONCILIATION_GATE: FAIL" in captured.err
    assert "EXPIRED_CLAIM_GATE: FAIL" in captured.err
    assert cycle_id not in captured.out + captured.err
    assert evidence_id not in captured.out + captured.err


def test_json_report_marks_expired_claim_gate_pass_for_active_lease(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "json-active-lease.sqlite3"
    _database_with_active_claim(database)

    assert main(
        [
            "check",
            "--database",
            str(database),
            "--json",
            "--fail-on-expired-claims",
        ]
    ) == 0
    report = _read_report(capsys.readouterr().out)

    assert report["expired_claims"] == 0
    assert report["policy_gates"] == {"expired_claims": "pass"}
    assert report["exit_code"] == 0
