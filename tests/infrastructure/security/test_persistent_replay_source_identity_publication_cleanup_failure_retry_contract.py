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


def _capture_artifacts(databases: tuple[Path, ...]) -> dict[Path, bytes | None]:
    artifacts: dict[Path, bytes | None] = {}
    for database in databases:
        for path in (
            database,
            Path(f"{database}-wal"),
            Path(f"{database}-shm"),
            Path(f"{database}-journal"),
        ):
            artifacts[path] = path.read_bytes() if path.is_file() else None
    return artifacts


def _assert_artifacts_unchanged(expected: dict[Path, bytes | None]) -> None:
    for path, contents in expected.items():
        if contents is None:
            assert not path.exists()
        else:
            assert path.is_file()
            assert path.read_bytes() == contents


def _partial_artifact_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


def _publish_snapshot(
    scenario: str,
    input_database: Path,
    destination: Path,
) -> replay_ops.DatabaseReadinessReport:
    if scenario == "backup-destination":
        return replay_ops.backup_database(input_database, destination)
    return replay_ops.restore_database(input_database, destination)


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_prepublication_identity_drift_preserves_inputs_and_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"identity-publication-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"identity-publication-{scenario}-backup.sqlite3"
    destination = tmp_path / f"identity-publication-{scenario}-destination.sqlite3"
    _initialize_database(source)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases: tuple[Path, ...] = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_artifacts = _capture_artifacts(protected_databases)
    assert not destination.exists()

    original_identity = replay_ops._source_file_identity
    original_check_database = replay_ops.check_database
    original_backup = replay_ops._backup_to_temporary
    original_link = os.link
    original_unlink = Path.unlink
    temporary_paths: list[Path] = []
    cleanup_attempts: list[Path] = []
    publication_attempts: list[tuple[object, object]] = []
    injected_cleanup_paths: set[Path] = set()
    snapshot_verified = False

    def inject_source_identity_drift(path: Path) -> tuple[int, int]:
        identity = original_identity(path)
        if snapshot_verified and path.resolve() == input_database.resolve():
            return identity[0], identity[1] + 1
        return identity

    def record_backup(
        source_path: Path,
        temporary_path: Path,
        *,
        timeout_seconds: float,
        source_connection: sqlite3.Connection | None = None,
    ) -> None:
        temporary_paths.append(temporary_path)
        original_backup(
            source_path,
            temporary_path,
            timeout_seconds=timeout_seconds,
            source_connection=source_connection,
        )

    def record_verified_snapshot(
        database_path: str | os.PathLike[str],
        *,
        timeout_seconds: float = 5.0,
        _connection: sqlite3.Connection | None = None,
    ) -> replay_ops.DatabaseReadinessReport:
        nonlocal snapshot_verified
        report = original_check_database(
            database_path,
            timeout_seconds=timeout_seconds,
            _connection=_connection,
        )
        temporary_path = temporary_paths[0] if temporary_paths else None
        if (
            temporary_path is not None
            and Path(database_path).resolve() == temporary_path.resolve()
        ):
            snapshot_verified = True
            wal_sidecar = Path(f"{temporary_paths[0]}-wal")
            wal_sidecar.write_bytes(b"injected WAL residue before publication")
            injected_cleanup_paths.update((wal_sidecar, temporary_paths[0]))
        return report

    def record_publication(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        publication_attempts.append((source_path, destination_path))
        original_link(source_path, destination_path)

    def fail_selected_cleanup(path: Path, missing_ok: bool = False) -> None:
        candidate = Path(path)
        cleanup_attempts.append(candidate)
        if candidate in injected_cleanup_paths:
            raise PermissionError(f"injected cleanup failure: {candidate.name}")
        original_unlink(path, missing_ok=missing_ok)

    with monkeypatch.context() as patch:
        patch.setattr(replay_ops, "_source_file_identity", inject_source_identity_drift)
        patch.setattr(replay_ops, "_backup_to_temporary", record_backup)
        patch.setattr(replay_ops, "check_database", record_verified_snapshot)
        patch.setattr(os, "link", record_publication)
        patch.setattr(Path, "unlink", fail_selected_cleanup)
        with pytest.raises(
            replay_ops.PersistentReplayReadinessError,
            match="source database file identity changed before snapshot publication",
        ) as exc_info:
            _publish_snapshot(scenario, input_database, destination)

    assert snapshot_verified
    assert len(temporary_paths) == 1
    temporary_snapshot = temporary_paths[0]
    wal_sidecar = Path(f"{temporary_snapshot}-wal")
    expected_cleanup_order = (
        wal_sidecar,
        Path(f"{temporary_snapshot}-shm"),
        Path(f"{temporary_snapshot}-journal"),
        temporary_snapshot,
    )
    assert tuple(cleanup_attempts) == expected_cleanup_order
    assert injected_cleanup_paths == {wal_sidecar, temporary_snapshot}
    assert len(exc_info.value.__notes__) == 1
    cleanup_note = exc_info.value.__notes__[0]
    assert "temporary snapshot cleanup was incomplete (2 item(s))" in cleanup_note
    assert (
        "inspect matching .partial files and SQLite sidecars before retrying"
        in cleanup_note
    )
    assert publication_attempts == []
    assert not destination.exists()
    assert temporary_snapshot.is_file()
    assert wal_sidecar.read_bytes() == b"injected WAL residue before publication"
    assert _partial_artifact_names(tmp_path, destination) == tuple(
        sorted((temporary_snapshot.name, wal_sidecar.name))
    )
    _assert_artifacts_unchanged(protected_artifacts)

    original_unlink(wal_sidecar, missing_ok=True)
    original_unlink(temporary_snapshot, missing_ok=True)
    assert _partial_artifact_names(tmp_path, destination) == ()

    retry_report = _publish_snapshot(scenario, input_database, destination)
    checked_report = replay_ops.check_database(destination)
    assert retry_report.database_path == destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert checked_report.evidence_count == input_report.evidence_count
    assert checked_report.replay_claim_count == input_report.replay_claim_count
    assert destination.is_file()
    assert _partial_artifact_names(tmp_path, destination) == ()
    _assert_artifacts_unchanged(protected_artifacts)
