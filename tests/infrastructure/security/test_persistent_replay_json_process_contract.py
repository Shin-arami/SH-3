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


def _initialize_database(path: Path) -> None:
    SQLiteEvidenceStore(path)
    SQLiteReplayClaimStore(path)


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _seed_expired_pending_evidence(database: Path) -> tuple[str, str]:
    _initialize_database(database)
    cycle_id = "learning-cycle:subprocess-policy-precedence"
    result_id = "result:subprocess-policy-precedence"
    stale_now = datetime.now(UTC) - timedelta(seconds=60)
    SQLiteReplayClaimStore(database).claim(
        cycle_id,
        "sha256:subprocess-policy-precedence",
        lease_seconds=5.0,
        now=stale_now,
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


def test_module_cli_success_reports_are_single_json_objects_for_all_commands(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    _initialize_database(source)

    commands = (
        (
            ["check", "--database", str(source), "--json", "--fail-on-expired-claims"],
            "check",
            source.resolve(),
            {"expired_claims": "pass"},
        ),
        (
            ["backup", "--database", str(source), "--destination", str(backup), "--json"],
            "backup",
            backup.resolve(),
            {},
        ),
        (
            ["restore", "--backup", str(backup), "--destination", str(restored), "--json"],
            "restore",
            restored.resolve(),
            {},
        ),
    )

    for arguments, action, expected_database, expected_gates in commands:
        result = _run_cli(*arguments)
        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
        assert result.stdout.count("\n") == 1
        report = _read_report(result.stdout)
        assert report["schema_version"] == 1
        assert report["action"] == action
        assert report["database"] == str(expected_database)
        assert report["integrity_status"] == "pass"
        assert report["policy_gates"] == expected_gates
        assert report["exit_code"] == result.returncode


def test_module_cli_check_error_is_json_on_stdout_and_diagnostic_on_stderr(
    tmp_path: Path,
) -> None:
    missing_database = tmp_path / "private-missing-database.sqlite3"

    result = _run_cli("check", "--database", str(missing_database), "--json")

    assert result.returncode == 1
    assert result.stdout.count("\n") == 1
    assert str(missing_database) not in result.stdout
    report = _read_report(result.stdout)
    assert report == {
        "schema_version": 1,
        "action": "check",
        "integrity_status": "error",
        "policy_gates": {},
        "error": {"code": "database_not_found", "type": "FileNotFoundError"},
        "exit_code": 1,
    }
    assert result.stderr.startswith("ERROR:")
    assert "[absolute path]" in result.stderr
    assert str(missing_database) not in result.stderr


def test_module_cli_expired_claim_gate_returns_process_exit_code_three(
    tmp_path: Path,
) -> None:
    database = tmp_path / "expired-claim.sqlite3"
    _initialize_database(database)
    cycle_id = "learning-cycle:subprocess-expired-gate"
    SQLiteReplayClaimStore(database).claim(
        cycle_id,
        "sha256:subprocess-expired-gate",
        lease_seconds=5.0,
        now=datetime.now(UTC) - timedelta(seconds=60),
    )

    result = _run_cli(
        "check",
        "--database",
        str(database),
        "--json",
        "--fail-on-expired-claims",
    )

    assert result.returncode == 3
    assert result.stdout.count("\n") == 1
    report = _read_report(result.stdout)
    assert report["action"] == "check"
    assert report["integrity_status"] == "pass"
    assert report["policy_gates"] == {"expired_claims": "fail"}
    assert report["exit_code"] == result.returncode
    assert cycle_id not in result.stdout + result.stderr
    assert "EXPIRED_CLAIM_GATE: FAIL" in result.stderr


def test_module_cli_both_failed_gates_keep_pending_precedence_and_redaction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "both-gates.sqlite3"
    cycle_id, evidence_id = _seed_expired_pending_evidence(database)

    result = _run_cli(
        "check",
        "--database",
        str(database),
        "--json",
        "--fail-on-pending-reconciliation",
        "--fail-on-expired-claims",
    )

    assert result.returncode == 2
    assert result.stdout.count("\n") == 1
    report = _read_report(result.stdout)
    assert report["policy_gates"] == {
        "pending_reconciliation": "fail",
        "expired_claims": "fail",
    }
    assert report["exit_code"] == result.returncode
    assert cycle_id not in result.stdout + result.stderr
    assert evidence_id not in result.stdout + result.stderr
    assert "PENDING_RECONCILIATION_GATE: FAIL" in result.stderr
    assert "EXPIRED_CLAIM_GATE: FAIL" in result.stderr
