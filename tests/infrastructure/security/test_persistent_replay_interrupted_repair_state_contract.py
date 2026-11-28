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


def _replace_claim_state_index(database: Path, columns: tuple[str, str]) -> None:
    assert columns in {
        ("state", "lease_expires_at"),
        ("lease_expires_at", "state"),
    }
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        connection.execute("DROP INDEX IF EXISTS sh3_replay_claims_state_idx")
        connection.execute(
            "CREATE INDEX sh3_replay_claims_state_idx "
            f"ON sh3_replay_claims({columns[0]}, {columns[1]})"
        )
        checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        assert checkpoint is not None
        assert int(checkpoint[0]) == 0
    finally:
        connection.close()


def _claim_state_index_columns(database: Path) -> tuple[str, ...]:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
        isolation_level=None,
    )
    try:
        rows = connection.execute(
            "PRAGMA index_info(sh3_replay_claims_state_idx)"
        ).fetchall()
        return tuple(str(row[2]) for row in rows)
    finally:
        connection.close()


def _prepare_destination(
    source: Path,
    destination: Path,
    *,
    scenario: str,
    backup: Path,
) -> tuple[Path, ...]:
    if scenario == "backup-destination":
        replay_ops.backup_database(source, destination)
        return (source,)
    replay_ops.backup_database(source, backup)
    replay_ops.restore_database(backup, destination)
    return (source, backup)


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_interrupted_repair_index_order_is_reported_without_mutating_recovery_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"interrupted-repair-{scenario}-source.sqlite3"
    backup = tmp_path / f"interrupted-repair-{scenario}-backup.sqlite3"
    destination = tmp_path / f"interrupted-repair-{scenario}.sqlite3"
    _initialize_database(source)
    protected_sources = _prepare_destination(
        source,
        destination,
        scenario=scenario,
        backup=backup,
    )
    source_bytes_before = {path: path.read_bytes() for path in protected_sources}
    healthy_readiness = replay_ops.check_database(destination)

    temporary_main = tmp_path / f".{destination.name}.part11-74-interrupted.partial"
    residual_contents = {
        temporary_main: b"interrupted repair temporary snapshot body",
        Path(f"{temporary_main}-wal"): b"interrupted repair WAL residue",
        Path(f"{temporary_main}-shm"): b"interrupted repair SHM residue",
        Path(f"{temporary_main}-journal"): b"interrupted repair journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    # Simulate a repair interrupted after replacing the required index with an
    # index that exists but has its key columns in the wrong order.
    _replace_claim_state_index(destination, ("lease_expires_at", "state"))
    interrupted_destination_bytes = destination.read_bytes()
    assert _claim_state_index_columns(destination) == ("lease_expires_at", "state")

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
        assert (
            "index sh3_replay_claims_state_idx must use ordered columns "
            "(state, lease_expires_at)"
        ) in captured.err
        captured_text = captured.out + captured.err
        assert str(destination) not in captured_text
        for protected_source in protected_sources:
            assert str(protected_source) not in captured_text
            assert protected_source.read_bytes() == source_bytes_before[protected_source]

        # The check must not repair the invalid index, even after repeated calls.
        assert _claim_state_index_columns(destination) == ("lease_expires_at", "state")
        assert destination.read_bytes() == interrupted_destination_bytes
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        failed_reports.append(report)
        failed_diagnostics.append(captured.err)

    assert failed_reports[0] == failed_reports[1] == failed_reports[2]
    assert failed_diagnostics[0] == failed_diagnostics[1] == failed_diagnostics[2]

    # The operator's explicit completion of the repair restores the canonical
    # index definition. Subsequent reads must pass without touching residue.
    _replace_claim_state_index(destination, ("state", "lease_expires_at"))
    repaired_destination_bytes = destination.read_bytes()
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
        assert _claim_state_index_columns(destination) == ("state", "lease_expires_at")
        assert destination.read_bytes() == repaired_destination_bytes
        for protected_source in protected_sources:
            assert protected_source.read_bytes() == source_bytes_before[protected_source]
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        success_reports.append(report)

    assert success_reports[0] == success_reports[1]
