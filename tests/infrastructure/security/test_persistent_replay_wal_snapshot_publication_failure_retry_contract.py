from __future__ import annotations

import json
import os
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
_PROBE_INDEX = "sh3_replay_part11_113_publication_probe_idx"
_BASELINE_USER_VERSION = 113_000
_RESIDUAL_TAG = "part11-113"
_CANONICAL_INDEX = (
    "sh3_replay_claims",
    False,
    False,
    ("state", "lease_expires_at"),
)


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        mode_row = connection.execute("PRAGMA journal_mode = WAL").fetchone()
        assert mode_row is not None
        assert str(mode_row[0]).casefold() == "wal"
        connection.execute(f"PRAGMA user_version = {_BASELINE_USER_VERSION}")
        connection.execute(
            f"CREATE INDEX {_PROBE_INDEX} ON sh3_replay_claims(state)"
        )
    finally:
        connection.close()


def _database_artifact_bytes(database: Path) -> dict[Path, bytes]:
    sidecars = tuple(
        Path(f"{database}{suffix}") for suffix in ("-wal", "-shm", "-journal")
    )
    artifacts = (database, *sidecars)
    return {path: path.read_bytes() for path in artifacts if path.is_file()}


def _capture_database_artifacts(databases: tuple[Path, ...]) -> dict[Path, bytes]:
    contents: dict[Path, bytes] = {}
    for database in databases:
        contents.update(_database_artifact_bytes(database))
    return contents


def _assert_artifacts_unchanged(expected: dict[Path, bytes]) -> None:
    for path, expected_bytes in expected.items():
        assert path.is_file()
        assert path.read_bytes() == expected_bytes


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


def _matching_partial_artifacts(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


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
    database_bytes = _database_artifact_bytes(database)
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
        _assert_artifacts_unchanged(database_bytes)
        reports.append(report)
    assert reports[0] == reports[1]


def _run_snapshot_operation(
    scenario: str,
    source: Path,
    backup: Path,
    destination: Path,
) -> replay_ops.DatabaseReadinessReport:
    if scenario == "backup-destination":
        return replay_ops.backup_database(source, destination)
    return replay_ops.restore_database(backup, destination)


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_wal_snapshot_publication_failure_cleans_temporary_state_and_retry_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"publication-failure-{scenario}-source.sqlite3"
    backup = tmp_path / f"publication-failure-{scenario}-backup.sqlite3"
    destination = tmp_path / f"publication-failure-{scenario}-destination.sqlite3"
    _initialize_database(source)
    protected_databases: tuple[Path, ...]
    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup)
        protected_databases = (source, backup)
    else:
        protected_databases = (source,)

    protected_bytes = _capture_database_artifacts(protected_databases)
    canonical_definition = _CANONICAL_INDEX
    assert _read_user_version(source) == _BASELINE_USER_VERSION
    assert _index_definition(source) == canonical_definition
    assert _has_index(source, _PROBE_INDEX)
    if scenario == "restore-destination":
        assert _read_user_version(backup) == _BASELINE_USER_VERSION
        assert _index_definition(backup) == canonical_definition
        assert _has_index(backup, _PROBE_INDEX)

    sentinel = tmp_path / f".{destination.name}.{_RESIDUAL_TAG}.partial"
    residual_contents = {
        sentinel: b"part11-113 publication-failure residue",
        Path(f"{sentinel}-wal"): b"part11-113 publication-failure WAL residue",
        Path(f"{sentinel}-shm"): b"part11-113 publication-failure SHM residue",
        Path(f"{sentinel}-journal"): b"part11-113 publication-failure journal residue",
    }
    for path, contents in residual_contents.items():
        path.write_bytes(contents)
    partial_names_before = _matching_partial_artifacts(tmp_path, destination)
    assert partial_names_before == tuple(
        sorted(path.name for path in residual_contents)
    )

    original_link = os.link
    publication_attempts = 0

    def fail_first_publication(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        nonlocal publication_attempts
        if Path(destination_path) == destination and publication_attempts == 0:
            publication_attempts += 1
            raise OSError("injected one-shot snapshot publication failure")
        original_link(source_path, destination_path)

    with monkeypatch.context() as patch:
        patch.setattr(os, "link", fail_first_publication)
        with pytest.raises(
            replay_ops.PersistentReplayReadinessError,
            match="could not publish the verified snapshot",
        ):
            _run_snapshot_operation(scenario, source, backup, destination)

    assert publication_attempts == 1
    assert not destination.exists()
    assert _matching_partial_artifacts(tmp_path, destination) == partial_names_before
    _assert_artifacts_unchanged(residual_contents)
    _assert_artifacts_unchanged(protected_bytes)

    result = _run_snapshot_operation(scenario, source, backup, destination)
    assert result.database_path == destination.resolve()
    assert result.journal_mode.casefold() == "wal"
    assert _read_user_version(destination) == _BASELINE_USER_VERSION
    assert _index_definition(destination) == canonical_definition
    assert _has_index(destination, _PROBE_INDEX)
    assert _has_index(destination, _REQUIRED_INDEX)
    assert _matching_partial_artifacts(tmp_path, destination) == partial_names_before
    _assert_artifacts_unchanged(residual_contents)
    _assert_artifacts_unchanged(protected_bytes)

    destination_readiness = replay_ops.check_database(destination)
    assert destination_readiness.evidence_count == result.evidence_count
    assert destination_readiness.replay_claim_count == result.replay_claim_count
    _assert_cli_readiness_is_stable(destination)
    _assert_artifacts_unchanged(protected_bytes)
    _assert_artifacts_unchanged(residual_contents)
