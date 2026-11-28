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


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_post_publication_wal_sidecar_cleanup_failure_keeps_destination_and_removes_main_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    source = tmp_path / f"private-{command}-source.sqlite3"
    destination = tmp_path / f"private-{command}-destination.sqlite3"
    _initialize_database(source)
    source_bytes = source.read_bytes()
    cleanup_attempts: list[Path] = []
    residual_sidecars: list[Path] = []
    temporary_main_paths: list[Path] = []
    original_unlink = Path.unlink

    def fail_wal_sidecar_unlink(path: Path, missing_ok: bool = False) -> None:
        candidate = Path(path)
        is_temporary_cleanup = (
            candidate.parent == destination.parent
            and candidate.name.startswith(f".{destination.name}.")
            and ".partial" in candidate.name
        )
        if is_temporary_cleanup:
            cleanup_attempts.append(candidate)
            if candidate.name.endswith(".partial-wal") and not residual_sidecars:
                candidate.write_text("injected residual WAL sidecar", encoding="utf-8")
                residual_sidecars.append(candidate)
                raise PermissionError("injected WAL sidecar cleanup denial")
            if candidate.name.endswith(".partial"):
                temporary_main_paths.append(candidate)
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_wal_sidecar_unlink)
    try:
        exit_code = replay_ops.main(_arguments(command, source, destination))
        captured = capsys.readouterr()

        assert exit_code == 1
        assert captured.out.count("\n") == 1
        assert _read_report(captured.out) == {
            "schema_version": 1,
            "action": command,
            "integrity_status": "error",
            "policy_gates": {},
            "error": {"code": "operating_system_error", "type": "OSError"},
            "exit_code": 1,
        }
        assert "snapshot was published, but temporary cleanup was incomplete" in captured.err
        assert "(1 item(s))" in captured.err
        assert "one or more temporary artifacts may remain" in captured.err
        assert "verify the destination before retrying" in captured.err.lower()
        assert "inspect matching .partial files and SQLite sidecars" in captured.err
        assert str(source) not in captured.out + captured.err
        assert str(destination) not in captured.out + captured.err
        assert source.is_file()
        assert source.read_bytes() == source_bytes
        assert destination.is_file()
        assert len(residual_sidecars) == 1
        assert residual_sidecars[0].read_text(encoding="utf-8") == (
            "injected residual WAL sidecar"
        )
        assert len(cleanup_attempts) == 4
        assert cleanup_attempts[0].name.endswith(".partial-wal")
        assert cleanup_attempts[1].name.endswith(".partial-shm")
        assert cleanup_attempts[2].name.endswith(".partial-journal")
        assert cleanup_attempts[3].name.endswith(".partial")
        assert len(temporary_main_paths) == 1
        assert not temporary_main_paths[0].exists()

        destination_report = replay_ops.check_database(destination)
        assert destination_report.evidence_count == 0
        assert destination_report.replay_claim_count == 0
    finally:
        for sidecar in residual_sidecars:
            original_unlink(sidecar, missing_ok=True)
