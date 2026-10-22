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


def _set_claim_state_index(database: Path, *, create: bool) -> None:
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        if create:
            connection.execute(
                "CREATE INDEX sh3_replay_claims_state_idx "
                "ON sh3_replay_claims(state, lease_expires_at)"
            )
        else:
            connection.execute("DROP INDEX sh3_replay_claims_state_idx")
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
def test_recovery_check_transitions_from_failure_to_pass_after_explicit_schema_repair(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"transition-{scenario}-source.sqlite3"
    destination = tmp_path / f"transition-{scenario}.sqlite3"
    _initialize_database(source)
    _initialize_database(destination)
    source_bytes_before = source.read_bytes()
    healthy_readiness_before = replay_ops.check_database(destination)

    temporary_main = tmp_path / f".{destination.name}.part11-71-stale.partial"
    residual_contents = {
        temporary_main: b"state-transition temporary snapshot body",
        Path(f"{temporary_main}-wal"): b"state-transition WAL residue",
        Path(f"{temporary_main}-shm"): b"state-transition SHM residue",
        Path(f"{temporary_main}-journal"): b"state-transition journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    _set_claim_state_index(destination, create=False)
    failed_destination_bytes = destination.read_bytes()

    failed_exit_code = replay_ops.main(
        ["check", "--database", str(destination), "--json"]
    )
    failed_capture = capsys.readouterr()

    assert failed_exit_code == 1
    assert failed_capture.out.count("\n") == 1
    failed_report = _read_report(failed_capture.out)
    assert failed_report == {
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
    assert "required index sh3_replay_claims_state_idx" in failed_capture.err
    assert str(source) not in failed_capture.out + failed_capture.err
    assert str(destination) not in failed_capture.out + failed_capture.err
    assert source.read_bytes() == source_bytes_before
    assert destination.read_bytes() == failed_destination_bytes
    assert _residual_artifact_names(tmp_path, destination) == residual_names_before
    for artifact, contents in residual_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents

    # Repair is an explicit test/operator action; the checker itself never repairs.
    _set_claim_state_index(destination, create=True)
    repaired_destination_bytes = destination.read_bytes()
    repaired_readiness = replay_ops.check_database(destination)
    assert repaired_readiness.evidence_count == healthy_readiness_before.evidence_count
    assert repaired_readiness.replay_claim_count == healthy_readiness_before.replay_claim_count
    assert repaired_readiness.journal_mode == healthy_readiness_before.journal_mode

    successful_reports: list[dict[str, Any]] = []
    for _ in range(3):
        success_exit_code = replay_ops.main(
            ["check", "--database", str(destination), "--json"]
        )
        success_capture = capsys.readouterr()

        assert success_exit_code == 0
        assert success_capture.out.count("\n") == 1
        assert success_capture.err == ""
        success_report = _read_report(success_capture.out)
        assert success_report == {
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
        assert source_bytes_before == source.read_bytes()
        assert destination.read_bytes() == repaired_destination_bytes
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        successful_reports.append(success_report)

    assert successful_reports[0] == successful_reports[1] == successful_reports[2]
