from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from infrastructure.security.persistent_replay_ops import main
from infrastructure.security.persistent_store import SQLiteEvidenceStore


def _read_error_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def test_json_error_report_for_missing_database_is_parseable_and_does_not_leak_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "private-database-path.sqlite3"

    assert main(["check", "--database", str(database), "--json"]) == 1
    captured = capsys.readouterr()
    report = _read_error_report(captured.out)

    assert captured.out.count("\n") == 1
    assert report == {
        "action": "check",
        "error": {"code": "database_not_found", "type": "FileNotFoundError"},
        "exit_code": 1,
        "integrity_status": "error",
        "policy_gates": {},
        "schema_version": 1,
    }
    assert str(database) not in captured.out
    assert "ERROR:" in captured.err
    assert "[absolute path]" in captured.err
    assert str(database) not in captured.err


def test_json_error_report_classifies_readiness_schema_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "incomplete-schema.sqlite3"
    SQLiteEvidenceStore(database)

    assert main(["check", "--database", str(database), "--json"]) == 1
    captured = capsys.readouterr()
    report = _read_error_report(captured.out)

    assert report["action"] == "check"
    assert report["integrity_status"] == "error"
    assert report["error"] == {
        "code": "readiness_check_failed",
        "type": "PersistentReplayReadinessError",
    }
    assert report["exit_code"] == 1
    assert report["policy_gates"] == {}
    assert "database is missing SH-3 table(s)" in captured.err
