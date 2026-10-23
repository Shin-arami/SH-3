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
    "sh3_replay_claims_part11_111_copy_one_idx",
    "sh3_replay_claims_part11_111_copy_two_idx",
    "sh3_replay_claims_part11_111_copy_three_idx",
)
_SAVEPOINT = "part11_111_restore_collision_scope"
_COLLISION_ATTEMPTS = 3
_MARKER_DELTA = 11_110
_INNER_MARKER_DELTA = 11_111
_MAX_USER_VERSION = 2_147_483_647
_CHECKPOINT_SEQUENCES = (
    ("PASSIVE", "FULL", "RESTART", "TRUNCATE"),
    ("TRUNCATE", "RESTART", "FULL", "PASSIVE"),
    ("FULL", "TRUNCATE", "PASSIVE", "RESTART"),
)
_CANONICAL_INDEX = (
    "sh3_replay_claims",
    False,
    False,
    ("state", "lease_expires_at"),
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


def _has_index_in_database(database: Path, name: str) -> bool:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro", uri=True, isolation_level=None
    )
    try:
        return _has_index(connection, name)
    finally:
        connection.close()


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
    prefix = f".{snapshot.name}.part11-111."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix)
        )
    )


def _run_write_epoch(
    database: Path, *, marker: int, probe_index: str
) -> tuple[str, ...]:
    inner_marker = (marker + _INNER_MARKER_DELTA) % _MAX_USER_VERSION
    assert marker != inner_marker
    messages: list[str] = []
    connection = sqlite3.connect(database, timeout=0.0, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(f"PRAGMA user_version = {marker}")
        connection.execute(
            f"CREATE INDEX {probe_index} ON sh3_replay_claims(lease_expires_at)"
        )
        assert connection.in_transaction
        assert _read_user_version(connection) == marker
        assert _has_index(connection, probe_index)
        assert _index_definition_from_connection(connection) == _CANONICAL_INDEX

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
            assert _index_definition_from_connection(connection) == _CANONICAL_INDEX

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
        result = tuple(int(value) for value in row)
        if mode == "TRUNCATE":
            assert result == (0, 0, 0)
        else:
            assert result[0] == 0
            assert result[1] == result[2]
        return (result[0], result[1], result[2])
    finally:
        connection.close()


def _report_json(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _assert_restored_baseline(
    database: Path,
    *,
    expected_marker: int,
    expected_evidence_count: int,
    expected_claim_count: int,
    sqlite_version: str,
) -> None:
    report = replay_ops.check_database(database)
    assert report.journal_mode.casefold() == "wal"
    assert report.sqlite_version == sqlite_version
    assert report.evidence_count == expected_evidence_count
    assert report.replay_claim_count == expected_claim_count
    assert _read_user_version_from_database(database) == expected_marker
    assert _index_definition(database) == _CANONICAL_INDEX
    for probe_index in _PROBE_INDEXES:
        assert not _has_index_in_database(database, probe_index)


@pytest.mark.parametrize(
    "scenario",
    ("direct-source", "restored-source"),
    ids=("direct-source", "restored-source"),
)
def test_wal_snapshot_is_immutable_across_repeated_restore_and_mutated_copies(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"part11-111-{scenario}-source.sqlite3"
    seed_snapshot = tmp_path / f"part11-111-{scenario}-seed-snapshot.sqlite3"
    restored_snapshot_source = (
        tmp_path / f"part11-111-{scenario}-snapshot-source.sqlite3"
    )
    immutable_snapshot = tmp_path / f"part11-111-{scenario}-immutable.sqlite3"
    working_copies = tuple(
        tmp_path / f"part11-111-{scenario}-working-{index}.sqlite3"
        for index in range(1, 5)
    )
    _initialize_database(source)
    _set_wal_mode(source)
    initial_report = replay_ops.check_database(source)
    initial_marker = _read_user_version_from_database(source)
    assert initial_report.journal_mode.casefold() == "wal"
    assert _index_definition(source) == _CANONICAL_INDEX

    protected_paths: tuple[Path, ...]
    if scenario == "direct-source":
        snapshot_source = source
        protected_paths = (source,)
    else:
        seed_report = replay_ops.backup_database(source, seed_snapshot)
        assert seed_report.database_path == seed_snapshot.resolve()
        replay_ops.restore_database(seed_snapshot, restored_snapshot_source)
        _set_wal_mode(restored_snapshot_source)
        snapshot_source = restored_snapshot_source
        protected_paths = (source, seed_snapshot, restored_snapshot_source)

    immutable_report = replay_ops.backup_database(snapshot_source, immutable_snapshot)
    assert immutable_report.database_path == immutable_snapshot.resolve()
    assert immutable_report.evidence_count == initial_report.evidence_count
    assert immutable_report.replay_claim_count == initial_report.replay_claim_count
    assert _read_user_version_from_database(immutable_snapshot) == initial_marker
    assert _index_definition(immutable_snapshot) == _CANONICAL_INDEX
    immutable_bytes = immutable_snapshot.read_bytes()
    protected_paths = (*protected_paths, immutable_snapshot)
    protected_bytes = {path: path.read_bytes() for path in protected_paths}

    residual_prefix = f".{immutable_snapshot.name}.part11-111."
    residual_contents = {
        tmp_path / f"{residual_prefix}partial": b"restore isolation partial residue",
        tmp_path / f"{residual_prefix}partial-wal": b"restore isolation WAL residue",
        tmp_path / f"{residual_prefix}partial-shm": b"restore isolation SHM residue",
        tmp_path / f"{residual_prefix}partial-journal": (
            b"restore isolation journal residue"
        ),
    }
    for path, contents in residual_contents.items():
        path.write_bytes(contents)
    residual_names = _residual_artifacts(tmp_path, immutable_snapshot)
    assert residual_names == tuple(sorted(path.name for path in residual_contents))

    marker_one = (initial_marker + _MARKER_DELTA) % _MAX_USER_VERSION
    marker_two = (initial_marker + 2 * _MARKER_DELTA) % _MAX_USER_VERSION
    marker_three = (initial_marker + 3 * _MARKER_DELTA) % _MAX_USER_VERSION
    for marker in (marker_one, marker_two, marker_three):
        assert marker != initial_marker
    assert len({initial_marker, marker_one, marker_two, marker_three}) == 4

    for index, (working_copy, marker) in enumerate(
        zip(working_copies[:2], (marker_one, marker_two), strict=True)
    ):
        restore_report = replay_ops.restore_database(immutable_snapshot, working_copy)
        assert restore_report.database_path == working_copy.resolve()
        _set_wal_mode(working_copy)
        _assert_restored_baseline(
            working_copy,
            expected_marker=initial_marker,
            expected_evidence_count=initial_report.evidence_count,
            expected_claim_count=initial_report.replay_claim_count,
            sqlite_version=initial_report.sqlite_version,
        )
        collision_messages = _run_write_epoch(
            working_copy,
            marker=marker,
            probe_index=_PROBE_INDEXES[index],
        )
        assert len(set(collision_messages)) == 1
        assert _read_user_version_from_database(working_copy) == marker
        assert _has_index_in_database(working_copy, _PROBE_INDEXES[index])
        for mode in _CHECKPOINT_SEQUENCES[index]:
            result = _checkpoint(working_copy, mode)
            assert result[0] == 0
            if mode == "TRUNCATE":
                wal_path = Path(f"{working_copy}-wal")
                if wal_path.exists():
                    assert wal_path.stat().st_size == 0
            assert _read_user_version_from_database(working_copy) == marker
            assert _index_definition(working_copy) == _CANONICAL_INDEX
            assert immutable_snapshot.read_bytes() == immutable_bytes
            assert (
                {path: path.read_bytes() for path in protected_paths}
                == protected_bytes
            )
            assert _residual_artifacts(tmp_path, immutable_snapshot) == residual_names
            for path, contents in residual_contents.items():
                assert path.is_file()
                assert path.read_bytes() == contents

    # Reuse the same immutable snapshot after both independent working copies
    # have been changed and checkpointed; neither mutation may leak into it.
    for working_copy in working_copies[2:]:
        restore_report = replay_ops.restore_database(immutable_snapshot, working_copy)
        assert restore_report.database_path == working_copy.resolve()
        _set_wal_mode(working_copy)
        _assert_restored_baseline(
            working_copy,
            expected_marker=initial_marker,
            expected_evidence_count=initial_report.evidence_count,
            expected_claim_count=initial_report.replay_claim_count,
            sqlite_version=initial_report.sqlite_version,
        )
        assert immutable_snapshot.read_bytes() == immutable_bytes
        assert (
            {path: path.read_bytes() for path in protected_paths}
            == protected_bytes
        )

    # The third working copy is independently mutated after restore, followed
    # by a fourth restore to prove that a later restore still yields baseline.
    _run_write_epoch(
        working_copies[2], marker=marker_three, probe_index=_PROBE_INDEXES[2]
    )
    for mode in _CHECKPOINT_SEQUENCES[2]:
        assert _checkpoint(working_copies[2], mode)[0] == 0
        assert immutable_snapshot.read_bytes() == immutable_bytes
        assert (
            {path: path.read_bytes() for path in protected_paths}
            == protected_bytes
        )
    _assert_restored_baseline(
        working_copies[3],
        expected_marker=initial_marker,
        expected_evidence_count=initial_report.evidence_count,
        expected_claim_count=initial_report.replay_claim_count,
        sqlite_version=initial_report.sqlite_version,
    )
    assert immutable_snapshot.read_bytes() == immutable_bytes
    assert (
        {path: path.read_bytes() for path in protected_paths}
        == protected_bytes
    )
    assert _residual_artifacts(tmp_path, immutable_snapshot) == residual_names
    for path, contents in residual_contents.items():
        assert path.is_file()
        assert path.read_bytes() == contents

    stable_report = replay_ops.check_database(working_copies[3])
    expected_json: dict[str, object] = {
        "schema_version": 1,
        "action": "check",
        "database": str(working_copies[3].resolve()),
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
    reports: list[dict[str, Any]] = []
    for _ in range(2):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "infrastructure.security.persistent_replay_ops",
                "check",
                "--database",
                str(working_copies[3]),
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
        reports.append(report)
        assert immutable_snapshot.read_bytes() == immutable_bytes
        assert (
            {path: path.read_bytes() for path in protected_paths}
            == protected_bytes
        )
    assert reports[0] == reports[1]
