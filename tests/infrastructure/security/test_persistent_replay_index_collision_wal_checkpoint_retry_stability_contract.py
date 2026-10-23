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

_REQUIRED_INDEX = "sh3_replay_claims_state_idx"
_SAVEPOINT = "part11_104_collision_scope"
_COLLISION_ATTEMPTS = 3
_MAX_USER_VERSION = 2_147_483_647
_MODE_ORDERS: tuple[tuple[str, ...], ...] = (
    ("PASSIVE", "FULL", "RESTART", "TRUNCATE"),
    ("TRUNCATE", "RESTART", "FULL", "PASSIVE"),
    ("FULL", "TRUNCATE", "PASSIVE", "RESTART"),
)


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _prepare_destination(
    source: Path,
    backup: Path,
    destination: Path,
    *,
    scenario: str,
) -> tuple[Path, ...]:
    if scenario == "backup-destination":
        replay_ops.backup_database(source, destination)
        return (source,)
    replay_ops.backup_database(source, backup)
    replay_ops.restore_database(backup, destination)
    return (source, backup)


def _set_wal_mode(database: Path) -> None:
    connection = sqlite3.connect(database, timeout=0.0, isolation_level=None)
    try:
        row = connection.execute("PRAGMA journal_mode = WAL").fetchone()
        assert row is not None
        assert str(row[0]).casefold() == "wal"
    finally:
        connection.close()


def _read_user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    assert row is not None
    return int(row[0])


def _read_user_version_from_database(database: Path) -> int:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
        timeout=0.0,
        isolation_level=None,
    )
    try:
        return _read_user_version(connection)
    finally:
        connection.close()


def _has_index(connection: sqlite3.Connection, index_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        is not None
    )


def _has_index_from_database(database: Path, index_name: str) -> bool:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
        timeout=0.0,
        isolation_level=None,
    )
    try:
        return _has_index(connection, index_name)
    finally:
        connection.close()


def _claim_state_index_definition_from_connection(
    connection: sqlite3.Connection,
) -> tuple[str, bool, bool, tuple[str, ...]]:
    owner_row = connection.execute(
        "SELECT tbl_name FROM sqlite_master "
        "WHERE type = 'index' AND name = ? COLLATE NOCASE",
        (_REQUIRED_INDEX,),
    ).fetchone()
    assert owner_row is not None
    index_row = next(
        row
        for row in connection.execute(
            "PRAGMA index_list(sh3_replay_claims)"
        ).fetchall()
        if str(row[1]).casefold() == _REQUIRED_INDEX.casefold()
    )
    columns = connection.execute(
        f"PRAGMA index_info({_REQUIRED_INDEX})"
    ).fetchall()
    return (
        str(owner_row[0]),
        bool(index_row[2]),
        bool(index_row[4]),
        tuple(str(row[2]) for row in columns),
    )


def _claim_state_index_definition(
    database: Path,
) -> tuple[str, bool, bool, tuple[str, ...]]:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
        timeout=0.0,
        isolation_level=None,
    )
    try:
        return _claim_state_index_definition_from_connection(connection)
    finally:
        connection.close()


def _residual_artifact_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _assert_collision_retries(
    connection: sqlite3.Connection,
    *,
    marker: int,
    inner_marker: int,
    probe_index: str,
    claim_count: int,
    canonical_definition: tuple[str, bool, bool, tuple[str, ...]],
) -> None:
    messages: list[str] = []
    for _ in range(_COLLISION_ATTEMPTS):
        connection.execute(f"SAVEPOINT {_SAVEPOINT}")
        connection.execute(f"PRAGMA user_version = {inner_marker}")
        with pytest.raises(
            sqlite3.OperationalError,
            match="already exists",
        ) as collision_error:
            connection.execute(
                f"CREATE INDEX {_REQUIRED_INDEX} "
                "ON sh3_replay_claims(lease_expires_at, state)"
            )
        messages.append(str(collision_error.value))
        assert connection.in_transaction
        assert _read_user_version(connection) == inner_marker
        connection.execute(f"ROLLBACK TO SAVEPOINT {_SAVEPOINT}")
        connection.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
        assert connection.in_transaction
        assert _read_user_version(connection) == marker
        assert _has_index(connection, probe_index)
        assert (
            _claim_state_index_definition_from_connection(connection)
            == canonical_definition
        )
        claim_row = connection.execute(
            "SELECT COUNT(*) FROM sh3_replay_claims"
        ).fetchone()
        assert claim_row is not None
        assert int(claim_row[0]) == claim_count
    assert len(messages) == _COLLISION_ATTEMPTS
    assert len(set(messages)) == 1


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_completed_wal_checkpoint_modes_remain_stable_across_retry_orders(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"checkpoint-retry-stability-{scenario}-source.sqlite3"
    backup = tmp_path / f"checkpoint-retry-stability-{scenario}-backup.sqlite3"
    destination = (
        tmp_path / f"checkpoint-retry-stability-{scenario}-destination.sqlite3"
    )
    _initialize_database(source)
    protected_sources = _prepare_destination(
        source,
        backup,
        destination,
        scenario=scenario,
    )
    protected_source_bytes = {
        path: path.read_bytes() for path in protected_sources
    }
    _set_wal_mode(destination)

    readiness = replay_ops.check_database(destination)
    assert readiness.journal_mode.casefold() == "wal"
    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    assert _claim_state_index_definition(destination) == canonical_definition
    original_marker = _read_user_version_from_database(destination)
    claim_count = readiness.replay_claim_count

    temporary_main = (
        tmp_path / f".{destination.name}.part11-104-checkpoint-retry.partial"
    )
    residual_contents = {
        temporary_main: b"part11-104 checkpoint-retry partial snapshot",
        Path(f"{temporary_main}-wal"): b"part11-104 checkpoint-retry WAL residue",
        Path(f"{temporary_main}-shm"): b"part11-104 checkpoint-retry SHM residue",
        Path(f"{temporary_main}-journal"): (
            b"part11-104 checkpoint-retry journal residue"
        ),
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    completed_modes: list[tuple[int, str, tuple[int, int, int]]] = []
    expected_markers = {original_marker}
    writer = sqlite3.connect(destination, timeout=0.0, isolation_level=None)
    try:
        epoch_number = 0
        for mode_order in _MODE_ORDERS:
            for mode in mode_order:
                epoch_number += 1
                probe_index = (
                    f"sh3_replay_claims_part11_104_epoch_{epoch_number:02d}_idx"
                )
                marker = (
                    original_marker + 104_000 + epoch_number * 101
                ) % _MAX_USER_VERSION
                inner_marker = (marker + 104_999) % _MAX_USER_VERSION
                assert marker != original_marker
                assert inner_marker != marker
                assert marker not in expected_markers
                expected_markers.add(marker)

                writer.execute("BEGIN IMMEDIATE")
                writer.execute(f"PRAGMA user_version = {marker}")
                writer.execute(
                    f"CREATE INDEX {probe_index} "
                    "ON sh3_replay_claims(lease_expires_at)"
                )
                assert writer.in_transaction
                assert _read_user_version(writer) == marker
                assert _has_index(writer, probe_index)
                _assert_collision_retries(
                    writer,
                    marker=marker,
                    inner_marker=inner_marker,
                    probe_index=probe_index,
                    claim_count=claim_count,
                    canonical_definition=canonical_definition,
                )
                writer.execute("COMMIT")
                assert not writer.in_transaction
                assert _read_user_version(writer) == marker

                result = writer.execute(
                    f"PRAGMA wal_checkpoint({mode})"
                ).fetchone()
                assert result is not None
                assert len(result) == 3
                busy, log_frames, checkpointed_frames = (
                    int(value) for value in result
                )
                assert busy == 0
                if mode == "TRUNCATE":
                    assert (busy, log_frames, checkpointed_frames) == (0, 0, 0)
                else:
                    assert log_frames > 0
                    assert checkpointed_frames == log_frames
                assert _read_user_version(writer) == marker
                assert _has_index(writer, probe_index)
                assert (
                    _claim_state_index_definition_from_connection(writer)
                    == canonical_definition
                )
                completed_modes.append(
                    (epoch_number, mode, (busy, log_frames, checkpointed_frames))
                )

        assert len(completed_modes) == 12
        assert tuple(mode for _, mode, _ in completed_modes[:4]) == _MODE_ORDERS[0]
        assert tuple(mode for _, mode, _ in completed_modes[4:8]) == _MODE_ORDERS[1]
        assert tuple(mode for _, mode, _ in completed_modes[8:]) == _MODE_ORDERS[2]
        assert all(result[0] == 0 for _, _, result in completed_modes)
        assert all(
            result == (0, 0, 0)
            for _, mode, result in completed_modes
            if mode == "TRUNCATE"
        )
        final_marker = (original_marker + 104_000 + 12 * 101) % _MAX_USER_VERSION
        assert _read_user_version(writer) == final_marker
        for epoch_number in range(1, 13):
            assert _has_index(
                writer,
                f"sh3_replay_claims_part11_104_epoch_{epoch_number:02d}_idx",
            )
        final_checkpoint = writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        assert final_checkpoint is not None
        assert tuple(int(value) for value in final_checkpoint) == (0, 0, 0)
    finally:
        if writer.in_transaction:
            writer.execute("ROLLBACK")
        writer.close()

    assert _read_user_version_from_database(destination) == final_marker
    assert _claim_state_index_definition(destination) == canonical_definition
    for epoch_number in range(1, 13):
        assert _has_index_from_database(
            destination,
            f"sh3_replay_claims_part11_104_epoch_{epoch_number:02d}_idx",
        )
    committed_readiness = replay_ops.check_database(destination)
    assert committed_readiness == readiness
    destination_bytes_after_checkpoints = destination.read_bytes()
    assert _residual_artifact_names(tmp_path, destination) == residual_names_before
    for artifact, contents in residual_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents
    for protected_source in protected_sources:
        assert protected_source.read_bytes() == protected_source_bytes[protected_source]

    expected_report = {
        "schema_version": 1,
        "action": "check",
        "database": str(destination.resolve()),
        "sqlite_version": committed_readiness.sqlite_version,
        "journal_mode": committed_readiness.journal_mode,
        "integrity_status": "pass",
        "evidence_records": committed_readiness.evidence_count,
        "replay_claims": committed_readiness.replay_claim_count,
        "expired_claims": committed_readiness.expired_claim_count,
        "pending_evidence_reconciliation": (
            committed_readiness.pending_evidence_reconciliation_count
        ),
        "policy_gates": {},
        "exit_code": 0,
    }
    reports: list[dict[str, Any]] = []
    for _ in range(2):
        exit_code = replay_ops.main(
            ["check", "--database", str(destination), "--json"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.count("\n") == 1
        assert captured.err == ""
        report = _read_report(captured.out)
        assert report == expected_report
        assert _read_user_version_from_database(destination) == final_marker
        assert _claim_state_index_definition(destination) == canonical_definition
        assert destination.read_bytes() == destination_bytes_after_checkpoints
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        for protected_source in protected_sources:
            assert (
                protected_source.read_bytes()
                == protected_source_bytes[protected_source]
            )
        reports.append(report)

    assert reports[0] == reports[1]
