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
_OUTER_PROBE_INDEX = "sh3_replay_claims_part11_86_outer_rollback_probe_idx"
_SAVEPOINT = "part11_86_collision_scope"
_COLLISION_ATTEMPTS = 3
_OUTER_USER_VERSION_MARKER = 86186
_INNER_USER_VERSION_MARKER = 86187


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


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_duplicate_index_collision_outer_rollback_restores_database_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"outer-rollback-{scenario}-source.sqlite3"
    backup = tmp_path / f"outer-rollback-{scenario}-backup.sqlite3"
    destination = tmp_path / f"outer-rollback-{scenario}-destination.sqlite3"
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
        tmp_path
        / f".{destination.name}.part11-86-outer-rollback.partial"
    )
    residual_contents = {
        temporary_main: b"part11-86 outer rollback temporary snapshot",
        Path(f"{temporary_main}-wal"): b"part11-86 outer rollback WAL residue",
        Path(f"{temporary_main}-shm"): b"part11-86 outer rollback SHM residue",
        Path(f"{temporary_main}-journal"): (
            b"part11-86 outer rollback journal residue"
        ),
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    outer_marker = (
        original_user_version + _OUTER_USER_VERSION_MARKER
    ) % 2_147_483_647
    inner_marker = (outer_marker + _INNER_USER_VERSION_MARKER) % 2_147_483_647
    assert outer_marker != original_user_version
    assert inner_marker != outer_marker
    collision_messages: list[str] = []

    connection = sqlite3.connect(destination, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        assert _read_user_version(connection) == original_user_version
        connection.execute(f"PRAGMA user_version = {outer_marker}")
        connection.execute(
            f"CREATE INDEX {_OUTER_PROBE_INDEX} "
            "ON sh3_replay_claims(lease_expires_at)"
        )
        assert connection.in_transaction
        assert _read_user_version(connection) == outer_marker
        assert _has_index(connection, _OUTER_PROBE_INDEX)

        for _ in range(_COLLISION_ATTEMPTS):
            connection.execute(f"SAVEPOINT {_SAVEPOINT}")
            connection.execute(f"PRAGMA user_version = {inner_marker}")
            with pytest.raises(
                sqlite3.OperationalError,
                match="already exists",
            ) as error:
                connection.execute(
                    f"CREATE INDEX {_REQUIRED_INDEX} "
                    "ON sh3_replay_claims(lease_expires_at, state)"
                )
            collision_messages.append(str(error.value))
            assert connection.in_transaction
            assert _read_user_version(connection) == inner_marker
            connection.execute(f"ROLLBACK TO SAVEPOINT {_SAVEPOINT}")
            connection.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
            assert connection.in_transaction
            assert _read_user_version(connection) == outer_marker
            assert _has_index(connection, _OUTER_PROBE_INDEX)
            assert (
                _claim_state_index_definition_from_connection(connection)
                == canonical_definition
            )
            row = connection.execute(
                "SELECT COUNT(*) FROM sh3_replay_claims"
            ).fetchone()
            assert row is not None
            assert int(row[0]) == claim_count

        assert len(collision_messages) == _COLLISION_ATTEMPTS
        assert len(set(collision_messages)) == 1
        assert connection.in_transaction
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()

    # The caller's full rollback must discard its valid transactional DDL and
    # marker as well as the scoped work, while retaining the original index.
    assert _claim_state_index_definition(destination) == canonical_definition
    assert not _has_index_from_database(destination, _OUTER_PROBE_INDEX)
    assert _read_user_version_from_database(destination) == original_user_version
    assert replay_ops.check_database(destination) == readiness
    destination_bytes_after_rollback = destination.read_bytes()
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
        "sqlite_version": readiness.sqlite_version,
        "journal_mode": readiness.journal_mode,
        "integrity_status": "pass",
        "evidence_records": readiness.evidence_count,
        "replay_claims": readiness.replay_claim_count,
        "expired_claims": readiness.expired_claim_count,
        "pending_evidence_reconciliation": (
            readiness.pending_evidence_reconciliation_count
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
        assert not _has_index_from_database(destination, _OUTER_PROBE_INDEX)
        assert _read_user_version_from_database(destination) == original_user_version
        assert destination.read_bytes() == destination_bytes_after_rollback
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
