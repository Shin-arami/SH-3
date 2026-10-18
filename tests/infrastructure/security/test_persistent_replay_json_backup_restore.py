from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from infrastructure.security.persistent_replay_ops import backup_database, main
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialized_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def test_backup_json_report_is_parseable_and_identifies_operation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "source.sqlite3"
    destination = tmp_path / "backups" / "backup.sqlite3"
    _initialized_database(database)

    assert main(
        ["backup", "--database", str(database), "--destination", str(destination), "--json"]
    ) == 0
    captured = capsys.readouterr()
    report = _read_report(captured.out)

    assert captured.out.count("\n") == 1
    assert captured.err == ""
    assert report["schema_version"] == 1
    assert report["action"] == "backup"
    assert report["database"] == str(destination.resolve())
    assert report["integrity_status"] == "pass"
    assert report["evidence_records"] == 0
    assert report["replay_claims"] == 0
    assert report["policy_gates"] == {}
    assert report["exit_code"] == 0
    assert destination.is_file()


def test_restore_json_report_is_parseable_and_identifies_operation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    destination = tmp_path / "restored" / "restore.sqlite3"
    _initialized_database(database)
    backup_database(database, backup)

    assert main(
        ["restore", "--backup", str(backup), "--destination", str(destination), "--json"]
    ) == 0
    captured = capsys.readouterr()
    report = _read_report(captured.out)

    assert captured.out.count("\n") == 1
    assert captured.err == ""
    assert report["schema_version"] == 1
    assert report["action"] == "restore"
    assert report["database"] == str(destination.resolve())
    assert report["integrity_status"] == "pass"
    assert report["evidence_records"] == 0
    assert report["replay_claims"] == 0
    assert report["policy_gates"] == {}
    assert report["exit_code"] == 0
    assert destination.is_file()


def test_backup_json_error_reports_existing_destination_without_overwrite(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "source.sqlite3"
    destination = tmp_path / "existing-backup.sqlite3"
    _initialized_database(database)
    destination.write_bytes(b"keep-this-content")

    assert main(
        ["backup", "--database", str(database), "--destination", str(destination), "--json"]
    ) == 1
    captured = capsys.readouterr()
    report = _read_report(captured.out)

    assert captured.out.count("\n") == 1
    assert report == {
        "action": "backup",
        "error": {"code": "destination_exists", "type": "FileExistsError"},
        "exit_code": 1,
        "integrity_status": "error",
        "policy_gates": {},
        "schema_version": 1,
    }
    assert str(destination) not in captured.out
    assert str(destination) in captured.err
    assert destination.read_bytes() == b"keep-this-content"


def test_restore_json_error_reports_missing_backup_without_path_leak(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    backup = tmp_path / "missing-private-backup.sqlite3"
    destination = tmp_path / "restore.sqlite3"

    assert main(
        ["restore", "--backup", str(backup), "--destination", str(destination), "--json"]
    ) == 1
    captured = capsys.readouterr()
    report = _read_report(captured.out)

    assert captured.out.count("\n") == 1
    assert report == {
        "action": "restore",
        "error": {"code": "database_not_found", "type": "FileNotFoundError"},
        "exit_code": 1,
        "integrity_status": "error",
        "policy_gates": {},
        "schema_version": 1,
    }
    assert str(backup) not in captured.out
    assert str(backup) in captured.err
    assert not destination.exists()


def test_backup_text_report_remains_default_without_json_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "source.sqlite3"
    destination = tmp_path / "backup.sqlite3"
    _initialized_database(database)

    assert main(
        ["backup", "--database", str(database), "--destination", str(destination)]
    ) == 0
    captured = capsys.readouterr()

    assert captured.out.startswith("BACKUP: PASS\n")
    assert "\"schema_version\"" not in captured.out
    assert captured.err == ""
