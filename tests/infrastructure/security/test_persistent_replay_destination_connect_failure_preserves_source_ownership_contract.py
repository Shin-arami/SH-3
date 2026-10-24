from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops


class _TrackingSourceConnection:
    def __init__(self, close_error: Exception) -> None:
        self.close_error = close_error
        self.close_calls = 0
        self.execute_calls: list[str] = []
        self.backup_calls: list[object] = []

    def execute(self, statement: str) -> None:
        self.execute_calls.append(statement)

    def backup(self, destination: object, *, pages: int, sleep: float) -> None:
        self.backup_calls.append(destination)
        raise AssertionError("online backup must not start when destination open fails")

    def close(self) -> None:
        self.close_calls += 1
        raise self.close_error


@pytest.mark.parametrize(
    "ownership", ("owned", "borrowed"), ids=("owned-source", "borrowed-source")
)
def test_destination_connection_open_failure_preserves_source_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ownership: str,
) -> None:
    source = tmp_path / "source.sqlite3"
    temporary = tmp_path / ".destination.sqlite3.snapshot.partial"
    source_close_error = PermissionError("injected source connection close failure")
    destination_open_error = sqlite3.OperationalError(
        "injected destination connection open failure"
    )
    source_connection = _TrackingSourceConnection(source_close_error)
    connection_requests: list[object] = []

    def fail_destination_connect(*args: object, **kwargs: Any) -> sqlite3.Connection:
        assert args
        requested = args[0]
        connection_requests.append(requested)
        if (
            ownership == "owned"
            and isinstance(requested, str)
            and requested == f"{source.as_uri()}?mode=ro"
        ):
            assert kwargs.get("uri") is True
            return cast(sqlite3.Connection, source_connection)
        assert requested == temporary
        raise destination_open_error

    monkeypatch.setattr(sqlite3, "connect", fail_destination_connect)
    borrowed_connection = (
        cast(sqlite3.Connection, source_connection)
        if ownership == "borrowed"
        else None
    )

    with pytest.raises(
        replay_ops.PersistentReplayReadinessError,
        match=(
            r"SQLite online backup failed from source\.sqlite3: "
            r"injected destination connection open failure"
        ),
    ) as exc_info:
        replay_ops._backup_to_temporary(
            source,
            temporary,
            timeout_seconds=2.0,
            source_connection=borrowed_connection,
        )

    assert exc_info.value.__cause__ is destination_open_error
    assert not temporary.exists()
    assert source_connection.backup_calls == []
    if ownership == "owned":
        assert connection_requests == [f"{source.as_uri()}?mode=ro", temporary]
        assert source_connection.execute_calls == ["PRAGMA busy_timeout = 2000"]
        assert source_connection.close_calls == 1
        assert len(exc_info.value.__notes__) == 1
        note = exc_info.value.__notes__[0]
        assert "connection cleanup was incomplete (1 item(s))" in note
        assert str(source_close_error) in note
    else:
        assert connection_requests == [temporary]
        assert source_connection.execute_calls == []
        assert source_connection.close_calls == 0
        assert getattr(exc_info.value, "__notes__", []) == []
