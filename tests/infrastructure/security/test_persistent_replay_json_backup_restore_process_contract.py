from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

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


def test_backup_process_reports_destination_exists_without_overwrite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "existing-backup.sqlite3"
    _initialize_database(source)
    original_content = b"preserve-existing-backup"
    destination.write_bytes(original_content)

    result = _run_cli(
        "backup",
        "--database",
        str(source),
        "--destination",
        str(destination),
        "--json",
    )

    assert result.returncode == 1
    assert result.stdout.count("\n") == 1
    report = _read_report(result.stdout)
    assert report == {
        "schema_version": 1,
        "action": "backup",
        "integrity_status": "error",
        "policy_gates": {},
        "error": {"code": "destination_exists", "type": "FileExistsError"},
        "exit_code": 1,
    }
    assert str(destination) not in result.stdout
    assert result.stderr.startswith("ERROR:")
    assert "[absolute path]" in result.stderr
    assert str(destination) not in result.stderr
    assert destination.read_bytes() == original_content


def test_restore_process_reports_missing_backup_without_path_leak(
    tmp_path: Path,
) -> None:
    missing_backup = tmp_path / "private-missing-backup.sqlite3"
    destination = tmp_path / "restored.sqlite3"

    result = _run_cli(
        "restore",
        "--backup",
        str(missing_backup),
        "--destination",
        str(destination),
        "--json",
    )

    assert result.returncode == 1
    assert result.stdout.count("\n") == 1
    report = _read_report(result.stdout)
    assert report == {
        "schema_version": 1,
        "action": "restore",
        "integrity_status": "error",
        "policy_gates": {},
        "error": {"code": "database_not_found", "type": "FileNotFoundError"},
        "exit_code": 1,
    }
    assert str(missing_backup) not in result.stdout
    assert result.stderr.startswith("ERROR:")
    assert "[absolute path]" in result.stderr
    assert str(missing_backup) not in result.stderr
    assert not destination.exists()


def test_restore_process_reports_existing_destination_without_overwrite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    destination = tmp_path / "existing-restore.sqlite3"
    _initialize_database(source)

    backup_result = _run_cli(
        "backup",
        "--database",
        str(source),
        "--destination",
        str(backup),
        "--json",
    )
    assert backup_result.returncode == 0, backup_result.stderr
    assert _read_report(backup_result.stdout)["action"] == "backup"

    original_content = b"preserve-existing-restore"
    destination.write_bytes(original_content)
    result = _run_cli(
        "restore",
        "--backup",
        str(backup),
        "--destination",
        str(destination),
        "--json",
    )

    assert result.returncode == 1
    assert result.stdout.count("\n") == 1
    report = _read_report(result.stdout)
    assert report == {
        "schema_version": 1,
        "action": "restore",
        "integrity_status": "error",
        "policy_gates": {},
        "error": {"code": "destination_exists", "type": "FileExistsError"},
        "exit_code": 1,
    }
    assert str(destination) not in result.stdout
    assert result.stderr.startswith("ERROR:")
    assert "[absolute path]" in result.stderr
    assert str(destination) not in result.stderr
    assert destination.read_bytes() == original_content

# PART11_52_BACKUP_RESTORE_TIMEOUT_ERROR_PROCESS_CONTRACT

@pytest.mark.parametrize("action", ("backup", "restore"))
@pytest.mark.parametrize("timeout_value", ("0", "nan", "inf"))
def test_backup_restore_process_rejects_invalid_timeout_with_stable_json_error(
    tmp_path: Path,
    action: str,
    timeout_value: str,
) -> None:
    source = tmp_path / f"private-{action}-source.sqlite3"
    destination = tmp_path / f"private-{action}-destination.sqlite3"
    if action == "backup":
        arguments = (
            "backup",
            "--database",
            str(source),
            "--destination",
            str(destination),
            "--timeout-seconds",
            timeout_value,
            "--json",
        )
    else:
        arguments = (
            "restore",
            "--backup",
            str(source),
            "--destination",
            str(destination),
            "--timeout-seconds",
            timeout_value,
            "--json",
        )

    result = _run_cli(*arguments)

    assert result.returncode == 1, result.stderr
    assert result.stdout.count("\n") == 1
    assert result.stderr == (
        "ERROR: timeout_seconds must be finite and greater than zero\n"
    )
    assert _read_report(result.stdout) == {
        "schema_version": 1,
        "action": action,
        "integrity_status": "error",
        "policy_gates": {},
        "error": {"code": "invalid_argument", "type": "ValueError"},
        "exit_code": 1,
    }
    for private_path in (source, destination):
        assert str(private_path) not in result.stdout + result.stderr
        assert not private_path.exists()
