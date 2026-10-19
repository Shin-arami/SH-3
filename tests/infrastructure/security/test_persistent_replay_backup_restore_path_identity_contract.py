from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_same_normalized_source_and_destination_are_rejected_without_mutation(
    tmp_path: Path,
    command: str,
) -> None:
    source = tmp_path / f"private-{command}-source.sqlite3"
    _initialize_database(source)
    original_bytes = source.read_bytes()

    # The existing alias directory makes the lexical '..' destination valid;
    # destination normalization must still identify the existing source file.
    alias_directory = tmp_path / "path-alias"
    alias_directory.mkdir()
    destination_alias = alias_directory / ".." / source.name

    if command == "backup":
        arguments = (
            "backup",
            "--database",
            str(source),
            "--destination",
            str(destination_alias),
            "--json",
        )
    else:
        arguments = (
            "restore",
            "--backup",
            str(source),
            "--destination",
            str(destination_alias),
            "--json",
        )

    result = _run_cli(*arguments)

    assert result.returncode == 1
    assert result.stdout.count("\n") == 1
    report = json.loads(result.stdout)
    assert report == {
        "schema_version": 1,
        "action": command,
        "integrity_status": "error",
        "policy_gates": {},
        "error": {
            "code": "readiness_check_failed",
            "type": "PersistentReplayReadinessError",
        },
        "exit_code": 1,
    }
    assert result.stderr == (
        "ERROR: source and destination database paths must be different\n"
    )
    assert str(source) not in result.stdout
    assert str(source) not in result.stderr
    assert "traceback" not in result.stderr.lower()
    assert source.is_file()
    assert source.read_bytes() == original_bytes
    assert not any(
        child.name.endswith(".partial") for child in tmp_path.iterdir()
    )
