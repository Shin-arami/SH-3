from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)

_REQUIRED_INDEX = "sh3_replay_claims_state_idx"
_PROBE_INDEX = "sh3_replay_claims_part11_108_uncommitted_writer_idx"
_SAVEPOINT = "part11_108_snapshot_scope"
_COLLISION_ATTEMPTS = 3
_MAX_USER_VERSION = 2_147_483_647
_WRITE_MARKER_DELTA = 108_108
_INNER_MARKER_DELTA = 108_908


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


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
        f"{database.as_uri()}?mode=ro", uri=True, timeout=0.0, isolation_level=None
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


def _index_definition(
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


def _index_definition_from_database(
    database: Path,
) -> tuple[str, bool, bool, tuple[str, ...]]:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro", uri=True, timeout=0.0, isolation_level=None
    )
    try:
        return _index_definition(connection)
    finally:
        connection.close()


def _has_index_from_database(database: Path, index_name: str) -> bool:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro", uri=True, timeout=0.0, isolation_level=None
    )
    try:
        return _has_index(connection, index_name)
    finally:
        connection.close()


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _expected_operation_report(
    *, action: str, destination: Path, readiness: Any
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "action": action,
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


def _run_process_snapshot_operation(
    *, action: str, source: Path, destination: Path
) -> subprocess.CompletedProcess[str]:
    if action == "backup":
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
    command = (
        "import sys; "
        "from infrastructure.security.persistent_replay_ops import main; "
        "raise SystemExit(main(sys.argv[1:]))"
    )
    return subprocess.run(
        [sys.executable, "-c", command, *arguments],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=20.0,
        check=False,
    )


def _residual_artifact_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


@pytest.mark.parametrize(
    ("scenario", "action"),
    (
        ("backup-destination", "backup"),
        ("restore-destination", "restore"),
    ),
    ids=("backup-destination", "restore-destination"),
)
def test_process_backup_and_restore_observe_only_committed_wal_writer_state(
    tmp_path: Path,
    scenario: str,
    action: str,
) -> None:
    source = tmp_path / f"uncommitted-writer-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"uncommitted-writer-{scenario}-input-backup.sqlite3"
    destination = tmp_path / f"uncommitted-writer-{scenario}-destination.sqlite3"
    _initialize_database(source)

    protected_sources: tuple[Path, ...]
    if action == "backup":
        operation_source = source
        protected_sources = (source,)
    else:
        replay_ops.backup_database(source, backup_input)
        operation_source = backup_input
        protected_sources = (source, backup_input)

    _set_wal_mode(operation_source)
    readiness = replay_ops.check_database(operation_source)
    assert readiness.journal_mode.casefold() == "wal"
    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    assert _index_definition_from_database(operation_source) == canonical_definition
    original_marker = _read_user_version_from_database(operation_source)
    claim_count = readiness.replay_claim_count
    marker = (original_marker + _WRITE_MARKER_DELTA) % _MAX_USER_VERSION
    inner_marker = (marker + _INNER_MARKER_DELTA) % _MAX_USER_VERSION
    assert len({original_marker, marker, inner_marker}) == 3

    temporary_main = (
        tmp_path / f".{destination.name}.part11-108-uncommitted-writer.partial"
    )
    residual_contents = {
        temporary_main: b"part11-108 protected partial snapshot",
        Path(f"{temporary_main}-wal"): b"part11-108 protected WAL residue",
        Path(f"{temporary_main}-shm"): b"part11-108 protected SHM residue",
        Path(f"{temporary_main}-journal"): b"part11-108 protected journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(sorted(p.name for p in residual_contents))

    protected_source_bytes = {path: path.read_bytes() for path in protected_sources}
    source_wal_path = Path(f"{operation_source}-wal")
    writer = sqlite3.connect(operation_source, timeout=0.0, isolation_level=None)
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(f"PRAGMA user_version = {marker}")
        writer.execute(
            f"CREATE INDEX {_PROBE_INDEX} ON sh3_replay_claims(lease_expires_at)"
        )
        assert writer.in_transaction
        assert _read_user_version(writer) == marker
        assert _has_index(writer, _PROBE_INDEX)

        collision_messages: list[str] = []
        for _ in range(_COLLISION_ATTEMPTS):
            writer.execute(f"SAVEPOINT {_SAVEPOINT}")
            writer.execute(f"PRAGMA user_version = {inner_marker}")
            with pytest.raises(sqlite3.OperationalError, match="already exists") as exc:
                writer.execute(
                    f"CREATE INDEX {_REQUIRED_INDEX} "
                    "ON sh3_replay_claims(lease_expires_at, state)"
                )
            collision_messages.append(str(exc.value))
            assert writer.in_transaction
            assert _read_user_version(writer) == inner_marker
            writer.execute(f"ROLLBACK TO SAVEPOINT {_SAVEPOINT}")
            writer.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
            assert writer.in_transaction
            assert _read_user_version(writer) == marker
            assert _has_index(writer, _PROBE_INDEX)
            assert _index_definition(writer) == canonical_definition
            claim_row = writer.execute(
                "SELECT COUNT(*) FROM sh3_replay_claims"
            ).fetchone()
            assert claim_row is not None
            assert int(claim_row[0]) == claim_count

        assert len(collision_messages) == _COLLISION_ATTEMPTS
        assert len(set(collision_messages)) == 1
        database_bytes_before = operation_source.read_bytes()
        assert source_wal_path.is_file()
        wal_bytes_before = source_wal_path.read_bytes()

        # Run the actual CLI in a distinct Python process while the source writer
        # retains uncommitted DDL and user_version changes in WAL mode.
        result = _run_process_snapshot_operation(
            action=action,
            source=operation_source,
            destination=destination,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.count("\n") == 1
        assert result.stderr == ""
        operation_report = _read_report(result.stdout)
        assert operation_report["action"] == action
        assert operation_report["database"] == str(destination.resolve())
        assert operation_report["integrity_status"] == "pass"
        assert operation_report["exit_code"] == 0

        # Snapshot publication must include only the source's last committed epoch.
        snapshot_readiness = replay_ops.check_database(destination)
        assert snapshot_readiness.evidence_count == readiness.evidence_count
        assert snapshot_readiness.replay_claim_count == readiness.replay_claim_count
        assert snapshot_readiness.expired_claim_count == readiness.expired_claim_count
        assert (
            snapshot_readiness.pending_evidence_reconciliation_count
            == readiness.pending_evidence_reconciliation_count
        )
        assert _read_user_version_from_database(destination) == original_marker
        assert _index_definition_from_database(destination) == canonical_definition
        assert not _has_index_from_database(destination, _PROBE_INDEX)
        expected_report = _expected_operation_report(
            action=action, destination=destination, readiness=snapshot_readiness
        )
        assert operation_report == expected_report

        # Online snapshot creation must not mutate the active writer's DB or WAL.
        assert operation_source.read_bytes() == database_bytes_before
        assert source_wal_path.read_bytes() == wal_bytes_before
        assert writer.in_transaction
        assert _read_user_version(writer) == marker
        assert _has_index(writer, _PROBE_INDEX)
        assert _index_definition(writer) == canonical_definition
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        for protected_source in protected_sources:
            if protected_source == operation_source:
                continue
            assert (
                protected_source.read_bytes()
                == protected_source_bytes[protected_source]
            )

        # The separate snapshot remains stable even after the writer commits its epoch.
        writer.execute("COMMIT")
        assert not writer.in_transaction
        assert _read_user_version(writer) == marker
        assert _has_index(writer, _PROBE_INDEX)
        snapshot_bytes = destination.read_bytes()
        post_commit_report = replay_ops.check_database(destination)
        assert post_commit_report == snapshot_readiness
        assert destination.read_bytes() == snapshot_bytes
        assert _read_user_version_from_database(destination) == original_marker
        assert _index_definition_from_database(destination) == canonical_definition

        follow_up = _run_process_snapshot_operation(
            action=action,
            source=operation_source,
            destination=tmp_path / f"{destination.stem}-follow-up.sqlite3",
        )
        assert follow_up.returncode == 0, follow_up.stderr
        assert follow_up.stderr == ""
        follow_up_report = _read_report(follow_up.stdout)
        assert follow_up_report["action"] == action
        assert follow_up_report["integrity_status"] == "pass"
        assert follow_up_report["exit_code"] == 0
    finally:
        if writer.in_transaction:
            writer.execute("ROLLBACK")
        writer.close()

    for protected_source in protected_sources:
        if protected_source == operation_source:
            # The single deliberate commit is expected to update the active input.
            assert _read_user_version_from_database(protected_source) == marker
            assert (
                _index_definition_from_database(protected_source)
                == canonical_definition
            )
        else:
            assert (
                protected_source.read_bytes()
                == protected_source_bytes[protected_source]
            )
    assert _read_user_version_from_database(destination) == original_marker
    assert _index_definition_from_database(destination) == canonical_definition
    assert _residual_artifact_names(tmp_path, destination) == residual_names_before
    for artifact, contents in residual_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents
