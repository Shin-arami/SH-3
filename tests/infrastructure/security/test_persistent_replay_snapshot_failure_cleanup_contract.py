from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
@pytest.mark.parametrize(
    "failure_stage",
    ("snapshot", "verification"),
    ids=("snapshot-failure", "snapshot-verification-failure"),
)
def test_snapshot_failure_removes_partial_file_and_preserves_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    failure_stage: str,
) -> None:
    source = tmp_path / f"private-{command}-source.sqlite3"
    destination = tmp_path / f"private-{command}-destination.sqlite3"
    _initialize_database(source)
    original_source_bytes = source.read_bytes()
    temporary_paths: list[Path] = []

    def inject_snapshot_failure(
        source_path: Path,
        temporary_path: Path,
        *,
        timeout_seconds: float,
    ) -> None:
        assert source_path == source.resolve()
        assert timeout_seconds > 0
        assert temporary_path.is_file()
        temporary_paths.append(temporary_path)
        if failure_stage == "snapshot":
            raise replay_ops.PersistentReplayReadinessError(
                "injected online snapshot failure"
            )
        temporary_path.write_bytes(b"not a SQLite database")

    monkeypatch.setattr(
        replay_ops,
        "_backup_to_temporary",
        inject_snapshot_failure,
    )

    if command == "backup":
        arguments = [
            "backup",
            "--database",
            str(source),
            "--destination",
            str(destination),
            "--json",
        ]
    else:
        arguments = [
            "restore",
            "--backup",
            str(source),
            "--destination",
            str(destination),
            "--json",
        ]

    exit_code = replay_ops.main(arguments)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out.count("\n") == 1
    assert _read_report(captured.out) == {
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
    assert captured.err.startswith("ERROR:")
    assert "traceback" not in captured.err.lower()
    assert str(source) not in captured.out + captured.err
    assert str(destination) not in captured.out + captured.err
    assert source.is_file()
    assert source.read_bytes() == original_source_bytes
    assert not destination.exists()
    assert len(temporary_paths) == 1
    assert not temporary_paths[0].exists()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial"))
