from __future__ import annotations

import os
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


def _capture_database_artifacts(
    databases: tuple[Path, ...],
) -> dict[Path, bytes | None]:
    expected: dict[Path, bytes | None] = {}
    for database in databases:
        for artifact in (
            database,
            Path(f"{database}-wal"),
            Path(f"{database}-shm"),
            Path(f"{database}-journal"),
        ):
            expected[artifact] = artifact.read_bytes() if artifact.is_file() else None
    return expected


def _assert_database_artifacts_unchanged(
    expected: dict[Path, bytes | None],
) -> None:
    for artifact, expected_bytes in expected.items():
        if expected_bytes is None:
            assert not artifact.exists()
        else:
            assert artifact.is_file()
            assert artifact.read_bytes() == expected_bytes


def _partial_artifact_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_online_snapshot_failure_aggregates_multiple_cleanup_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"online-snapshot-failure-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"online-snapshot-failure-{scenario}-input.sqlite3"
    destination = tmp_path / f"online-snapshot-failure-{scenario}-destination.sqlite3"
    retry_destination = tmp_path / f"online-snapshot-failure-{scenario}-retry.sqlite3"
    _initialize_database(source)

    protected_databases: tuple[Path, ...]
    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_artifacts = _capture_database_artifacts(protected_databases)
    assert not destination.exists()

    def publish_snapshot(target: Path) -> replay_ops.DatabaseReadinessReport:
        if scenario == "backup-destination":
            return replay_ops.backup_database(input_database, target)
        return replay_ops.restore_database(input_database, target)

    temporary_paths: list[Path] = []
    cleanup_attempts: list[Path] = []
    injected_failure_paths: set[Path] = set()
    publication_attempts: list[tuple[Path, Path]] = []
    real_unlink = Path.unlink

    def fail_online_snapshot(
        source_path: Path,
        temporary_path: Path,
        *,
        timeout_seconds: float,
        source_connection: sqlite3.Connection | None = None,
    ) -> None:
        assert source_path == input_database.resolve()
        assert timeout_seconds > 0
        assert source_connection is not None
        assert not source_connection.in_transaction
        assert temporary_path.is_file()
        temporary_paths.append(temporary_path)
        wal_sidecar = Path(f"{temporary_path}-wal")
        journal_sidecar = Path(f"{temporary_path}-journal")
        wal_sidecar.write_bytes(b"injected temporary WAL sidecar")
        journal_sidecar.write_bytes(b"injected temporary journal sidecar")
        injected_failure_paths.update((wal_sidecar, temporary_path))
        raise replay_ops.PersistentReplayReadinessError(
            "injected primary online snapshot failure"
        )

    def fail_selected_unlinks(path: Path, missing_ok: bool = False) -> None:
        cleanup_attempts.append(path)
        if path in injected_failure_paths:
            raise PermissionError(f"injected unlink failure: {path.name}")
        real_unlink(path, missing_ok=missing_ok)

    def forbid_publication(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        publication_attempts.append((Path(source_path), Path(destination_path)))
        raise AssertionError("publication must not run after online snapshot failure")

    with monkeypatch.context() as patch:
        patch.setattr(replay_ops, "_backup_to_temporary", fail_online_snapshot)
        patch.setattr(Path, "unlink", fail_selected_unlinks)
        patch.setattr(os, "link", forbid_publication)
        with pytest.raises(
            replay_ops.PersistentReplayReadinessError,
            match="injected primary online snapshot failure",
        ) as exc_info:
            publish_snapshot(destination)

    assert len(temporary_paths) == 1
    temporary_snapshot = temporary_paths[0]
    wal_sidecar = Path(f"{temporary_snapshot}-wal")
    shm_sidecar = Path(f"{temporary_snapshot}-shm")
    journal_sidecar = Path(f"{temporary_snapshot}-journal")
    assert publication_attempts == []
    assert injected_failure_paths == {wal_sidecar, temporary_snapshot}
    assert cleanup_attempts == [
        wal_sidecar,
        shm_sidecar,
        journal_sidecar,
        temporary_snapshot,
    ]
    assert str(exc_info.value) == "injected primary online snapshot failure"
    assert exc_info.value.__cause__ is None
    assert len(exc_info.value.__notes__) == 1
    cleanup_note = exc_info.value.__notes__[0]
    assert "temporary snapshot cleanup was incomplete (2 item(s))" in cleanup_note
    assert "one or more temporary artifacts may remain" in cleanup_note
    assert "inspect matching .partial files and SQLite sidecars before retrying" in (
        cleanup_note
    )

    # Two failed cleanup targets remain, but the remaining cleanup attempts ran.
    assert temporary_snapshot.is_file()
    assert wal_sidecar.read_bytes() == b"injected temporary WAL sidecar"
    assert not shm_sidecar.exists()
    assert not journal_sidecar.exists()
    assert not destination.exists()
    assert _partial_artifact_names(tmp_path, destination) == tuple(
        sorted((temporary_snapshot.name, wal_sidecar.name))
    )
    _assert_database_artifacts_unchanged(protected_artifacts)

    # Recover only the intentionally orphaned temporary names, then retry.
    real_unlink(wal_sidecar, missing_ok=True)
    real_unlink(temporary_snapshot, missing_ok=True)
    assert _partial_artifact_names(tmp_path, destination) == ()
    assert not destination.exists()
    _assert_database_artifacts_unchanged(protected_artifacts)

    retry_report = publish_snapshot(retry_destination)
    checked_retry = replay_ops.check_database(retry_destination)
    assert retry_report.database_path == retry_destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert retry_report.expired_claim_count == input_report.expired_claim_count
    assert checked_retry.evidence_count == input_report.evidence_count
    assert checked_retry.replay_claim_count == input_report.replay_claim_count
    assert checked_retry.expired_claim_count == input_report.expired_claim_count
    assert not destination.exists()
    assert _partial_artifact_names(tmp_path, destination) == ()
    _assert_database_artifacts_unchanged(protected_artifacts)
