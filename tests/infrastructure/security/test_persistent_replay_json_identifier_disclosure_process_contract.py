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
