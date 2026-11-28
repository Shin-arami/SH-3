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
_DECOY_TABLE = "sh3_replay_claims_decoy"


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


def _move_required_index_to_decoy_table(database: Path) -> None:
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        connection.execute(f"DROP INDEX IF EXISTS {_REQUIRED_INDEX}")
        connection.execute(
            f"CREATE TABLE {_DECOY_TABLE} "
            "(state TEXT, lease_expires_at INTEGER)"
        )
        connection.execute(
            f"CREATE INDEX {_REQUIRED_INDEX} "
            f"ON {_DECOY_TABLE}(state, lease_expires_at)"
        )
        checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        assert checkpoint is not None
        assert int(checkpoint[0]) == 0
    finally:
        connection.close()


def _index_owner_and_columns(database: Path) -> tuple[str, tuple[str, ...]]:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
        isolation_level=None,
    )
    try:
        row = connection.execute(
            "SELECT tbl_name FROM sqlite_master "
            "WHERE type = 'index' AND name = ?",
            (_REQUIRED_INDEX,),
        ).fetchone()
        assert row is not None
        owner = str(row[0])
        columns = connection.execute(
            f"PRAGMA index_info({_REQUIRED_INDEX})"
        ).fetchall()
        return owner, tuple(str(column[2]) for column in columns)
    finally:
        connection.close()


def _repair_required_index_ownership(database: Path) -> None:
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        connection.execute(f"DROP INDEX IF EXISTS {_REQUIRED_INDEX}")
        connection.execute(f"DROP TABLE IF EXISTS {_DECOY_TABLE}")
        connection.execute(
            f"CREATE INDEX {_REQUIRED_INDEX} "
            "ON sh3_replay_claims(state, lease_expires_at)"
        )
        checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        assert checkpoint is not None
        assert int(checkpoint[0]) == 0
    finally:
        connection.close()


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_required_replay_index_on_wrong_table_remains_rejected_until_explicit_repair(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"misplaced-index-{scenario}-source.sqlite3"
    backup = tmp_path / f"misplaced-index-{scenario}-backup.sqlite3"
    destination = tmp_path / f"misplaced-index-{scenario}-destination.sqlite3"
    _initialize_database(source)
    protected_sources = _prepare_destination(
        source,
        backup,
        destination,
        scenario=scenario,
    )
    source_bytes_before = {path: path.read_bytes() for path in protected_sources}
    healthy_readiness = replay_ops.check_database(destination)

    temporary_main = (
        tmp_path / f".{destination.name}.part11-76-misplaced-index.partial"
    )
    residual_contents = {
        temporary_main: b"misplaced-index temporary snapshot body",
        Path(f"{temporary_main}-wal"): b"misplaced-index WAL residue",
        Path(f"{temporary_main}-shm"): b"misplaced-index SHM residue",
        Path(f"{temporary_main}-journal"): b"misplaced-index journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    # Model interrupted repair: the canonical index name still exists and its
    # key columns match, but it belongs to a decoy table, not replay claims.
    _move_required_index_to_decoy_table(destination)
    invalid_destination_bytes = destination.read_bytes()
    assert _index_owner_and_columns(destination) == (
        _DECOY_TABLE,
        ("state", "lease_expires_at"),
    )

    failed_reports: list[dict[str, Any]] = []
    failed_diagnostics: list[str] = []
    for _ in range(3):
        exit_code = replay_ops.main(
            ["check", "--database", str(destination), "--json"]
        )
        captured = capsys.readouterr()

        assert exit_code == 1
        assert captured.out.count("\n") == 1
        report = _read_report(captured.out)
        assert report == {
            "schema_version": 1,
            "action": "check",
            "integrity_status": "error",
            "policy_gates": {},
            "error": {
                "code": "readiness_check_failed",
                "type": "PersistentReplayReadinessError",
            },
            "exit_code": 1,
        }
        assert f"missing required index {_REQUIRED_INDEX}" in captured.err
        captured_text = captured.out + captured.err
        assert str(destination) not in captured_text
        for protected_source in protected_sources:
            assert str(protected_source) not in captured_text
            assert protected_source.read_bytes() == source_bytes_before[protected_source]

        # The readiness check is observational: no automatic index relocation,
        # schema modification, or residual-artifact cleanup is allowed.
        assert _index_owner_and_columns(destination) == (
            _DECOY_TABLE,
            ("state", "lease_expires_at"),
        )
        assert destination.read_bytes() == invalid_destination_bytes
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        failed_reports.append(report)
        failed_diagnostics.append(captured.err)

    assert failed_reports[0] == failed_reports[1] == failed_reports[2]
    assert failed_diagnostics[0] == failed_diagnostics[1] == failed_diagnostics[2]

    # Only explicit repair moves the index back to the intended table.
    _repair_required_index_ownership(destination)
    repaired_destination_bytes = destination.read_bytes()
    assert _index_owner_and_columns(destination) == (
        "sh3_replay_claims",
        ("state", "lease_expires_at"),
    )
    repaired_readiness = replay_ops.check_database(destination)
    assert repaired_readiness.evidence_count == healthy_readiness.evidence_count
    assert repaired_readiness.replay_claim_count == healthy_readiness.replay_claim_count
    assert repaired_readiness.journal_mode == healthy_readiness.journal_mode

    success_reports: list[dict[str, Any]] = []
    for _ in range(2):
        exit_code = replay_ops.main(
            ["check", "--database", str(destination), "--json"]
        )
        captured = capsys.readouterr()

        assert exit_code == 0
        assert captured.out.count("\n") == 1
        assert captured.err == ""
        report = _read_report(captured.out)
        assert report == {
            "schema_version": 1,
            "action": "check",
            "database": str(destination.resolve()),
            "sqlite_version": repaired_readiness.sqlite_version,
            "journal_mode": repaired_readiness.journal_mode,
            "integrity_status": "pass",
            "evidence_records": repaired_readiness.evidence_count,
            "replay_claims": repaired_readiness.replay_claim_count,
            "expired_claims": repaired_readiness.expired_claim_count,
            "pending_evidence_reconciliation": (
                repaired_readiness.pending_evidence_reconciliation_count
            ),
            "policy_gates": {},
            "exit_code": 0,
        }
        assert _index_owner_and_columns(destination) == (
            "sh3_replay_claims",
            ("state", "lease_expires_at"),
        )
        assert destination.read_bytes() == repaired_destination_bytes
        for protected_source in protected_sources:
            assert protected_source.read_bytes() == source_bytes_before[protected_source]
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        success_reports.append(report)

    assert success_reports[0] == success_reports[1]
