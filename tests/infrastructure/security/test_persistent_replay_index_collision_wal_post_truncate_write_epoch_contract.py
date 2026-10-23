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
_FIRST_EPOCH_INDEX = "sh3_replay_claims_part11_96_epoch_one_idx"
_SECOND_EPOCH_INDEX = "sh3_replay_claims_part11_96_epoch_two_idx"
_SAVEPOINT = "part11_96_collision_scope"
_COLLISION_ATTEMPTS = 3
_FIRST_MARKER_DELTA = 96_196
_FIRST_INNER_DELTA = 96_296
_SECOND_MARKER_DELTA = 96_396
_SECOND_INNER_DELTA = 96_496


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


def _run_write_epoch(
    connection: sqlite3.Connection,
    *,
    marker: int,
    inner_marker: int,
    probe_index: str,
    canonical_definition: tuple[str, bool, bool, tuple[str, ...]],
    claim_count: int,
) -> tuple[str, ...]:
    collision_messages: list[str] = []
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(f"PRAGMA user_version = {marker}")
    connection.execute(
        f"CREATE INDEX {probe_index} "
        "ON sh3_replay_claims(lease_expires_at)"
    )
    assert connection.in_transaction
    assert _read_user_version(connection) == marker
    assert _has_index(connection, probe_index)
    assert (
        _claim_state_index_definition_from_connection(connection)
        == canonical_definition
    )

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
        collision_messages.append(str(collision_error.value))
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

    assert len(collision_messages) == _COLLISION_ATTEMPTS
    assert len(set(collision_messages)) == 1
    connection.execute("COMMIT")
    assert not connection.in_transaction
    return tuple(collision_messages)


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_required_index_collision_remains_isolated_across_post_truncate_wal_epochs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"post-truncate-{scenario}-source.sqlite3"
    backup = tmp_path / f"post-truncate-{scenario}-backup.sqlite3"
    destination = tmp_path / f"post-truncate-{scenario}-destination.sqlite3"
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
    initial_marker = _read_user_version_from_database(destination)
    claim_count = readiness.replay_claim_count
    first_marker = (initial_marker + _FIRST_MARKER_DELTA) % 2_147_483_647
    first_inner = (first_marker + _FIRST_INNER_DELTA) % 2_147_483_647
    second_marker = (first_marker + _SECOND_MARKER_DELTA) % 2_147_483_647
    second_inner = (second_marker + _SECOND_INNER_DELTA) % 2_147_483_647
    markers = {initial_marker, first_marker, first_inner, second_marker, second_inner}
    assert len(markers) == 5

    temporary_main = (
        tmp_path / f".{destination.name}.part11-96-post-truncate.partial"
    )
    residual_contents = {
        temporary_main: b"part11-96 post-truncate partial snapshot",
        Path(f"{temporary_main}-wal"): b"part11-96 post-truncate WAL residue",
        Path(f"{temporary_main}-shm"): b"part11-96 post-truncate SHM residue",
        Path(f"{temporary_main}-journal"): (
            b"part11-96 post-truncate journal residue"
        ),
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    writer = sqlite3.connect(destination, timeout=0.0, isolation_level=None)
    try:
        first_collision_messages = _run_write_epoch(
            writer,
            marker=first_marker,
            inner_marker=first_inner,
            probe_index=_FIRST_EPOCH_INDEX,
            canonical_definition=canonical_definition,
            claim_count=claim_count,
        )
        first_truncate = writer.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        assert first_truncate is not None
        assert tuple(int(value) for value in first_truncate) == (0, 0, 0)
        assert _read_user_version(writer) == first_marker
        assert _has_index(writer, _FIRST_EPOCH_INDEX)
        assert (
            _claim_state_index_definition_from_connection(writer)
            == canonical_definition
        )

        # The first checkpoint has emptied the WAL. A subsequent write cycle
        # must create a fresh WAL generation without inheriting old frames.
        second_collision_messages = _run_write_epoch(
            writer,
            marker=second_marker,
            inner_marker=second_inner,
            probe_index=_SECOND_EPOCH_INDEX,
            canonical_definition=canonical_definition,
            claim_count=claim_count,
        )
        assert len(first_collision_messages) == _COLLISION_ATTEMPTS
        assert len(second_collision_messages) == _COLLISION_ATTEMPTS
        assert first_collision_messages == second_collision_messages

        passive_checkpoint = writer.execute(
            "PRAGMA wal_checkpoint(PASSIVE)"
        ).fetchone()
        assert passive_checkpoint is not None
        assert len(passive_checkpoint) == 3
        assert int(passive_checkpoint[0]) == 0
        second_epoch_frames = int(passive_checkpoint[1])
        checkpointed_frames = int(passive_checkpoint[2])
        assert second_epoch_frames > 0
        assert checkpointed_frames == second_epoch_frames

        second_truncate = writer.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        assert second_truncate is not None
        assert tuple(int(value) for value in second_truncate) == (0, 0, 0)
        assert _read_user_version(writer) == second_marker
        assert _has_index(writer, _FIRST_EPOCH_INDEX)
        assert _has_index(writer, _SECOND_EPOCH_INDEX)
        assert (
            _claim_state_index_definition_from_connection(writer)
            == canonical_definition
        )
    finally:
        if writer.in_transaction:
            writer.execute("ROLLBACK")
        writer.close()

    assert _read_user_version_from_database(destination) == second_marker
    assert _has_index_from_database(destination, _FIRST_EPOCH_INDEX)
    assert _has_index_from_database(destination, _SECOND_EPOCH_INDEX)
    assert _claim_state_index_definition(destination) == canonical_definition
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
        assert _read_user_version_from_database(destination) == second_marker
        assert _has_index_from_database(destination, _FIRST_EPOCH_INDEX)
        assert _has_index_from_database(destination, _SECOND_EPOCH_INDEX)
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
