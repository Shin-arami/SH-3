from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


class _FailingCloseSourceConnection(sqlite3.Connection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        super().close()
        raise sqlite3.OperationalError(
            "injected read-only source connection close failure"
        )


def _initialize_database(database: Path, suffix: str) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database).claim(
        f"learning-cycle:part11-140-{suffix}",
        f"sha256:part11-140-{suffix}",
        lease_seconds=3600.0,
    )


def _capture_artifacts(databases: tuple[Path, ...]) -> dict[Path, bytes | None]:
    expected: dict[Path, bytes | None] = {}
    for database in databases:
        for suffix in ("", "-wal", "-shm", "-journal"):
            artifact = database if not suffix else Path(f"{database}{suffix}")
            expected[artifact] = artifact.read_bytes() if artifact.is_file() else None
    return expected


def _assert_artifacts_unchanged(expected: dict[Path, bytes | None]) -> None:
    for artifact, expected_bytes in expected.items():
        if expected_bytes is None:
            assert not artifact.exists()
        else:
            assert artifact.is_file()
            assert artifact.read_bytes() == expected_bytes


def _matching_partials(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            item.name
            for item in directory.iterdir()
            if item.name.startswith(prefix) and ".partial" in item.name
        )
    )


def _publish(
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
def test_source_close_and_partial_cleanup_failures_preserve_identity_error_and_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"source-close-cleanup-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"source-close-cleanup-{scenario}-backup.sqlite3"
    destination = tmp_path / f"source-close-cleanup-{scenario}-destination.sqlite3"
    _initialize_database(source, scenario)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases: tuple[Path, ...] = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_artifacts = _capture_artifacts(protected_databases)
    original_connect = sqlite3.connect
    original_identity = replay_ops._source_file_identity
    original_check_database = replay_ops.check_database
    original_link = os.link
    original_unlink = Path.unlink
    source_connections: list[_FailingCloseSourceConnection] = []
    temporary_paths: list[Path] = []
    snapshot_verified = False
    publication_attempts: list[tuple[Path, Path]] = []
    cleanup_attempts: list[Path] = []
    cleanup_failure_injected = False

    def tracked_connect(
        database: Any,
        *args: Any,
        **kwargs: Any,
    ) -> sqlite3.Connection:
        if (
            isinstance(database, str)
            and database == f"{input_database.as_uri()}?mode=ro"
        ):
            kwargs["factory"] = _FailingCloseSourceConnection
            connection = original_connect(database, *args, **kwargs)
            assert isinstance(connection, _FailingCloseSourceConnection)
            source_connections.append(connection)
            return connection
        return cast(sqlite3.Connection, original_connect(database, *args, **kwargs))

    def drift_identity(path: Path) -> tuple[int, int]:
        identity = original_identity(path)
        if snapshot_verified and path.resolve() == input_database.resolve():
            return identity[0], identity[1] + 1
        return identity

    def record_snapshot_verification(
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
        candidate = Path(database_path).resolve()
        if (
            _connection is None
            and candidate.parent == tmp_path.resolve()
            and candidate.name.startswith(f".{destination.name}.")
            and candidate.name.endswith(".partial")
        ):
            temporary_paths.append(candidate)
            snapshot_verified = True
        return report

    def fail_temporary_unlink(path: Path, missing_ok: bool = False) -> None:
        nonlocal cleanup_failure_injected
        cleanup_attempts.append(path)
        if (
            temporary_paths
            and path == temporary_paths[0]
            and not cleanup_failure_injected
        ):
            cleanup_failure_injected = True
            raise PermissionError("injected temporary snapshot cleanup failure")
        original_unlink(path, missing_ok=missing_ok)

    def record_publication(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        publication_attempts.append((Path(source_path), Path(destination_path)))
        original_link(source_path, destination_path)

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", tracked_connect)
        patch.setattr(replay_ops, "_source_file_identity", drift_identity)
        patch.setattr(replay_ops, "check_database", record_snapshot_verification)
        patch.setattr(Path, "unlink", fail_temporary_unlink)
        patch.setattr(os, "link", record_publication)
        with pytest.raises(
            replay_ops.PersistentReplayReadinessError,
            match="source database file identity changed before snapshot publication",
        ) as exc_info:
            _publish(scenario, input_database, destination)

    assert snapshot_verified
    assert len(source_connections) == 1
    assert source_connections[0].close_calls == 1
    assert len(temporary_paths) == 1
    temporary = temporary_paths[0]
    assert cleanup_failure_injected
    assert cleanup_attempts.count(temporary) == 1
    assert len(exc_info.value.__notes__) == 2
    cleanup_note, source_close_note = exc_info.value.__notes__
    assert "temporary snapshot cleanup was incomplete (1 item(s))" in cleanup_note
    assert (
        "inspect matching .partial files and SQLite sidecars before retrying"
        in cleanup_note
    )
    assert "read-only source connection cleanup failed" in source_close_note
    assert "injected read-only source connection close failure" in source_close_note
    assert publication_attempts == []
    assert not destination.exists()
    assert temporary.is_file()
    assert _matching_partials(tmp_path, destination) == (temporary.name,)
    _assert_artifacts_unchanged(protected_artifacts)

    # Reclaim the sole orphan after the injected failures have been disabled.
    original_unlink(temporary, missing_ok=True)
    assert not temporary.exists()
    assert _matching_partials(tmp_path, destination) == ()
    _assert_artifacts_unchanged(protected_artifacts)

    retry_report = _publish(scenario, input_database, destination)
    checked_destination = replay_ops.check_database(destination)
    assert retry_report.database_path == destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert checked_destination.evidence_count == input_report.evidence_count
    assert checked_destination.replay_claim_count == input_report.replay_claim_count
    assert destination.is_file()
    assert _matching_partials(tmp_path, destination) == ()
    _assert_artifacts_unchanged(protected_artifacts)
