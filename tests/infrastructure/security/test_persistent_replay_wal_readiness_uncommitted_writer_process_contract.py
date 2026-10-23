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
_PROBE_INDEX = "sh3_replay_claims_part11_107_writer_probe_idx"
_SAVEPOINT = "part11_107_readiness_writer_scope"
_COLLISION_ATTEMPTS = 3
_MAX_USER_VERSION = 2_147_483_647
_WRITE_MARKER_DELTA = 107_107
_INNER_MARKER_DELTA = 107_907


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


def _has_index(connection: sqlite3.Connection, index_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        is not None
    )


def _claim_state_index_definition(
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


def _readiness_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _expected_cli_report(database: Path, readiness: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "action": "check",
        "database": str(database.resolve()),
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


def _run_process_readiness_check(database: Path) -> subprocess.CompletedProcess[str]:
    command = (
        "import sys; "
        "from infrastructure.security.persistent_replay_ops import main; "
        "raise SystemExit(main(['check', '--database', sys.argv[1], '--json']))"
    )
    return subprocess.run(
        [sys.executable, "-c", command, str(database)],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=15.0,
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
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_process_readiness_checks_stay_observational_during_uncommitted_wal_writer(
    tmp_path: Path,
    scenario: str,
) -> None:
    source = tmp_path / f"writer-process-{scenario}-source.sqlite3"
    backup = tmp_path / f"writer-process-{scenario}-backup.sqlite3"
    destination = tmp_path / f"writer-process-{scenario}-destination.sqlite3"
    _initialize_database(source)
    protected_sources = _prepare_destination(
        source,
        backup,
        destination,
        scenario=scenario,
    )
    protected_source_bytes = {path: path.read_bytes() for path in protected_sources}
    _set_wal_mode(destination)

    readiness = replay_ops.check_database(destination)
    assert readiness.journal_mode.casefold() == "wal"
    expected_report = _expected_cli_report(destination, readiness)
    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    assert (
        _claim_state_index_definition_from_database(destination)
        == canonical_definition
    )
    original_marker = _read_user_version_from_database(destination)
    claim_count = readiness.replay_claim_count
    marker = (original_marker + _WRITE_MARKER_DELTA) % _MAX_USER_VERSION
    inner_marker = (marker + _INNER_MARKER_DELTA) % _MAX_USER_VERSION
    assert len({original_marker, marker, inner_marker}) == 3

    temporary_main = (
        tmp_path / f".{destination.name}.part11-107-writer-process.partial"
    )
    residual_contents = {
        temporary_main: b"part11-107 writer-process partial snapshot",
        Path(f"{temporary_main}-wal"): b"part11-107 writer-process WAL residue",
        Path(f"{temporary_main}-shm"): b"part11-107 writer-process SHM residue",
        Path(f"{temporary_main}-journal"): b"part11-107 writer-process journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(sorted(p.name for p in residual_contents))

    reader = sqlite3.connect(destination, timeout=0.0, isolation_level=None)
    writer = sqlite3.connect(destination, timeout=0.0, isolation_level=None)
    reader_closed = False
    try:
        # Pin the last committed snapshot before the writer stages its epoch.
        reader.execute("BEGIN")
        initial_claims = reader.execute(
            "SELECT COUNT(*) FROM sh3_replay_claims"
        ).fetchone()
        assert initial_claims is not None
        assert int(initial_claims[0]) == claim_count
        assert _read_user_version(reader) == original_marker
        assert _claim_state_index_definition(reader) == canonical_definition
        assert not _has_index(reader, _PROBE_INDEX)

        writer.execute("BEGIN IMMEDIATE")
        writer.execute(f"PRAGMA user_version = {marker}")
        writer.execute(
            f"CREATE INDEX {_PROBE_INDEX} "
            "ON sh3_replay_claims(lease_expires_at)"
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
            assert _claim_state_index_definition(writer) == canonical_definition
            row = writer.execute(
                "SELECT COUNT(*) FROM sh3_replay_claims"
            ).fetchone()
            assert row is not None
            assert int(row[0]) == claim_count
        assert len(collision_messages) == _COLLISION_ATTEMPTS
        assert len(set(collision_messages)) == 1

        # Take a stable image after the writer's uncommitted work; read-only
        # subprocesses must not commit, checkpoint, or otherwise mutate it.
        database_bytes_before = destination.read_bytes()
        wal_path = Path(f"{destination}-wal")
        assert wal_path.is_file()
        wal_bytes_before = wal_path.read_bytes()

        api_results = [replay_ops.check_database(destination) for _ in range(3)]
        assert api_results == [readiness, readiness, readiness]
        assert destination.read_bytes() == database_bytes_before
        assert wal_path.read_bytes() == wal_bytes_before
        assert _read_user_version(reader) == original_marker
        assert not _has_index(reader, _PROBE_INDEX)
        assert _read_user_version(writer) == marker
        assert _has_index(writer, _PROBE_INDEX)

        process_reports: list[dict[str, Any]] = []
        for _ in range(3):
            result = _run_process_readiness_check(destination)
            assert result.returncode == 0, result.stderr
            assert result.stdout.count("\n") == 1
            assert result.stderr == ""
            report = _readiness_report(result.stdout)
            assert report == expected_report
            process_reports.append(report)
            assert destination.read_bytes() == database_bytes_before
            assert wal_path.read_bytes() == wal_bytes_before
            assert _read_user_version(reader) == original_marker
            assert not _has_index(reader, _PROBE_INDEX)
            assert _read_user_version(writer) == marker
            assert _has_index(writer, _PROBE_INDEX)
        assert process_reports[0] == process_reports[1] == process_reports[2]

        # Commit only after all read-only observers have finished. The old reader
        # keeps the pre-commit snapshot, while a fresh observer sees the new epoch.
        writer.execute("COMMIT")
        assert not writer.in_transaction
        assert _read_user_version(reader) == original_marker
        assert not _has_index(reader, _PROBE_INDEX)
        assert _read_user_version(writer) == marker
        assert _has_index(writer, _PROBE_INDEX)
        assert _claim_state_index_definition(writer) == canonical_definition
        reader.execute("ROLLBACK")
        assert not reader.in_transaction
        reader.close()
        reader_closed = True
    finally:
        if not reader_closed:
            if reader.in_transaction:
                reader.execute("ROLLBACK")
            reader.close()
        if writer.in_transaction:
            writer.execute("ROLLBACK")
        writer.close()

    committed_readiness = replay_ops.check_database(destination)
    assert committed_readiness == readiness
    committed_image = destination.read_bytes()
    wal_path = Path(f"{destination}-wal")
    committed_wal = wal_path.read_bytes() if wal_path.exists() else None
    post_commit_reports: list[dict[str, Any]] = []
    for _ in range(2):
        result = _run_process_readiness_check(destination)
        assert result.returncode == 0, result.stderr
        assert result.stdout.count("\n") == 1
        assert result.stderr == ""
        report = _readiness_report(result.stdout)
        assert report == expected_report
        post_commit_reports.append(report)
        assert destination.read_bytes() == committed_image
        current_wal = wal_path.read_bytes() if wal_path.exists() else None
        assert current_wal == committed_wal
        assert (
            _claim_state_index_definition_from_database(destination)
            == canonical_definition
        )
        connection = sqlite3.connect(
            f"{destination.as_uri()}?mode=ro",
            uri=True,
            timeout=0.0,
            isolation_level=None,
        )
        try:
            assert _read_user_version(connection) == marker
            assert _has_index(connection, _PROBE_INDEX)
        finally:
            connection.close()
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        for protected_source in protected_sources:
            assert (
                protected_source.read_bytes()
                == protected_source_bytes[protected_source]
            )
    assert post_commit_reports[0] == post_commit_reports[1]


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


def _claim_state_index_definition_from_database(
    database: Path,
) -> tuple[str, bool, bool, tuple[str, ...]]:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
        timeout=0.0,
        isolation_level=None,
    )
    try:
        return _claim_state_index_definition(connection)
    finally:
        connection.close()
