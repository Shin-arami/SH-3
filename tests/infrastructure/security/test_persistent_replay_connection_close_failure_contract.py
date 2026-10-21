from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops


@pytest.mark.parametrize("ownership", ("owned", "borrowed"), ids=("owned-source", "borrowed-source"))
def test_source_connection_ownership_survives_destination_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ownership: str,
) -> None:
    source = tmp_path / f"source-{ownership}.sqlite3"
    snapshot = tmp_path / f"snapshot-{ownership}.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (value INTEGER NOT NULL)")
        connection.execute("INSERT INTO sample (value) VALUES (42)")

    original_connect = sqlite3.connect
    source_connections: list[sqlite3.Connection] = []

    class TrackingSourceConnection(sqlite3.Connection):
        def close(self) -> None:
            source_connections.append(self)
            super().close()

    class FailingCloseDestinationConnection(sqlite3.Connection):
        def close(self) -> None:
            super().close()
            raise sqlite3.OperationalError("injected destination close failure")

    def tracked_connect(
        database: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> sqlite3.Connection:
        if not kwargs.get("uri", False) and Path(database) == snapshot:
            kwargs["factory"] = FailingCloseDestinationConnection
        elif kwargs.get("uri", False) and "mode=ro" in str(database):
            kwargs["factory"] = TrackingSourceConnection
        return cast(sqlite3.Connection, original_connect(database, *args, **kwargs))

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)

    borrowed_connection: sqlite3.Connection | None = None
    if ownership == "borrowed":
        borrowed_connection = original_connect(
            f"{source.as_uri()}?mode=ro",
            uri=True,
            timeout=1.0,
            isolation_level=None,
            factory=TrackingSourceConnection,
        )

    with pytest.raises(sqlite3.OperationalError, match="injected destination close failure"):
        replay_ops._backup_to_temporary(
            source,
            snapshot,
            timeout_seconds=1.0,
            source_connection=borrowed_connection,
        )

    if ownership == "owned":
        assert len(source_connections) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            source_connections[0].execute("SELECT 1")
    else:
        assert borrowed_connection is not None
        assert source_connections == []
        result = borrowed_connection.execute("SELECT value FROM sample").fetchone()
        assert result is not None
        assert result[0] == 42
        borrowed_connection.close()
        assert source_connections == [borrowed_connection]

    assert source.is_file()
    assert snapshot.is_file()
