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
def test_cleanup_failure_during_snapshot_error_is_visible_without_masking_primary_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    source = tmp_path / f"private-{command}-source.sqlite3"
    destination = tmp_path / f"private-{command}-destination.sqlite3"
    _initialize_database(source)
    source_bytes = source.read_bytes()
    temporary_paths: list[Path] = []
    cleanup_attempts: list[Path] = []
    original_unlink = Path.unlink

    def inject_snapshot_failure(
        source_path: Path,
        temporary_path: Path,
        *,
        timeout_seconds: float,
        source_connection: Any = None,
    ) -> None:
        assert source_path == source.resolve()
        assert timeout_seconds > 0
        assert temporary_path.is_file()
        temporary_paths.append(temporary_path)
        Path(f"{temporary_path}-wal").write_text("injected residual sidecar", encoding="utf-8")
        raise replay_ops.PersistentReplayReadinessError(
            "injected primary snapshot failure"
        )

    def fail_wal_unlink(path: Path, missing_ok: bool = False) -> None:
        candidate = Path(path)
        cleanup_attempts.append(candidate)
        if temporary_paths and candidate == Path(f"{temporary_paths[0]}-wal"):
            raise PermissionError("injected sidecar cleanup denial")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(replay_ops, "_backup_to_temporary", inject_snapshot_failure)
    monkeypatch.setattr(Path, "unlink", fail_wal_unlink)
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
            "error": {
                "code": "readiness_check_failed",
                "type": "PersistentReplayReadinessError",
            },
            "exit_code": 1,
        }
        assert "ERROR: injected primary snapshot failure" in captured.err
        assert "DETAIL: temporary snapshot cleanup was incomplete (1 item(s))" in captured.err
        assert "inspect matching .partial files and SQLite sidecars" in captured.err
        assert str(source) not in captured.out + captured.err
        assert str(destination) not in captured.out + captured.err
        assert source.is_file()
        assert source.read_bytes() == source_bytes
        assert not destination.exists()
        assert len(temporary_paths) == 1
        assert Path(f"{temporary_paths[0]}-wal").read_text(encoding="utf-8") == (
            "injected residual sidecar"
        )
        assert not temporary_paths[0].exists()
        assert len(cleanup_attempts) == 4
        assert cleanup_attempts[-1] == temporary_paths[0]
    finally:
        if temporary_paths:
            original_unlink(Path(f"{temporary_paths[0]}-wal"), missing_ok=True)


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_post_publication_cleanup_failure_reports_ambiguous_success_and_preserves_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    source = tmp_path / f"private-{command}-source.sqlite3"
    destination = tmp_path / f"private-{command}-destination.sqlite3"
    _initialize_database(source)
    source_bytes = source.read_bytes()
    temporary_paths: list[Path] = []
    cleanup_attempts: list[Path] = []
    original_unlink = Path.unlink

    def fail_main_snapshot_unlink(path: Path, missing_ok: bool = False) -> None:
        candidate = Path(path)
        cleanup_attempts.append(candidate)
        if candidate.name.startswith(f".{destination.name}.") and candidate.name.endswith(
            ".partial"
        ):
            temporary_paths.append(candidate)
            raise PermissionError("injected temporary snapshot cleanup denial")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_main_snapshot_unlink)
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
        assert "verify the destination before retrying" in captured.err.lower()
        assert "inspect matching .partial files and SQLite sidecars" in captured.err
        assert str(source) not in captured.out + captured.err
        assert str(destination) not in captured.out + captured.err
        assert source.read_bytes() == source_bytes
        assert destination.is_file()
        assert len(temporary_paths) == 1
        assert temporary_paths[0].is_file()
        assert destination.samefile(temporary_paths[0])
        assert len(cleanup_attempts) == 4
        destination_report = replay_ops.check_database(destination)
        assert destination_report.evidence_count == 0
        assert destination_report.replay_claim_count == 0
    finally:
        for temporary in temporary_paths:
            original_unlink(temporary, missing_ok=True)
