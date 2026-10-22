from __future__ import annotations

import json
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


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_read_only_recovery_check_verifies_destination_without_mutating_residual_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    source = tmp_path / f"recovery-{command}-source.sqlite3"
    destination = tmp_path / f"recovery-{command}-destination.sqlite3"
    _initialize_database(source)
    _initialize_database(destination)
    source_bytes_before = source.read_bytes()
    destination_bytes_before = destination.read_bytes()
    readiness_before = replay_ops.check_database(destination)

    temporary_main = tmp_path / f".{destination.name}.part11-69-stale.partial"
    residual_contents = {
        temporary_main: b"preserved recovery snapshot body",
        Path(f"{temporary_main}-wal"): b"preserved recovery WAL residue",
        Path(f"{temporary_main}-shm"): b"preserved recovery SHM residue",
        Path(f"{temporary_main}-journal"): b"preserved recovery journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    exit_code = replay_ops.main(
        ["check", "--database", str(destination), "--json"]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.count("\n") == 1
    assert captured.err == ""
    report = _read_report(captured.out)
    assert report["schema_version"] == 1
    assert report["action"] == "check"
    assert report["database"] == str(destination.resolve())
    assert report["integrity_status"] == "pass"
    assert report["evidence_records"] == readiness_before.evidence_count
    assert report["replay_claims"] == readiness_before.replay_claim_count
    assert report["expired_claims"] == readiness_before.expired_claim_count
    assert (
        report["pending_evidence_reconciliation"]
        == readiness_before.pending_evidence_reconciliation_count
    )
    assert report["policy_gates"] == {}
    assert report["exit_code"] == 0
    assert str(source) not in captured.out

    assert source.read_bytes() == source_bytes_before
    assert destination.read_bytes() == destination_bytes_before
    assert _residual_artifact_names(tmp_path, destination) == residual_names_before
    for artifact, contents in residual_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents

    readiness_after = replay_ops.check_database(destination)
    assert readiness_after.evidence_count == readiness_before.evidence_count
    assert readiness_after.replay_claim_count == readiness_before.replay_claim_count
    assert readiness_after.expired_claim_count == readiness_before.expired_claim_count
    assert (
        readiness_after.pending_evidence_reconciliation_count
        == readiness_before.pending_evidence_reconciliation_count
    )
