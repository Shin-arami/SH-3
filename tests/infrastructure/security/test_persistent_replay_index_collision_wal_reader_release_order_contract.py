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
_FIRST_PROBE_INDEX = "sh3_replay_claims_part11_99_first_epoch_idx"
_SECOND_PROBE_INDEX = "sh3_replay_claims_part11_99_second_epoch_idx"
_SAVEPOINT = "part11_99_collision_scope"
_COLLISION_ATTEMPTS = 3
_FIRST_EPOCH_DELTA = 99_199
_SECOND_EPOCH_DELTA = 99_299
_FIRST_INNER_DELTA = 99_399
_SECOND_INNER_DELTA = 99_499
_MAX_USER_VERSION = 2_147_483_647


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
    expected_marker: int,
    inner_marker: int,
    visible_probe_indexes: tuple[str, ...],
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
        assert _read_user_version(connection) == expected_marker
        assert (
            _claim_state_index_definition_from_connection(connection)
            == canonical_definition
        )
        for index_name in (_FIRST_PROBE_INDEX, _SECOND_PROBE_INDEX):
            assert _has_index(connection, index_name) is (
                index_name in visible_probe_indexes
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
def test_wal_checkpoint_obeys_reverse_reader_release_order(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"multi-reader-{scenario}-source.sqlite3"
    backup = tmp_path / f"multi-reader-{scenario}-backup.sqlite3"
    destination = tmp_path / f"multi-reader-{scenario}-destination.sqlite3"
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
    first_epoch_marker = (original_marker + _FIRST_EPOCH_DELTA) % _MAX_USER_VERSION
    second_epoch_marker = (
        first_epoch_marker + _SECOND_EPOCH_DELTA
    ) % _MAX_USER_VERSION
    first_inner_marker = (
        first_epoch_marker + _FIRST_INNER_DELTA
    ) % _MAX_USER_VERSION
    second_inner_marker = (
        second_epoch_marker + _SECOND_INNER_DELTA
    ) % _MAX_USER_VERSION
    assert len(
        {
            original_marker,
            first_epoch_marker,
            second_epoch_marker,
            first_inner_marker,
            second_inner_marker,
        }
    ) == 5

    temporary_main = (
        tmp_path / f".{destination.name}.part11-99-multi-reader.partial"
    )
    residual_contents = {
        temporary_main: b"part11-99 multi-reader partial snapshot",
        Path(f"{temporary_main}-wal"): b"part11-99 multi-reader WAL residue",
        Path(f"{temporary_main}-shm"): b"part11-99 multi-reader SHM residue",
        Path(f"{temporary_main}-journal"): b"part11-99 multi-reader journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    older_reader = sqlite3.connect(
        destination,
        timeout=0.0,
        isolation_level=None,
    )
    writer = sqlite3.connect(destination, timeout=0.0, isolation_level=None)
    newer_reader = sqlite3.connect(
        destination,
        timeout=0.0,
        isolation_level=None,
    )
    older_reader_closed = False
    newer_reader_closed = False
    try:
        older_reader.execute("BEGIN")
        base_claims = older_reader.execute(
            "SELECT COUNT(*) FROM sh3_replay_claims"
        ).fetchone()
        assert base_claims is not None
        assert int(base_claims[0]) == claim_count
        assert _read_user_version(older_reader) == original_marker
        assert _claim_state_index_definition_from_connection(
            older_reader
        ) == canonical_definition
        assert not _has_index(older_reader, _FIRST_PROBE_INDEX)
        assert not _has_index(older_reader, _SECOND_PROBE_INDEX)

        writer.execute("BEGIN IMMEDIATE")
        writer.execute(f"PRAGMA user_version = {first_epoch_marker}")
        writer.execute(
            f"CREATE INDEX {_FIRST_PROBE_INDEX} "
            "ON sh3_replay_claims(lease_expires_at)"
        )
        _assert_collision_retries(
            writer,
            expected_marker=first_epoch_marker,
            inner_marker=first_inner_marker,
            visible_probe_indexes=(_FIRST_PROBE_INDEX,),
            claim_count=claim_count,
            canonical_definition=canonical_definition,
        )
        writer.execute("COMMIT")
        assert not writer.in_transaction

        newer_reader.execute("BEGIN")
        middle_claims = newer_reader.execute(
            "SELECT COUNT(*) FROM sh3_replay_claims"
        ).fetchone()
        assert middle_claims is not None
        assert int(middle_claims[0]) == claim_count
        assert _read_user_version(newer_reader) == first_epoch_marker
        assert _has_index(newer_reader, _FIRST_PROBE_INDEX)
        assert not _has_index(newer_reader, _SECOND_PROBE_INDEX)
        assert (
            _claim_state_index_definition_from_connection(newer_reader)
            == canonical_definition
        )

        writer.execute("BEGIN IMMEDIATE")
        writer.execute(f"PRAGMA user_version = {second_epoch_marker}")
        writer.execute(
            f"CREATE INDEX {_SECOND_PROBE_INDEX} "
            "ON sh3_replay_claims(state)"
        )
        _assert_collision_retries(
            writer,
            expected_marker=second_epoch_marker,
            inner_marker=second_inner_marker,
            visible_probe_indexes=(_FIRST_PROBE_INDEX, _SECOND_PROBE_INDEX),
            claim_count=claim_count,
            canonical_definition=canonical_definition,
        )
        writer.execute("COMMIT")
        assert not writer.in_transaction

        assert _read_user_version(older_reader) == original_marker
        assert not _has_index(older_reader, _FIRST_PROBE_INDEX)
        assert not _has_index(older_reader, _SECOND_PROBE_INDEX)
        assert _read_user_version(newer_reader) == first_epoch_marker
        assert _has_index(newer_reader, _FIRST_PROBE_INDEX)
        assert not _has_index(newer_reader, _SECOND_PROBE_INDEX)
        assert (
            _claim_state_index_definition_from_connection(older_reader)
            == canonical_definition
        )
        assert (
            _claim_state_index_definition_from_connection(newer_reader)
            == canonical_definition
        )

        both_reader_results: list[tuple[int, int, int]] = []
        for _ in range(2):
            result = writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            assert result is not None
            assert len(result) == 3
            busy, log_frames, checkpointed_frames = (
                int(value) for value in result
            )
            assert busy == 1
            assert log_frames > 0
            assert 0 <= checkpointed_frames <= log_frames
            both_reader_results.append((busy, log_frames, checkpointed_frames))
            assert _read_user_version(older_reader) == original_marker
            assert _read_user_version(newer_reader) == first_epoch_marker
            assert not _has_index(older_reader, _FIRST_PROBE_INDEX)
            assert _has_index(newer_reader, _FIRST_PROBE_INDEX)
            assert not _has_index(newer_reader, _SECOND_PROBE_INDEX)
        assert both_reader_results[0] == both_reader_results[1]

        # Release the newer/intermediate reader first. The older reader must
        # still pin the checkpoint because it retains the oldest WAL snapshot.
        newer_reader.execute("ROLLBACK")
        assert not newer_reader.in_transaction
        newer_reader.close()
        newer_reader_closed = True

        oldest_reader_results: list[tuple[int, int, int]] = []
        for _ in range(2):
            result = writer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            assert result is not None
            assert len(result) == 3
            busy, log_frames, checkpointed_frames = (
                int(value) for value in result
            )
            assert busy == 1
            assert log_frames > 0
            assert 0 <= checkpointed_frames <= log_frames
            oldest_reader_results.append((busy, log_frames, checkpointed_frames))
            assert _read_user_version(older_reader) == original_marker
            assert not _has_index(older_reader, _FIRST_PROBE_INDEX)
            assert not _has_index(older_reader, _SECOND_PROBE_INDEX)
            assert (
                _claim_state_index_definition_from_connection(older_reader)
                == canonical_definition
            )
        assert oldest_reader_results[0] == oldest_reader_results[1]

        # Once the oldest reader releases its snapshot, the same checkpoint
        # connection can complete TRUNCATE for both committed write epochs.
        older_reader.execute("ROLLBACK")
        assert not older_reader.in_transaction
        older_reader.close()
        older_reader_closed = True

        final_checkpoint = writer.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        assert final_checkpoint is not None
        assert tuple(int(value) for value in final_checkpoint) == (0, 0, 0)
        wal_path = Path(f"{destination}-wal")
        if wal_path.exists():
            assert wal_path.stat().st_size == 0

        assert _read_user_version(writer) == second_epoch_marker
        assert _has_index(writer, _FIRST_PROBE_INDEX)
        assert _has_index(writer, _SECOND_PROBE_INDEX)
        assert (
            _claim_state_index_definition_from_connection(writer)
            == canonical_definition
        )
    finally:
        if not older_reader_closed:
            if older_reader.in_transaction:
                older_reader.execute("ROLLBACK")
            older_reader.close()
        if not newer_reader_closed:
            if newer_reader.in_transaction:
                newer_reader.execute("ROLLBACK")
            newer_reader.close()
        if writer.in_transaction:
            writer.execute("ROLLBACK")
        writer.close()

    assert _read_user_version_from_database(destination) == second_epoch_marker
    assert _has_index_from_database(destination, _FIRST_PROBE_INDEX)
    assert _has_index_from_database(destination, _SECOND_PROBE_INDEX)
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
        assert _read_user_version_from_database(destination) == second_epoch_marker
        assert _has_index_from_database(destination, _FIRST_PROBE_INDEX)
        assert _has_index_from_database(destination, _SECOND_PROBE_INDEX)
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
