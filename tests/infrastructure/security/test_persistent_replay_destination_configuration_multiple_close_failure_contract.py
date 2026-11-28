from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops


@pytest.mark.parametrize(
    "ownership", ("owned", "borrowed"), ids=("owned-source", "borrowed-source")
)
def test_destination_configuration_failure_aggregates_both_close_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ownership: str,
) -> None:
    source = tmp_path / "source.sqlite3"
    temporary = tmp_path / ".snapshot.sqlite3.partial"
    configuration_error = sqlite3.OperationalError(
        "injected destination busy_timeout configuration failure"
    )
    destination_close_error = sqlite3.OperationalError(
        "injected destination connection close failure"
    )
    source_close_error = sqlite3.OperationalError(
        "injected owned source connection close failure"
    )
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (value INTEGER NOT NULL)")
        connection.execute("INSERT INTO sample (value) VALUES (42)")
    original_source_bytes = source.read_bytes()
    original_connect = sqlite3.connect
    source_uri = f"{source.as_uri()}?mode=ro"
    owned_source_connections: list[sqlite3.Connection] = []
    destination_connections: list[sqlite3.Connection] = []

    class FailingCloseOwnedSourceConnection(sqlite3.Connection):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            super().close()
            raise source_close_error

    class TrackingBorrowedSourceConnection(sqlite3.Connection):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            super().close()

    class FailingConfigurationDestinationConnection(sqlite3.Connection):
        close_calls = 0

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
            self.close_calls += 1
            super().close()
            raise destination_close_error

    borrowed_source: sqlite3.Connection | None = None
    if ownership == "borrowed":
        borrowed_source = cast(
            sqlite3.Connection,
            original_connect(
                source_uri,
                uri=True,
                timeout=2.0,
                isolation_level=None,
                factory=TrackingBorrowedSourceConnection,
            ),
        )

    def tracked_connect(
        database: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> sqlite3.Connection:
        is_owned_source = (
            ownership == "owned"
            and isinstance(database, str)
            and database == source_uri
        )
        if is_owned_source:
            kwargs["factory"] = FailingCloseOwnedSourceConnection
            connection = cast(
                sqlite3.Connection,
                original_connect(database, *args, **kwargs),
            )
            owned_source_connections.append(connection)
            return connection
        if isinstance(database, Path) and database == temporary:
            kwargs["factory"] = FailingConfigurationDestinationConnection
            connection = cast(
                sqlite3.Connection,
                original_connect(database, *args, **kwargs),
            )
            destination_connections.append(connection)
            return connection
        return cast(sqlite3.Connection, original_connect(database, *args, **kwargs))

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sqlite3, "connect", tracked_connect)
            with pytest.raises(
                replay_ops.PersistentReplayReadinessError,
                match=(
                    r"SQLite online backup failed from source\.sqlite3: "
                    r"injected destination busy_timeout configuration failure"
                ),
            ) as exc_info:
                replay_ops._backup_to_temporary(
                    source,
                    temporary,
                    timeout_seconds=2.0,
                    source_connection=borrowed_source,
                )

        assert exc_info.value.__cause__ is configuration_error
        assert len(destination_connections) == 1
        destination_connection = cast(
            FailingConfigurationDestinationConnection, destination_connections[0]
        )
        assert destination_connection.close_calls == 1
        notes = getattr(exc_info.value, "__notes__", [])
        assert len(notes) == 1
        note = notes[0]

        if ownership == "owned":
            assert len(owned_source_connections) == 1
            owned_connection = cast(
                FailingCloseOwnedSourceConnection, owned_source_connections[0]
            )
            assert owned_connection.close_calls == 1
            assert "connection cleanup was incomplete (2 item(s))" in note
            assert str(destination_close_error) in note
            assert str(source_close_error) in note
        else:
            assert owned_source_connections == []
            assert borrowed_source is not None
            borrowed_tracking = cast(TrackingBorrowedSourceConnection, borrowed_source)
            assert borrowed_tracking.close_calls == 0
            assert "connection cleanup was incomplete (1 item(s))" in note
            assert str(destination_close_error) in note
            assert str(source_close_error) not in note
            result = borrowed_source.execute("SELECT value FROM sample").fetchone()
            assert result == (42,)

        # The outer snapshot owner removes this temporary path after the helper fails.
        assert temporary.is_file()
        assert source.read_bytes() == original_source_bytes
    finally:
        if borrowed_source is not None:
            borrowed_source.close()
        temporary.unlink(missing_ok=True)
