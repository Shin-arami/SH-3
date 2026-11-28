from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)

_REQUIRED_INDEX = "sh3_replay_claims_state_idx"
_BASELINE_USER_VERSION = 112_000
_RESIDUAL_TAG = "part11-112"
_CANONICAL_INDEX = (
    "sh3_replay_claims",
    False,
    False,
    ("state", "lease_expires_at"),
)


@dataclass(frozen=True, slots=True)
class _SnapshotFixture:
    source: Path
    snapshot: Path
    protected_copy: Path
    source_bytes: bytes
    snapshot_bytes: bytes
    protected_copy_bytes: bytes
    snapshot_report: replay_ops.DatabaseReadinessReport


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        connection.execute(f"PRAGMA user_version = {_BASELINE_USER_VERSION}")
        mode_row = connection.execute("PRAGMA journal_mode = WAL").fetchone()
        assert mode_row is not None
        assert str(mode_row[0]).casefold() == "wal"
    finally:
        connection.close()


def _read_user_version(database: Path) -> int:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro", uri=True, isolation_level=None
    )
    try:
        row = connection.execute("PRAGMA user_version").fetchone()
        assert row is not None
        return int(row[0])
    finally:
        connection.close()


def _has_index(database: Path, index_name: str) -> bool:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro", uri=True, isolation_level=None
    )
    try:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
                (index_name,),
            ).fetchone()
            is not None
        )
    finally:
        connection.close()


def _index_definition(database: Path) -> tuple[str, bool, bool, tuple[str, ...]]:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro", uri=True, isolation_level=None
    )
    try:
        owner_row = connection.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type = 'index' AND name = ?",
            (_REQUIRED_INDEX,),
        ).fetchone()
        assert owner_row is not None
        index_row = next(
            row
            for row in connection.execute(
                "PRAGMA index_list(sh3_replay_claims)"
            ).fetchall()
            if str(row[1]) == _REQUIRED_INDEX
        )
        column_rows = connection.execute(
            f"PRAGMA index_info({_REQUIRED_INDEX})"
        ).fetchall()
        return (
            str(owner_row[0]),
            bool(index_row[2]),
            bool(index_row[4]),
            tuple(str(row[2]) for row in column_rows),
        )
    finally:
        connection.close()


def _prepare_snapshot_fixture(directory: Path, prefix: str) -> _SnapshotFixture:
    source = directory / f"{prefix}-source.sqlite3"
    snapshot = directory / f"{prefix}-snapshot.sqlite3"
    protected_copy = directory / f"{prefix}-protected-copy.sqlite3"
    _initialize_database(source)
    source_report = replay_ops.check_database(source)
    snapshot_report = replay_ops.backup_database(source, snapshot)
    restored_report = replay_ops.restore_database(snapshot, protected_copy)
    assert restored_report.evidence_count == source_report.evidence_count
    assert restored_report.replay_claim_count == source_report.replay_claim_count
    assert _read_user_version(snapshot) == _BASELINE_USER_VERSION
    assert _read_user_version(protected_copy) == _BASELINE_USER_VERSION
    assert _index_definition(snapshot) == _CANONICAL_INDEX
    assert _index_definition(protected_copy) == _CANONICAL_INDEX
    return _SnapshotFixture(
        source=source,
        snapshot=snapshot,
        protected_copy=protected_copy,
        source_bytes=source.read_bytes(),
        snapshot_bytes=snapshot.read_bytes(),
        protected_copy_bytes=protected_copy.read_bytes(),
        snapshot_report=snapshot_report,
    )


def _create_residual_artifacts(
    directory: Path, destination: Path
) -> dict[Path, bytes]:
    prefix = f".{destination.name}.{_RESIDUAL_TAG}"
    contents = {
        directory / f"{prefix}.partial": b"part11-112 failed restore residue",
        directory / f"{prefix}.partial-wal": b"part11-112 failed restore WAL residue",
        directory / f"{prefix}.partial-shm": b"part11-112 failed restore SHM residue",
        directory / f"{prefix}.partial-journal": (
            b"part11-112 failed restore journal residue"
        ),
    }
    for path, data in contents.items():
        path.write_bytes(data)
    return contents


def _assert_residual_artifacts(artifacts: dict[Path, bytes]) -> None:
    for path, expected_bytes in artifacts.items():
        assert path.is_file()
        assert path.read_bytes() == expected_bytes


def _assert_snapshot_fixture_unchanged(fixture: _SnapshotFixture) -> None:
    assert fixture.source.read_bytes() == fixture.source_bytes
    assert fixture.snapshot.read_bytes() == fixture.snapshot_bytes
    assert fixture.protected_copy.read_bytes() == fixture.protected_copy_bytes
    assert _read_user_version(fixture.source) == _BASELINE_USER_VERSION
    assert _read_user_version(fixture.snapshot) == _BASELINE_USER_VERSION
    assert _read_user_version(fixture.protected_copy) == _BASELINE_USER_VERSION
    assert _index_definition(fixture.source) == _CANONICAL_INDEX
    assert _index_definition(fixture.snapshot) == _CANONICAL_INDEX
    assert _index_definition(fixture.protected_copy) == _CANONICAL_INDEX


def _assert_cli_readiness_is_stable(database: Path) -> None:
    readiness = replay_ops.check_database(database)
    expected_json: dict[str, object] = {
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
    project_root = Path(__file__).resolve().parents[3]
    database_bytes = database.read_bytes()
    reports: list[dict[str, Any]] = []
    for _ in range(2):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "infrastructure.security.persistent_replay_ops",
                "check",
                "--database",
                str(database),
                "--json",
            ],
            cwd=project_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=20,
        )
        assert process.returncode == 0
        assert process.stderr == ""
        assert process.stdout.count("\n") == 1
        report = json.loads(process.stdout)
        assert isinstance(report, dict)
        assert report == expected_json
        assert database.read_bytes() == database_bytes
        reports.append(report)
    assert reports[0] == reports[1]


def _damage_snapshot_by_removing_required_index(snapshot: Path, damaged: Path) -> bytes:
    shutil.copyfile(snapshot, damaged)
    connection = sqlite3.connect(damaged, isolation_level=None)
    try:
        connection.execute(f"DROP INDEX {_REQUIRED_INDEX}")
    finally:
        connection.close()
    damaged_bytes = damaged.read_bytes()
    assert not _has_index(damaged, _REQUIRED_INDEX)
    return damaged_bytes


def test_invalid_snapshot_restore_failure_isolated_and_valid_retry_succeeds(
    tmp_path: Path,
) -> None:
    fixture = _prepare_snapshot_fixture(tmp_path, "invalid-snapshot")
    invalid_snapshot = tmp_path / "invalid-snapshot-missing-index.sqlite3"
    invalid_snapshot_bytes = _damage_snapshot_by_removing_required_index(
        fixture.snapshot, invalid_snapshot
    )
    destination = tmp_path / "invalid-snapshot-retry-destination.sqlite3"
    residual_artifacts = _create_residual_artifacts(tmp_path, destination)

    with pytest.raises(
        replay_ops.PersistentReplayReadinessError,
        match="missing required index sh3_replay_claims_state_idx",
    ):
        replay_ops.restore_database(invalid_snapshot, destination)

    assert not destination.exists()
    assert invalid_snapshot.read_bytes() == invalid_snapshot_bytes
    _assert_snapshot_fixture_unchanged(fixture)
    _assert_residual_artifacts(residual_artifacts)

    restored_report = replay_ops.restore_database(fixture.snapshot, destination)
    assert restored_report.database_path == destination.resolve()
    assert restored_report.evidence_count == fixture.snapshot_report.evidence_count
    assert (
        restored_report.replay_claim_count
        == fixture.snapshot_report.replay_claim_count
    )
    assert _read_user_version(destination) == _BASELINE_USER_VERSION
    assert _index_definition(destination) == _CANONICAL_INDEX
    assert _has_index(destination, _REQUIRED_INDEX)
    _assert_snapshot_fixture_unchanged(fixture)
    _assert_residual_artifacts(residual_artifacts)
    _assert_cli_readiness_is_stable(destination)
    _assert_snapshot_fixture_unchanged(fixture)
    _assert_residual_artifacts(residual_artifacts)


def test_existing_destination_collision_preserves_copy_and_later_restore_succeeds(
    tmp_path: Path,
) -> None:
    fixture = _prepare_snapshot_fixture(tmp_path, "destination-collision")
    destination = tmp_path / "destination-collision-existing.sqlite3"
    initial_restore = replay_ops.restore_database(fixture.snapshot, destination)
    assert initial_restore.database_path == destination.resolve()
    destination_bytes = destination.read_bytes()
    residual_artifacts = _create_residual_artifacts(tmp_path, destination)

    with pytest.raises(
        FileExistsError, match="refusing to overwrite existing destination"
    ):
        replay_ops.restore_database(fixture.snapshot, destination)

    assert destination.read_bytes() == destination_bytes
    assert _read_user_version(destination) == _BASELINE_USER_VERSION
    assert _index_definition(destination) == _CANONICAL_INDEX
    _assert_snapshot_fixture_unchanged(fixture)
    _assert_residual_artifacts(residual_artifacts)

    retry_destination = tmp_path / "destination-collision-retry.sqlite3"
    retry_report = replay_ops.restore_database(fixture.snapshot, retry_destination)
    assert retry_report.database_path == retry_destination.resolve()
    assert retry_report.evidence_count == fixture.snapshot_report.evidence_count
    assert (
        retry_report.replay_claim_count
        == fixture.snapshot_report.replay_claim_count
    )
    assert _read_user_version(retry_destination) == _BASELINE_USER_VERSION
    assert _index_definition(retry_destination) == _CANONICAL_INDEX
    assert destination.read_bytes() == destination_bytes
    assert _read_user_version(destination) == _BASELINE_USER_VERSION
    assert _index_definition(destination) == _CANONICAL_INDEX
    _assert_snapshot_fixture_unchanged(fixture)
    _assert_residual_artifacts(residual_artifacts)
    _assert_cli_readiness_is_stable(retry_destination)
    assert destination.read_bytes() == destination_bytes
    _assert_snapshot_fixture_unchanged(fixture)
    _assert_residual_artifacts(residual_artifacts)
