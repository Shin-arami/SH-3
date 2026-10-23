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
_FIRST_WRITER_INDEX = "sh3_replay_claims_part11_89_first_writer_idx"
_SECOND_WRITER_INDEX = "sh3_replay_claims_part11_89_second_writer_idx"
_SAVEPOINT = "part11_89_collision_scope"
_COLLISION_ATTEMPTS = 3
_FIRST_WRITER_MARKER = 89_189
_SECOND_WRITER_MARKER = 89_289


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _residual_artifact_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


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
        isolation_level=None,
    )
    try:
        return _claim_state_index_definition_from_connection(connection)
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
        isolation_level=None,
    )
    try:
        return _has_index(connection, index_name)
    finally:
        connection.close()


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_required_index_collision_isolated_across_contending_writers(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"writer-contention-{scenario}-source.sqlite3"
    backup = tmp_path / f"writer-contention-{scenario}-backup.sqlite3"
    destination = tmp_path / f"writer-contention-{scenario}-destination.sqlite3"
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
    readiness = replay_ops.check_database(destination)
    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    assert _claim_state_index_definition(destination) == canonical_definition
    original_user_version = _read_user_version_from_database(destination)
    claim_count = readiness.replay_claim_count

    temporary_main = (
        tmp_path / f".{destination.name}.part11-89-writer-contention.partial"
    )
    residual_contents = {
        temporary_main: b"part11-89 writer-contention partial snapshot",
        Path(f"{temporary_main}-wal"): b"part11-89 writer-contention WAL residue",
        Path(f"{temporary_main}-shm"): b"part11-89 writer-contention SHM residue",
        Path(f"{temporary_main}-journal"): (
            b"part11-89 writer-contention journal residue"
        ),
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    first_writer_marker = (
        original_user_version + _FIRST_WRITER_MARKER
    ) % 2_147_483_647
    second_writer_marker = (
        first_writer_marker + _SECOND_WRITER_MARKER
    ) % 2_147_483_647
    assert first_writer_marker != original_user_version
    assert second_writer_marker != first_writer_marker
    lock_messages: list[str] = []
    collision_messages: list[str] = []

    # Keep both writer connections open so the second writer encounters the
    # first writer's live RESERVED lock rather than relying on thread timing.
    first_writer = sqlite3.connect(
        destination,
        timeout=0.0,
        isolation_level=None,
    )
    second_writer = sqlite3.connect(
        destination,
        timeout=0.0,
        isolation_level=None,
    )
    try:
        first_writer.execute("BEGIN IMMEDIATE")
        first_writer.execute(f"PRAGMA user_version = {first_writer_marker}")
        first_writer.execute(
            f"CREATE INDEX {_FIRST_WRITER_INDEX} "
            "ON sh3_replay_claims(lease_expires_at)"
        )
        assert first_writer.in_transaction
        assert _read_user_version(first_writer) == first_writer_marker
        assert _has_index(first_writer, _FIRST_WRITER_INDEX)
        assert (
            _claim_state_index_definition_from_connection(first_writer)
            == canonical_definition
        )

        with pytest.raises(
            sqlite3.OperationalError,
            match=r"locked|busy",
        ) as lock_error:
            second_writer.execute("BEGIN IMMEDIATE")
        lock_messages.append(str(lock_error.value))
        assert not second_writer.in_transaction
        assert first_writer.in_transaction
        assert _read_user_version(first_writer) == first_writer_marker

        first_writer.execute("COMMIT")
        assert not first_writer.in_transaction
        assert not second_writer.in_transaction

        # Reusing the same second connection after the lock failure must see
        # the first writer's committed schema before attempting the collision.
        second_writer.execute("BEGIN IMMEDIATE")
        assert _read_user_version(second_writer) == first_writer_marker
        assert _has_index(second_writer, _FIRST_WRITER_INDEX)
        assert (
            _claim_state_index_definition_from_connection(second_writer)
            == canonical_definition
        )
        outer_marker = _read_user_version(second_writer)
        inner_marker = (
            outer_marker + _SECOND_WRITER_MARKER
        ) % 2_147_483_647
        assert inner_marker != outer_marker

        for _ in range(_COLLISION_ATTEMPTS):
            second_writer.execute(f"SAVEPOINT {_SAVEPOINT}")
            second_writer.execute(f"PRAGMA user_version = {inner_marker}")
            with pytest.raises(
                sqlite3.OperationalError,
                match="already exists",
            ) as collision_error:
                second_writer.execute(
                    f"CREATE INDEX {_REQUIRED_INDEX} "
                    "ON sh3_replay_claims(lease_expires_at, state)"
                )
            collision_messages.append(str(collision_error.value))
            assert second_writer.in_transaction
            assert _read_user_version(second_writer) == inner_marker
            second_writer.execute(f"ROLLBACK TO SAVEPOINT {_SAVEPOINT}")
            second_writer.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
            assert second_writer.in_transaction
            assert _read_user_version(second_writer) == outer_marker
            assert _has_index(second_writer, _FIRST_WRITER_INDEX)
            assert (
                _claim_state_index_definition_from_connection(second_writer)
                == canonical_definition
            )
            claim_row = second_writer.execute(
                "SELECT COUNT(*) FROM sh3_replay_claims"
            ).fetchone()
            assert claim_row is not None
            assert int(claim_row[0]) == claim_count

        assert len(lock_messages) == 1
        assert len(collision_messages) == _COLLISION_ATTEMPTS
        assert len(set(collision_messages)) == 1
        assert second_writer.in_transaction
        second_writer.execute(f"PRAGMA user_version = {second_writer_marker}")
        second_writer.execute(
            f"CREATE INDEX {_SECOND_WRITER_INDEX} "
            "ON sh3_replay_claims(state)"
        )
        assert _has_index(second_writer, _SECOND_WRITER_INDEX)
        second_writer.execute("COMMIT")
        assert not second_writer.in_transaction
    finally:
        if first_writer.in_transaction:
            first_writer.execute("ROLLBACK")
        if second_writer.in_transaction:
            second_writer.execute("ROLLBACK")
        first_writer.close()
        second_writer.close()

    # The blocked writer's valid work must commit, and its later failed index
    # attempts must not alter the required index or erase either writer's work.
    assert _claim_state_index_definition(destination) == canonical_definition
    assert _has_index_from_database(destination, _FIRST_WRITER_INDEX)
    assert _has_index_from_database(destination, _SECOND_WRITER_INDEX)
    assert _read_user_version_from_database(destination) == second_writer_marker
    committed_readiness = replay_ops.check_database(destination)
    assert committed_readiness == readiness
    destination_bytes_after_writes = destination.read_bytes()
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
        assert _claim_state_index_definition(destination) == canonical_definition
        assert _has_index_from_database(destination, _FIRST_WRITER_INDEX)
        assert _has_index_from_database(destination, _SECOND_WRITER_INDEX)
        assert _read_user_version_from_database(destination) == second_writer_marker
        assert destination.read_bytes() == destination_bytes_after_writes
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
