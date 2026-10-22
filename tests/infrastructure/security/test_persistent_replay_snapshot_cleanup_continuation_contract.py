from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_sidecar_cleanup_failure_does_not_block_remaining_cleanup_or_mask_primary_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    source = tmp_path / f"cleanup-source-{command}.sqlite3"
    destination = tmp_path / f"cleanup-destination-{command}.sqlite3"
    _initialize_database(source)
    source_bytes_before = source.read_bytes()
    original_unlink = Path.unlink
    cleanup_attempts: list[str] = []
    injected_failure = False

    def inject_snapshot_failure(
        source_path: Path,
        temporary_path: Path,
        *,
        timeout_seconds: float,
        source_connection: sqlite3.Connection | None = None,
    ) -> None:
        assert source_path == source.resolve()
        assert timeout_seconds > 0
        assert source_connection is not None
        assert not source_connection.in_transaction
        assert temporary_path.is_file()
        raise replay_ops.PersistentReplayReadinessError(
            "injected primary online snapshot failure"
        )

    def track_unlink(path: Path, *, missing_ok: bool = False) -> None:
        nonlocal injected_failure
        is_temporary_cleanup = (
            path.parent == tmp_path
            and path.name.startswith(f".{destination.name}.")
            and ".partial" in path.name
        )
        if is_temporary_cleanup:
            cleanup_attempts.append(path.name)
            if path.name.endswith(".partial-wal") and not injected_failure:
                injected_failure = True
                raise PermissionError("injected WAL sidecar cleanup failure")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(replay_ops, "_backup_to_temporary", inject_snapshot_failure)
    monkeypatch.setattr(Path, "unlink", track_unlink)

    operation = (
        replay_ops.backup_database
        if command == "backup"
        else replay_ops.restore_database
    )
    with pytest.raises(
        replay_ops.PersistentReplayReadinessError,
        match="injected primary online snapshot failure",
    ) as exc_info:
        operation(source, destination)

    assert injected_failure
    assert len(cleanup_attempts) == 4
    assert cleanup_attempts[0].endswith(".partial-wal")
    assert cleanup_attempts[1].endswith(".partial-shm")
    assert cleanup_attempts[2].endswith(".partial-journal")
    assert cleanup_attempts[3].endswith(".partial")
    assert len(exc_info.value.__notes__) == 1
    cleanup_note = exc_info.value.__notes__[0]
    assert "temporary snapshot cleanup was incomplete (1 item(s))" in cleanup_note
    assert (
        "inspect matching .partial files and SQLite sidecars before retrying."
        in cleanup_note
    )

    assert source.is_file()
    assert source.read_bytes() == source_bytes_before
    assert not destination.exists()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))
