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


def _assert_residual_artifacts_unchanged(
    *,
    directory: Path,
    destination: Path,
    expected_names: tuple[str, ...],
    expected_contents: dict[Path, bytes],
) -> None:
    assert _residual_artifact_names(directory, destination) == expected_names
    for artifact, contents in expected_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_multiple_recovery_repair_cycles_keep_check_reports_and_residuals_consistent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"cycles-{scenario}-source.sqlite3"
    destination = tmp_path / f"cycles-{scenario}.sqlite3"
    _initialize_database(source)
    _initialize_database(destination)
    source_bytes_before = source.read_bytes()

    temporary_main = tmp_path / f".{destination.name}.part11-73-stale.partial"
    residual_contents = {
        temporary_main: b"multi-cycle recovery temporary snapshot body",
        Path(f"{temporary_main}-wal"): b"multi-cycle recovery WAL residue",
        Path(f"{temporary_main}-shm"): b"multi-cycle recovery SHM residue",
        Path(f"{temporary_main}-journal"): b"multi-cycle recovery journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    failure_reports: list[dict[str, Any]] = []
    failure_diagnostics: list[str] = []
    success_reports: list[dict[str, Any]] = []

    # Exercise three complete absent-index -> failed-check -> explicit-repair -> pass
    # cycles. Each check is observational only; only _set_claim_state_index mutates
    # the synthetic database as the explicit repair/fault injection action.
    for _cycle in range(3):
        _set_claim_state_index(destination, create=False)
        failed_destination_bytes = destination.read_bytes()

        failure_exit_code = replay_ops.main(
            ["check", "--database", str(destination), "--json"]
        )
        failure_capture = capsys.readouterr()

        assert failure_exit_code == 1
        assert failure_capture.out.count("\n") == 1
        failure_report = _read_report(failure_capture.out)
        assert failure_report == {
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
        assert "required index sh3_replay_claims_state_idx" in failure_capture.err
        failure_text = failure_capture.out + failure_capture.err
        assert str(source) not in failure_text
        assert str(destination) not in failure_text
        assert source.read_bytes() == source_bytes_before
        assert destination.read_bytes() == failed_destination_bytes
        _assert_residual_artifacts_unchanged(
            directory=tmp_path,
            destination=destination,
            expected_names=residual_names_before,
            expected_contents=residual_contents,
        )
        failure_reports.append(failure_report)
        failure_diagnostics.append(failure_capture.err)

        # Repair is a separate, explicit operation; check does not self-heal.
        _set_claim_state_index(destination, create=True)
        repaired_readiness = replay_ops.check_database(destination)
        repaired_destination_bytes = destination.read_bytes()
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
        success_text = success_capture.out + success_capture.err
        assert str(source) not in success_text
        assert source.read_bytes() == source_bytes_before
        assert destination.read_bytes() == repaired_destination_bytes
        _assert_residual_artifacts_unchanged(
            directory=tmp_path,
            destination=destination,
            expected_names=residual_names_before,
            expected_contents=residual_contents,
        )
        success_reports.append(success_report)

    assert failure_reports[0] == failure_reports[1] == failure_reports[2]
    assert failure_diagnostics[0] == failure_diagnostics[1] == failure_diagnostics[2]
    assert success_reports[0] == success_reports[1] == success_reports[2]
