from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops


class _FakeConnection:
    def __init__(
        self,
        *,
        backup_error: sqlite3.Error | None = None,
        close_error: Exception,
    ) -> None:
        self.backup_error = backup_error
        self.close_error = close_error
        self.close_calls = 0
        self.execute_calls: list[str] = []
        self.backup_calls: list[tuple[object, int, float]] = []

    def execute(self, statement: str) -> None:
        self.execute_calls.append(statement)

    def backup(self, destination: object, *, pages: int, sleep: float) -> None:
        self.backup_calls.append((destination, pages, sleep))
        if self.backup_error is not None:
            raise self.backup_error

    def close(self) -> None:
        self.close_calls += 1
        raise self.close_error


def _patch_connect(
    monkeypatch: pytest.MonkeyPatch,
    source: Path,
    temporary: Path,
    source_connection: _FakeConnection,
    destination_connection: _FakeConnection,
) -> None:
    calls: list[object] = []

    def fake_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        assert args
        requested = args[0]
        assert kwargs.get("timeout") == 2.0
        assert kwargs.get("isolation_level") is None
        calls.append(requested)
        if isinstance(requested, str) and requested == f"{source.as_uri()}?mode=ro":
            assert len(calls) == 1
            return cast(sqlite3.Connection, source_connection)
        assert requested == temporary
        assert len(calls) == 2
        return cast(sqlite3.Connection, destination_connection)

    monkeypatch.setattr(sqlite3, "connect", fake_connect)


def test_primary_online_backup_failure_survives_both_connection_close_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.sqlite3"
    temporary = tmp_path / ".destination.sqlite3.snapshot.partial"
    backup_error = sqlite3.OperationalError("injected online backup failure")
    source_close_error = PermissionError("injected source connection close failure")
    destination_close_error = PermissionError(
        "injected destination connection close failure"
    )
    source_connection = _FakeConnection(
        backup_error=backup_error,
        close_error=source_close_error,
    )
    destination_connection = _FakeConnection(close_error=destination_close_error)
    _patch_connect(
        monkeypatch,
        source,
        temporary,
        source_connection,
        destination_connection,
    )

    with pytest.raises(
        replay_ops.PersistentReplayReadinessError,
        match=r"SQLite online backup failed from source\.sqlite3: injected online backup failure",
    ) as exc_info:
        replay_ops._backup_to_temporary(source, temporary, timeout_seconds=2.0)

    assert exc_info.value.__cause__ is backup_error
    assert source_connection.close_calls == 1
    assert destination_connection.close_calls == 1
    assert len(source_connection.backup_calls) == 1
    assert source_connection.backup_calls[0][0] is destination_connection
    assert source_connection.backup_calls[0][1:] == (256, 0.05)
    assert destination_connection.execute_calls == ["PRAGMA busy_timeout = 2000"]
    assert len(exc_info.value.__notes__) == 1
    note = exc_info.value.__notes__[0]
    assert "connection cleanup was incomplete (2 item(s))" in note
    assert str(destination_close_error) in note
    assert str(source_close_error) in note
    assert not temporary.exists()


def test_successful_online_backup_reports_both_connection_close_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.sqlite3"
    temporary = tmp_path / ".destination.sqlite3.snapshot.partial"
    source_close_error = PermissionError("injected source connection close failure")
    destination_close_error = PermissionError(
        "injected destination connection close failure"
    )
    source_connection = _FakeConnection(close_error=source_close_error)
    destination_connection = _FakeConnection(close_error=destination_close_error)
    _patch_connect(
        monkeypatch,
        source,
        temporary,
        source_connection,
        destination_connection,
    )

    with pytest.raises(
        replay_ops.PersistentReplayReadinessError,
        match=r"SQLite snapshot connection cleanup was incomplete \(2 item\(s\)\)",
    ) as exc_info:
        replay_ops._backup_to_temporary(source, temporary, timeout_seconds=2.0)

    assert exc_info.value.__cause__ is destination_close_error
    assert source_connection.close_calls == 1
    assert destination_connection.close_calls == 1
    assert len(source_connection.backup_calls) == 1
    assert source_connection.backup_calls[0][0] is destination_connection
    assert source_connection.backup_calls[0][1:] == (256, 0.05)
    assert "injected destination connection close failure" in str(exc_info.value)
    assert "injected source connection close failure" in str(exc_info.value)
    assert not temporary.exists()
