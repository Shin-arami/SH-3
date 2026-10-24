from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops


@pytest.mark.parametrize(
    "source_close_fails",
    (False, True),
    ids=("source-close-succeeds", "source-close-fails"),
)
def test_owned_source_busy_timeout_failure_preserves_primary_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_close_fails: bool,
) -> None:
    source = tmp_path / "source.sqlite3"
    temporary = tmp_path / ".snapshot.sqlite3.partial"
    source_uri = f"{source.as_uri()}?mode=ro"
    configuration_error = sqlite3.OperationalError(
        "injected source busy_timeout configuration failure"
    )
    close_error = sqlite3.OperationalError("injected owned source close failure")
    setup_connection = sqlite3.connect(source)
    try:
        setup_connection.execute("CREATE TABLE sample (value INTEGER NOT NULL)")
        setup_connection.execute("INSERT INTO sample (value) VALUES (42)")
    finally:
        setup_connection.close()
    source_bytes = source.read_bytes()

    original_connect = sqlite3.connect
    connection_requests: list[object] = []
    execute_calls: list[str] = []
    source_connections: list[sqlite3.Connection] = []
    close_attempts: list[sqlite3.Connection] = []

    class FailingSourceConfigurationConnection(sqlite3.Connection):
        def execute(
            self,
            sql: str,
            parameters: Any = (),
            /,
        ) -> sqlite3.Cursor:
            execute_calls.append(sql)
            if sql.casefold().startswith("pragma busy_timeout"):
                raise configuration_error
            return super().execute(sql, parameters)

        def close(self) -> None:
            close_attempts.append(self)
            super().close()
            if source_close_fails:
                raise close_error

    def tracked_connect(
        database: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> sqlite3.Connection:
        connection_requests.append(database)
        if isinstance(database, str) and database == source_uri:
            kwargs["factory"] = FailingSourceConfigurationConnection
            connection = cast(
                sqlite3.Connection,
                original_connect(database, *args, **kwargs),
            )
            source_connections.append(connection)
            return connection
        if isinstance(database, Path) and database == temporary:
            raise AssertionError("destination connection must not be opened")
        return cast(sqlite3.Connection, original_connect(database, *args, **kwargs))

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)

    with pytest.raises(
        replay_ops.PersistentReplayReadinessError,
        match=(
            r"SQLite online backup failed from source\.sqlite3: "
            r"injected source busy_timeout configuration failure"
        ),
    ) as exc_info:
        replay_ops._backup_to_temporary(
            source,
            temporary,
            timeout_seconds=2.0,
        )

    assert isinstance(exc_info.value.__cause__, sqlite3.OperationalError)
    assert exc_info.value.__cause__ is configuration_error
    assert connection_requests == [source_uri]
    assert execute_calls == ["PRAGMA busy_timeout = 2000"]
    assert len(source_connections) == 1
    assert close_attempts == source_connections
    assert not temporary.exists()
    assert source.read_bytes() == source_bytes
    notes = getattr(exc_info.value, "__notes__", [])
    if source_close_fails:
        assert len(notes) == 1
        assert "connection cleanup was incomplete (1 item(s))" in notes[0]
        assert str(close_error) in notes[0]
    else:
        assert notes == []
