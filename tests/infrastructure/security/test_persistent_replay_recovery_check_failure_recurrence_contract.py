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


def _assert_failed_read_only_check(
    *,
    source: Path,
    destination: Path,
    source_bytes_before: bytes,
    destination_bytes_before: bytes,
    residual_contents: dict[Path, bytes],
    residual_names_before: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> tuple[dict[str, Any], str]:
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
    assert "required index sh3_replay_claims_state_idx" in captured.err
    captured_text = captured.out + captured.err
    assert str(source) not in captured_text
    assert str(destination) not in captured_text
    assert source.read_bytes() == source_bytes_before
    assert destination.read_bytes() == destination_bytes_before
    assert _residual_artifact_names(tmp_path, destination) == residual_names_before
    for artifact, contents in residual_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents
    return report, captured.err


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_recurrent_schema_failure_after_explicit_repair_is_detected_without_mutation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"recurrence-{scenario}-source.sqlite3"
    destination = tmp_path / f"recurrence-{scenario}.sqlite3"
    _initialize_database(source)
    _initialize_database(destination)
    source_bytes_before = source.read_bytes()

    temporary_main = tmp_path / f".{destination.name}.part11-72-stale.partial"
    residual_contents = {
        temporary_main: b"recurrence temporary snapshot body",
        Path(f"{temporary_main}-wal"): b"recurrence WAL residue",
        Path(f"{temporary_main}-shm"): b"recurrence SHM residue",
        Path(f"{temporary_main}-journal"): b"recurrence journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    # First failure: a missing required index must be reported, not repaired.
    _set_claim_state_index(destination, create=False)
    first_failure_bytes = destination.read_bytes()
    first_report, first_stderr = _assert_failed_read_only_check(
        source=source,
        destination=destination,
        source_bytes_before=source_bytes_before,
        destination_bytes_before=first_failure_bytes,
        residual_contents=residual_contents,
        residual_names_before=residual_names_before,
        capsys=capsys,
        tmp_path=tmp_path,
    )

    # Repair is explicit. The checker must pass only after the index is restored.
    _set_claim_state_index(destination, create=True)
    repaired_readiness = replay_ops.check_database(destination)
    repaired_bytes = destination.read_bytes()
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
    assert source.read_bytes() == source_bytes_before
    assert destination.read_bytes() == repaired_bytes
    assert _residual_artifact_names(tmp_path, destination) == residual_names_before
    for artifact, contents in residual_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents

    # The same defect recurs after repair. Repeated checks must fail consistently
    # and must not recreate the index or alter database/residual-artifact bytes.
    _set_claim_state_index(destination, create=False)
    recurrent_failure_bytes = destination.read_bytes()
    recurrent_results = [
        _assert_failed_read_only_check(
            source=source,
            destination=destination,
            source_bytes_before=source_bytes_before,
            destination_bytes_before=recurrent_failure_bytes,
            residual_contents=residual_contents,
            residual_names_before=residual_names_before,
            capsys=capsys,
            tmp_path=tmp_path,
        )
        for _ in range(2)
    ]

    assert recurrent_results[0] == recurrent_results[1]
    assert recurrent_results[0][0] == first_report
    assert recurrent_results[0][1] == first_stderr
