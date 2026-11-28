from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_source_preflight_and_snapshot_share_the_exact_sqlite_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    source = tmp_path / f"pinned-source-{command}.sqlite3"
    decoy = tmp_path / f"different-valid-database-{command}.sqlite3"
    destination = tmp_path / f"pinned-destination-{command}.sqlite3"
    _initialize_database(source)
    _initialize_database(decoy)

    SQLiteReplayClaimStore(source).claim(
        f"learning-cycle:part11-62-source-{command}",
        "sha256:part11-62-source-input",
        lease_seconds=3600.0,
    )
    SQLiteReplayClaimStore(decoy).claim(
        f"learning-cycle:part11-62-decoy-one-{command}",
        "sha256:part11-62-decoy-one",
        lease_seconds=3600.0,
    )
    SQLiteReplayClaimStore(decoy).claim(
        f"learning-cycle:part11-62-decoy-two-{command}",
        "sha256:part11-62-decoy-two",
        lease_seconds=3600.0,
    )
    assert replay_ops.check_database(source).replay_claim_count == 1
    assert replay_ops.check_database(decoy).replay_claim_count == 2

    source_check_connections: list[sqlite3.Connection] = []
    source_backup_connections: list[sqlite3.Connection] = []
    original_check_database = replay_ops.check_database
    original_backup = replay_ops._backup_to_temporary

    def record_check(
        database_path: str | Path,
        *,
        timeout_seconds: float = 5.0,
        _connection: sqlite3.Connection | None = None,
    ) -> replay_ops.DatabaseReadinessReport:
        if Path(database_path).resolve() == source.resolve():
            assert _connection is not None
            source_check_connections.append(_connection)
        return original_check_database(
            database_path,
            timeout_seconds=timeout_seconds,
            _connection=_connection,
        )

    def record_backup(
        source_path: Path,
        temporary_path: Path,
        *,
        timeout_seconds: float,
        source_connection: sqlite3.Connection | None = None,
    ) -> None:
        assert source_path == source.resolve()
        assert source_connection is not None
        assert len(source_check_connections) == 1
        assert source_connection is source_check_connections[0]
        assert not source_connection.in_transaction
        source_backup_connections.append(source_connection)
        original_backup(
            source_path,
            temporary_path,
            timeout_seconds=timeout_seconds,
            source_connection=source_connection,
        )

    monkeypatch.setattr(replay_ops, "check_database", record_check)
    monkeypatch.setattr(replay_ops, "_backup_to_temporary", record_backup)

    if command == "backup":
        arguments = [
            "backup",
            "--database",
            str(source),
            "--destination",
            str(destination),
            "--json",
        ]
    else:
        arguments = [
            "restore",
            "--backup",
            str(source),
            "--destination",
            str(destination),
            "--json",
        ]

    exit_code = replay_ops.main(arguments)
    captured = capsys.readouterr()

    assert exit_code == 0, captured.err
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    report = _read_report(captured.out)
    assert report["action"] == command
    assert report["integrity_status"] == "pass"
    assert report["replay_claims"] == 1
    assert report["exit_code"] == 0
    assert len(source_check_connections) == 1
    assert len(source_backup_connections) == 1
    assert source_backup_connections[0] is source_check_connections[0]

    destination_report = original_check_database(destination)
    assert destination_report.replay_claim_count == 1
    assert destination_report.evidence_count == 0
    assert destination.is_file()
    assert source.is_file()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))
