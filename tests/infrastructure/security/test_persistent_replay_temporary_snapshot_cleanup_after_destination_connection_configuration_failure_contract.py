from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

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
    artifacts: dict[Path, bytes | None] = {}
    for database in databases:
        for suffix in ("", "-wal", "-shm", "-journal"):
            artifact = Path(f"{database}{suffix}") if suffix else database
            artifacts[artifact] = artifact.read_bytes() if artifact.is_file() else None
    return artifacts


def _assert_database_artifacts_unchanged(
    expected: dict[Path, bytes | None],
) -> None:
    for artifact, expected_bytes in expected.items():
        if expected_bytes is None:
            assert not artifact.exists()
        else:
            assert artifact.is_file()
            assert artifact.read_bytes() == expected_bytes


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
def test_temporary_snapshot_cleanup_after_destination_connection_configuration_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"connect-config-{scenario}-source.sqlite3"
    backup = tmp_path / f"connect-config-{scenario}-backup.sqlite3"
    destination = tmp_path / f"connect-config-{scenario}-destination.sqlite3"
    _initialize_database(source)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup)
        input_database = backup
        protected_databases: tuple[Path, ...] = (source, backup)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_artifacts = _capture_database_artifacts(protected_databases)
    assert not destination.exists()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))

    original_connect = sqlite3.connect
    configuration_error = sqlite3.OperationalError(
        "injected destination busy_timeout configuration failure"
    )
    close_error = sqlite3.OperationalError(
        "injected destination connection close failure"
    )
    temporary_paths: list[Path] = []
    destination_connections: list[sqlite3.Connection] = []

    class FailingConfigurationConnection(sqlite3.Connection):
        def execute(
            self,
            sql: str,
            parameters: Any = (),
            /,
        ) -> sqlite3.Cursor:
            if sql.casefold().startswith("pragma busy_timeout"):
                raise configuration_error
            return super().execute(sql, parameters)

        def close(self) -> None:
            super().close()
            raise close_error

    def inject_destination_configuration_failure(
        database: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> sqlite3.Connection:
        if (
            isinstance(database, Path)
            and database.parent == tmp_path
            and database.name.startswith(f".{destination.name}.")
            and database.name.endswith(".partial")
        ):
            temporary_paths.append(database)
            kwargs["factory"] = FailingConfigurationConnection
            connection = cast(
                sqlite3.Connection,
                original_connect(database, *args, **kwargs),
            )
            destination_connections.append(connection)
            return connection
        return cast(sqlite3.Connection, original_connect(database, *args, **kwargs))

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", inject_destination_configuration_failure)
        with pytest.raises(
            replay_ops.PersistentReplayReadinessError,
            match=(
                r"SQLite online backup failed from .*: "
                r"injected destination busy_timeout configuration failure"
            ),
        ) as exc_info:
            _publish_snapshot(scenario, input_database, destination)

    assert exc_info.value.__cause__ is configuration_error
    assert len(destination_connections) == 1
    assert len(temporary_paths) == 1
    notes = getattr(exc_info.value, "__notes__", [])
    assert len(notes) == 1
    assert "connection cleanup was incomplete (1 item(s))" in notes[0]
    assert str(close_error) in notes[0]

    temporary = temporary_paths[0]
    assert not temporary.exists()
    assert not destination.exists()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))
    _assert_database_artifacts_unchanged(protected_artifacts)

    retry_report = _publish_snapshot(scenario, input_database, destination)
    destination_report = replay_ops.check_database(destination)
    assert retry_report.database_path == destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert retry_report.expired_claim_count == input_report.expired_claim_count
    assert destination_report.evidence_count == input_report.evidence_count
    assert destination_report.replay_claim_count == input_report.replay_claim_count
    assert destination_report.expired_claim_count == input_report.expired_claim_count
    assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))
    _assert_database_artifacts_unchanged(protected_artifacts)
