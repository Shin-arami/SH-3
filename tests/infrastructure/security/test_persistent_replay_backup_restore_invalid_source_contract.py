from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

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


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_invalid_source_is_rejected_before_destination_parent_creation(
    tmp_path: Path,
    command: str,
) -> None:
    source = tmp_path / f"private-{command}-input.sqlite3"
    source.write_bytes(b"not a SQLite database")
    original_source_bytes = source.read_bytes()

    destination_parent = tmp_path / "destination-parent-must-not-be-created"
    destination = destination_parent / f"{command}-destination.sqlite3"
    assert not destination_parent.exists()

    if command == "backup":
        arguments = (
            "backup",
            "--database",
            str(source),
            "--destination",
            str(destination),
            "--json",
        )
    else:
        arguments = (
            "restore",
            "--backup",
            str(source),
            "--destination",
            str(destination),
            "--json",
        )

    result = _run_cli(*arguments)

    assert result.returncode == 1
    assert result.stdout.count("\n") == 1
    assert _read_report(result.stdout) == {
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
    assert result.stderr.startswith("ERROR: SQLite inspection failed for ")
    assert "not a database" in result.stderr.lower()
    assert "traceback" not in result.stderr.lower()
    assert str(source) not in result.stdout + result.stderr
    assert str(destination) not in result.stdout + result.stderr
    assert source.is_file()
    assert source.read_bytes() == original_source_bytes
    assert not destination_parent.exists()
    assert not destination.exists()
