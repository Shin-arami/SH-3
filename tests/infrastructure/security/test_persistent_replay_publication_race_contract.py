from __future__ import annotations

import json
import os
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
def test_destination_created_during_publication_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    source = tmp_path / f"private-{command}-source.sqlite3"
    destination = tmp_path / f"private-{command}-destination.sqlite3"
    _initialize_database(source)
    source_before = source.read_bytes()
    competing_content = b"created-by-competing-publisher"
    temporary_paths: list[Path] = []
    publication_attempts: list[tuple[Path, Path]] = []

    def publish_race(temporary_path: str | Path, destination_path: str | Path) -> None:
        temporary = Path(temporary_path)
        attempted_destination = Path(destination_path)
        assert temporary.is_file()
        assert temporary.name.endswith(".partial")
        assert attempted_destination == destination.resolve()
        assert not attempted_destination.exists()
        temporary_paths.append(temporary)
        publication_attempts.append((temporary, attempted_destination))

        # Simulate another publisher winning after the preflight check but
        # immediately before this operation's atomic no-overwrite publication.
        attempted_destination.write_bytes(competing_content)
        raise FileExistsError(
            f"destination was published concurrently: {attempted_destination}"
        )

    monkeypatch.setattr(os, "link", publish_race)

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
        "error": {"code": "destination_exists", "type": "FileExistsError"},
        "exit_code": 1,
    }
    assert str(destination) not in captured.out
    assert captured.err.startswith("ERROR: refusing to overwrite existing destination:")
    assert "[absolute path]" in captured.err
    assert str(destination) not in captured.err
    assert "traceback" not in captured.err.lower()
    assert source.is_file()
    assert source.read_bytes() == source_before
    assert destination.is_file()
    assert destination.read_bytes() == competing_content
    assert len(publication_attempts) == 1
    assert len(temporary_paths) == 1
    assert not temporary_paths[0].exists()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial"))
