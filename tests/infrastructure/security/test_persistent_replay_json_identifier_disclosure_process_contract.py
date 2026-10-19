from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from foundation.utils.hash import short_id
from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_MODULE = "infrastructure.security.persistent_replay_ops"


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", _MODULE, *arguments],
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def _database_with_pending_terminal_evidence(database: Path) -> tuple[str, str]:
    SQLiteEvidenceStore(database)
    cycle_id = "learning-cycle:identifier-disclosure-process"
    result_id = "result:identifier-disclosure-process"
    SQLiteReplayClaimStore(database).claim(
        cycle_id,
        "sha256:identifier-disclosure-process",
        lease_seconds=5.0,
        now=datetime.now(UTC) - timedelta(seconds=60),
    )
    evidence_id = short_id(cycle_id, prefix="learning-closed-loop:")
    evidence = EvidenceRecord.create(
        evidence_id=evidence_id,
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id=result_id,
        version="1.1.0",
        trace_id=f"trace:{cycle_id}",
        collected_at=datetime.now(UTC).isoformat(),
        payload={
            "cycle_id": cycle_id,
            "result_id": result_id,
            "status": "completed",
        },
    )
    SQLiteEvidenceStore(database).register(evidence)
    return cycle_id, evidence_id


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def test_module_cli_redacts_pending_identifiers_without_explicit_opt_in(
    tmp_path: Path,
) -> None:
    database = tmp_path / "redacted-identifiers.sqlite3"
    cycle_id, evidence_id = _database_with_pending_terminal_evidence(database)

    result = _run_cli("check", "--database", str(database), "--json")

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    report = _read_report(result.stdout)
    assert report["action"] == "check"
    assert report["integrity_status"] == "pass"
    assert report["pending_evidence_reconciliation"] == 1
    assert "pending_reconciliations" not in report
    assert cycle_id not in result.stdout + result.stderr
    assert evidence_id not in result.stdout + result.stderr


def test_module_cli_includes_pending_identifiers_only_with_explicit_opt_in(
    tmp_path: Path,
) -> None:
    database = tmp_path / "explicit-identifiers.sqlite3"
    cycle_id, evidence_id = _database_with_pending_terminal_evidence(database)

    result = _run_cli(
        "check",
        "--database",
        str(database),
        "--json",
        "--include-pending-cycle-ids",
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    report = _read_report(result.stdout)
    details = report["pending_reconciliations"]
    assert len(details) == 1
    detail = details[0]
    assert detail == {
        "cycle_id": cycle_id,
        "claim_state": "claimed",
        "generation": 1,
        "attempts": 1,
        "lease_expired": True,
        "lease_expires_at": detail["lease_expires_at"],
        "evidence_id": evidence_id,
    }
    assert isinstance(detail["lease_expires_at"], (int, float))
    assert detail["lease_expired"] is True
    assert cycle_id in result.stdout
    assert evidence_id in result.stdout


# PART11_47_JSON_POLICY_GATE_PROCESS_DISCLOSURE_INVARIANCE

def test_module_cli_policy_gate_results_are_invariant_under_identifier_disclosure(
    tmp_path: Path,
) -> None:
    database = tmp_path / "policy-gate-disclosure-process.sqlite3"
    cycle_id, evidence_id = _database_with_pending_terminal_evidence(database)
    arguments = (
        "check",
        "--database",
        str(database),
        "--json",
        "--fail-on-pending-reconciliation",
        "--fail-on-expired-claims",
    )

    redacted = _run_cli(*arguments)
    assert redacted.returncode == 2
    assert redacted.stdout.count("\n") == 1
    assert "PENDING_RECONCILIATION_GATE: FAIL" in redacted.stderr
    assert "EXPIRED_CLAIM_GATE: FAIL" in redacted.stderr
    assert cycle_id not in redacted.stdout + redacted.stderr
    assert evidence_id not in redacted.stdout + redacted.stderr

    redacted_report = _read_report(redacted.stdout)
    assert redacted_report["exit_code"] == redacted.returncode
    assert redacted_report["pending_evidence_reconciliation"] == 1
    assert redacted_report["expired_claims"] == 1
    assert redacted_report["policy_gates"] == {
        "pending_reconciliation": "fail",
        "expired_claims": "fail",
    }
    assert "pending_reconciliations" not in redacted_report

    disclosed = _run_cli(*arguments, "--include-pending-cycle-ids")
    assert disclosed.returncode == redacted.returncode
    assert disclosed.stdout.count("\n") == 1
    assert disclosed.stderr == redacted.stderr
    assert cycle_id not in disclosed.stderr
    assert evidence_id not in disclosed.stderr

    disclosed_report = _read_report(disclosed.stdout)
    assert disclosed_report["exit_code"] == disclosed.returncode
    assert disclosed_report["policy_gates"] == redacted_report["policy_gates"]
    assert disclosed_report["pending_evidence_reconciliation"] == 1
    assert disclosed_report["expired_claims"] == 1
    details = disclosed_report["pending_reconciliations"]
    assert len(details) == 1
    assert details[0]["cycle_id"] == cycle_id
    assert details[0]["evidence_id"] == evidence_id
    assert details[0]["claim_state"] == "claimed"
    assert details[0]["generation"] == 1
    assert details[0]["attempts"] == 1
    assert details[0]["lease_expired"] is True
    assert cycle_id in disclosed.stdout
    assert evidence_id in disclosed.stdout
    assert redacted_report == {
        key: value
        for key, value in disclosed_report.items()
        if key != "pending_reconciliations"
    }

# PART11_48_JSON_EXPIRED_CLAIM_GATE_PROCESS_DISCLOSURE_INVARIANCE

def test_module_cli_expired_claim_gate_result_is_invariant_under_identifier_disclosure(
    tmp_path: Path,
) -> None:
    database = tmp_path / "expired-gate-disclosure-process.sqlite3"
    cycle_id, evidence_id = _database_with_pending_terminal_evidence(database)
    arguments = (
        "check",
        "--database",
        str(database),
        "--json",
        "--fail-on-expired-claims",
    )

    redacted = _run_cli(*arguments)
    assert redacted.returncode == 3
    assert redacted.stdout.count("\n") == 1
    assert "EXPIRED_CLAIM_GATE: FAIL" in redacted.stderr
    assert "PENDING_RECONCILIATION_GATE" not in redacted.stderr
    assert cycle_id not in redacted.stdout + redacted.stderr
    assert evidence_id not in redacted.stdout + redacted.stderr

    redacted_report = _read_report(redacted.stdout)
    assert redacted_report["action"] == "check"
    assert redacted_report["exit_code"] == redacted.returncode
    assert redacted_report["pending_evidence_reconciliation"] == 1
    assert redacted_report["expired_claims"] == 1
    assert redacted_report["policy_gates"] == {"expired_claims": "fail"}
    assert "pending_reconciliations" not in redacted_report

    disclosed = _run_cli(*arguments, "--include-pending-cycle-ids")
    assert disclosed.returncode == redacted.returncode
    assert disclosed.stdout.count("\n") == 1
    assert disclosed.stderr == redacted.stderr
    assert "PENDING_RECONCILIATION_GATE" not in disclosed.stderr
    assert cycle_id not in disclosed.stderr
    assert evidence_id not in disclosed.stderr

    disclosed_report = _read_report(disclosed.stdout)
    assert disclosed_report["action"] == "check"
    assert disclosed_report["exit_code"] == disclosed.returncode
    assert disclosed_report["pending_evidence_reconciliation"] == 1
    assert disclosed_report["expired_claims"] == 1
    assert disclosed_report["policy_gates"] == {"expired_claims": "fail"}
    details = disclosed_report["pending_reconciliations"]
    assert len(details) == 1
    assert details[0]["cycle_id"] == cycle_id
    assert details[0]["evidence_id"] == evidence_id
    assert details[0]["claim_state"] == "claimed"
    assert details[0]["generation"] == 1
    assert details[0]["attempts"] == 1
    assert details[0]["lease_expired"] is True
    assert cycle_id in disclosed.stdout
    assert evidence_id in disclosed.stdout
    assert redacted_report == {
        key: value
        for key, value in disclosed_report.items()
        if key != "pending_reconciliations"
    }

# PART11_49_JSON_ERROR_REPORT_DISCLOSURE_INVARIANCE

def test_module_cli_readiness_error_report_is_invariant_under_identifier_disclosure(
    tmp_path: Path,
) -> None:
    database = tmp_path / "private-readiness-error.sqlite3"
    SQLiteEvidenceStore(database)
    cycle_id = "learning-cycle:error-disclosure-invariance"
    result_id = "result:error-disclosure-invariance"
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
    arguments = ("check", "--database", str(database), "--json")

    redacted = _run_cli(*arguments)
    assert redacted.returncode == 1
    assert redacted.stdout.count("\n") == 1
    assert redacted.stderr.startswith("ERROR:")
    assert cycle_id not in redacted.stdout + redacted.stderr
    assert evidence_id not in redacted.stdout + redacted.stderr
    redacted_report = _read_report(redacted.stdout)
    assert redacted_report == {
        "action": "check",
        "error": {
            "code": "readiness_check_failed",
            "type": "PersistentReplayReadinessError",
        },
        "exit_code": 1,
        "integrity_status": "error",
        "policy_gates": {},
        "schema_version": 1,
    }
    assert "pending_reconciliations" not in redacted_report

    disclosed = _run_cli(*arguments, "--include-pending-cycle-ids")
    assert disclosed.returncode == redacted.returncode
    assert disclosed.stdout.count("\n") == 1
    assert disclosed.stdout == redacted.stdout
    assert disclosed.stderr == redacted.stderr
    assert cycle_id not in disclosed.stdout + disclosed.stderr
    assert evidence_id not in disclosed.stdout + disclosed.stderr
    disclosed_report = _read_report(disclosed.stdout)
    assert disclosed_report == redacted_report
    assert "pending_reconciliations" not in disclosed_report
