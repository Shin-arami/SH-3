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


def _arguments(command: str, source: Path, destination: Path) -> list[str]:
    if command == "backup":
        return [
            "backup",
            "--database",
            str(source),
            "--destination",
            str(destination),
            "--json",
        ]
    return [
        "restore",
        "--backup",
        str(source),
        "--destination",
        str(destination),
        "--json",
    ]


def _matching_residual_artifacts(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_existing_destination_refusal_preserves_all_preexisting_partial_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    source = tmp_path / f"residual-{command}-source.sqlite3"
    destination = tmp_path / f"residual-{command}-destination.sqlite3"
    _initialize_database(source)
    _initialize_database(destination)
    source_bytes_before = source.read_bytes()
    destination_bytes_before = destination.read_bytes()
    destination_report_before = replay_ops.check_database(destination)

    temporary_main = tmp_path / f".{destination.name}.part11-68-stale.partial"
    residual_contents = {
        temporary_main: b"stale temporary snapshot body",
        Path(f"{temporary_main}-wal"): b"stale WAL residue",
        Path(f"{temporary_main}-shm"): b"stale SHM residue",
        Path(f"{temporary_main}-journal"): b"stale journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)

    artifact_names_before = _matching_residual_artifacts(tmp_path, destination)
    assert artifact_names_before == tuple(sorted(path.name for path in residual_contents))

    exit_code = replay_ops.main(_arguments(command, source, destination))
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

    captured_text = captured.out + captured.err
    assert captured.err.startswith("ERROR: refusing to overwrite existing destination:")
    assert "[absolute path]" in captured.err
    assert str(source) not in captured_text
    assert str(destination) not in captured_text
    assert source.read_bytes() == source_bytes_before
    assert destination.read_bytes() == destination_bytes_before
    assert _matching_residual_artifacts(tmp_path, destination) == artifact_names_before

    for artifact, contents in residual_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents

    destination_report_after = replay_ops.check_database(destination)
    assert destination_report_after.evidence_count == destination_report_before.evidence_count
    assert (
        destination_report_after.replay_claim_count
        == destination_report_before.replay_claim_count
    )
