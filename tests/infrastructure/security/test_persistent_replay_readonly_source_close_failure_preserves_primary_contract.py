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
    close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        super().close()
        raise sqlite3.OperationalError(
            "injected read-only source connection close failure"
        )


def _initialize_database(database: Path, suffix: str) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database).claim(
        f"learning-cycle:part11-139-{suffix}",
        f"sha256:part11-139-{suffix}",
        lease_seconds=3600.0,
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
def test_source_close_failure_does_not_mask_prepublication_identity_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"source-close-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"source-close-{scenario}-backup.sqlite3"
    destination = tmp_path / f"source-close-{scenario}-destination.sqlite3"
    _initialize_database(source, scenario)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases: tuple[Path, ...] = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_bytes = {
        database: database.read_bytes() for database in protected_databases
    }
    original_identity = replay_ops._source_file_identity
    original_check_database = replay_ops.check_database
    original_connect = sqlite3.connect
    original_link = os.link
    source_connections: list[_FailingCloseSourceConnection] = []
    snapshot_verified = False
    publication_attempts: list[tuple[Path, Path]] = []

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
            snapshot_verified = True
        return report

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
        patch.setattr(os, "link", record_publication)
        with pytest.raises(
            replay_ops.PersistentReplayReadinessError,
            match="source database file identity changed before snapshot publication",
        ) as exc_info:
            _publish(scenario, input_database, destination)

    assert snapshot_verified
    assert len(source_connections) == 1
    assert source_connections[0].close_calls == 1
    assert len(exc_info.value.__notes__) == 1
    close_note = exc_info.value.__notes__[0]
    assert "read-only source connection cleanup failed" in close_note
    assert "injected read-only source connection close failure" in close_note
    assert publication_attempts == []
    assert not destination.exists()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))
    for database, expected_bytes in protected_bytes.items():
        assert database.read_bytes() == expected_bytes

    retry_report = _publish(scenario, input_database, destination)
    checked_destination = replay_ops.check_database(destination)
    assert retry_report.database_path == destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert checked_destination.evidence_count == input_report.evidence_count
    assert checked_destination.replay_claim_count == input_report.replay_claim_count
    assert destination.is_file()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))
    for database, expected_bytes in protected_bytes.items():
        assert database.read_bytes() == expected_bytes
