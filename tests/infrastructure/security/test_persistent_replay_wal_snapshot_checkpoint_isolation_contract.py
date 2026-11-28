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
_PROBE_INDEXES = (
    "sh3_replay_claims_part11_109_epoch_one_idx",
    "sh3_replay_claims_part11_109_epoch_two_idx",
)
_SAVEPOINT = "part11_109_snapshot_isolation"
_COLLISION_ATTEMPTS = 3
_MARKER_DELTA = 10_900
_INNER_MARKER_DELTA = 10_901
_MAX_USER_VERSION = 2_147_483_647
_CHECKPOINT_SEQUENCES = (
    ("PASSIVE", "FULL", "RESTART", "TRUNCATE"),
    ("TRUNCATE", "RESTART", "FULL", "PASSIVE"),
)


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _set_wal_mode(database: Path) -> None:
    connection = sqlite3.connect(database, isolation_level=None)
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
        f"{database.as_uri()}?mode=ro", uri=True, isolation_level=None
    )
    try:
        return _read_user_version(connection)
    finally:
        connection.close()


def _has_index(connection: sqlite3.Connection, name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (name,),
        ).fetchone()
        is not None
    )


def _index_definition_from_connection(
    connection: sqlite3.Connection,
) -> tuple[str, bool, bool, tuple[str, ...]]:
    owner = connection.execute(
        "SELECT tbl_name FROM sqlite_master WHERE type = 'index' AND name = ?",
        (_REQUIRED_INDEX,),
    ).fetchone()
    assert owner is not None
    listed = next(
        row
        for row in connection.execute("PRAGMA index_list(sh3_replay_claims)")
        if str(row[1]) == _REQUIRED_INDEX
    )
    columns = connection.execute(
        f"PRAGMA index_info({_REQUIRED_INDEX})"
    ).fetchall()
    return (
        str(owner[0]),
        bool(listed[2]),
        bool(listed[4]),
        tuple(str(row[2]) for row in columns),
    )


def _index_definition(database: Path) -> tuple[str, bool, bool, tuple[str, ...]]:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro", uri=True, isolation_level=None
    )
    try:
        return _index_definition_from_connection(connection)
    finally:
        connection.close()


def _residual_artifacts(directory: Path, snapshot: Path) -> tuple[str, ...]:
    prefix = f".{snapshot.name}.part11-109."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix)
        )
    )


def _run_write_epoch(database: Path, *, marker: int, epoch: int) -> tuple[str, ...]:
    probe_index = _PROBE_INDEXES[epoch - 1]
    inner_marker = (marker + _INNER_MARKER_DELTA) % _MAX_USER_VERSION
    assert marker != inner_marker
    messages: list[str] = []
    connection = sqlite3.connect(database, timeout=0.0, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(f"PRAGMA user_version = {marker}")
        connection.execute(
            f"CREATE INDEX {probe_index} "
            "ON sh3_replay_claims(lease_expires_at)"
        )
        assert connection.in_transaction
        assert _read_user_version(connection) == marker
        assert _has_index(connection, probe_index)

        for _ in range(_COLLISION_ATTEMPTS):
            connection.execute(f"SAVEPOINT {_SAVEPOINT}")
            connection.execute(f"PRAGMA user_version = {inner_marker}")
            with pytest.raises(sqlite3.OperationalError, match="already exists") as exc:
                connection.execute(
                    f"CREATE INDEX {_REQUIRED_INDEX} "
                    "ON sh3_replay_claims(lease_expires_at, state)"
                )
            messages.append(str(exc.value))
            assert connection.in_transaction
            assert _read_user_version(connection) == inner_marker
            connection.execute(f"ROLLBACK TO SAVEPOINT {_SAVEPOINT}")
            connection.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
            assert connection.in_transaction
            assert _read_user_version(connection) == marker
            assert _has_index(connection, probe_index)
            assert _index_definition_from_connection(connection) == (
                "sh3_replay_claims",
                False,
                False,
                ("state", "lease_expires_at"),
            )

        assert len(messages) == _COLLISION_ATTEMPTS
        assert len(set(messages)) == 1
        connection.execute("COMMIT")
        assert not connection.in_transaction
        return tuple(messages)
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def _checkpoint(database: Path, mode: str) -> tuple[int, int, int]:
    connection = sqlite3.connect(database, timeout=0.0, isolation_level=None)
    try:
        row = connection.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
        assert row is not None
        assert len(row) == 3
        result = (int(row[0]), int(row[1]), int(row[2]))
        if mode == "TRUNCATE":
            assert result == (0, 0, 0)
        else:
            assert result[0] == 0
            assert result[1] == result[2]
        return result
    finally:
        connection.close()


def _report_json(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_published_wal_snapshot_isolated_from_source_checkpoints_and_writes(
    tmp_path: Path,
    scenario: str,
) -> None:
    source = tmp_path / f"part11-109-{scenario}-source.sqlite3"
    snapshot = tmp_path / f"part11-109-{scenario}-snapshot.sqlite3"
    working = tmp_path / f"part11-109-{scenario}-working.sqlite3"
    verification_restore = tmp_path / f"part11-109-{scenario}-verification.sqlite3"
    _initialize_database(source)
    _set_wal_mode(source)

    initial_report = replay_ops.check_database(source)
    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    assert initial_report.journal_mode.casefold() == "wal"
    assert _index_definition(source) == canonical_definition
    initial_marker = _read_user_version_from_database(source)
    replay_ops.backup_database(source, snapshot)
    protected_paths: tuple[Path, ...]
    if scenario == "backup-destination":
        working = source
        protected_paths = (snapshot,)
    else:
        replay_ops.restore_database(snapshot, working)
        _set_wal_mode(working)
        protected_paths = (source, snapshot)

    working_report = replay_ops.check_database(working)
    assert working_report.journal_mode.casefold() == "wal"
    assert working_report.evidence_count == initial_report.evidence_count
    assert working_report.replay_claim_count == initial_report.replay_claim_count
    assert _index_definition(working) == canonical_definition
    assert _read_user_version_from_database(working) == initial_marker
    snapshot_bytes = snapshot.read_bytes()
    baseline_working_report = replay_ops.check_database(working)
    protected_bytes = {path: path.read_bytes() for path in protected_paths}

    residual_prefix = f".{snapshot.name}.part11-109."
    residual_contents = {
        tmp_path / f"{residual_prefix}partial": b"snapshot isolation partial residue",
        tmp_path / f"{residual_prefix}partial-wal": b"snapshot isolation WAL residue",
        tmp_path / f"{residual_prefix}partial-shm": b"snapshot isolation SHM residue",
        tmp_path / f"{residual_prefix}partial-journal": (
            b"snapshot isolation journal residue"
        ),
    }
    for path, contents in residual_contents.items():
        path.write_bytes(contents)
    residual_names = _residual_artifacts(tmp_path, snapshot)
    assert residual_names == tuple(sorted(path.name for path in residual_contents))

    markers = (
        (initial_marker + _MARKER_DELTA) % _MAX_USER_VERSION,
        (initial_marker + 2 * _MARKER_DELTA) % _MAX_USER_VERSION,
    )
    assert initial_marker not in markers
    assert markers[0] != markers[1]
    for epoch, marker in enumerate(markers, start=1):
        collision_messages = _run_write_epoch(working, marker=marker, epoch=epoch)
        assert len(set(collision_messages)) == 1
        assert _read_user_version_from_database(working) == marker
        assert _has_index_for_database(working, _PROBE_INDEXES[epoch - 1])
        assert _index_definition(working) == canonical_definition

        for mode in _CHECKPOINT_SEQUENCES[epoch - 1]:
            result = _checkpoint(working, mode)
            if mode == "TRUNCATE":
                wal_path = Path(f"{working}-wal")
                if wal_path.exists():
                    assert wal_path.stat().st_size == 0
            assert result[0] == 0
            assert snapshot.read_bytes() == snapshot_bytes
            current_protected_bytes = {
                path: path.read_bytes() for path in protected_paths
            }
            assert current_protected_bytes == protected_bytes
            assert _residual_artifacts(tmp_path, snapshot) == residual_names
            for path, contents in residual_contents.items():
                assert path.is_file()
                assert path.read_bytes() == contents
            assert _index_definition(working) == canonical_definition
            assert _read_user_version_from_database(working) == marker
            assert replay_ops.check_database(working) == baseline_working_report

    restored = replay_ops.restore_database(snapshot, verification_restore)
    assert restored.database_path == verification_restore.resolve()
    assert restored.evidence_count == initial_report.evidence_count
    assert restored.replay_claim_count == initial_report.replay_claim_count
    assert _read_user_version_from_database(verification_restore) == initial_marker
    assert _index_definition(verification_restore) == canonical_definition
    for probe_index in _PROBE_INDEXES:
        assert not _has_index_for_database(verification_restore, probe_index)
    assert snapshot.read_bytes() == snapshot_bytes
    assert {path: path.read_bytes() for path in protected_paths} == protected_bytes

    stable_report = replay_ops.check_database(working)
    expected_json = {
        "schema_version": 1,
        "action": "check",
        "database": str(working.resolve()),
        "sqlite_version": stable_report.sqlite_version,
        "journal_mode": stable_report.journal_mode,
        "integrity_status": "pass",
        "evidence_records": stable_report.evidence_count,
        "replay_claims": stable_report.replay_claim_count,
        "expired_claims": stable_report.expired_claim_count,
        "pending_evidence_reconciliation": (
            stable_report.pending_evidence_reconciliation_count
        ),
        "policy_gates": {},
        "exit_code": 0,
    }
    project_root = Path(__file__).resolve().parents[3]
    cli_reports: list[dict[str, Any]] = []
    for _ in range(2):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "infrastructure.security.persistent_replay_ops",
                "check",
                "--database",
                str(working),
                "--json",
            ],
            cwd=project_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=15,
        )
        assert process.returncode == 0
        assert process.stderr == ""
        report = _report_json(process.stdout)
        assert report == expected_json
        cli_reports.append(report)
        assert snapshot.read_bytes() == snapshot_bytes
        assert {path: path.read_bytes() for path in protected_paths} == protected_bytes
    assert cli_reports[0] == cli_reports[1]


def _has_index_for_database(database: Path, index_name: str) -> bool:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro", uri=True, isolation_level=None
    )
    try:
        return _has_index(connection, index_name)
    finally:
        connection.close()
