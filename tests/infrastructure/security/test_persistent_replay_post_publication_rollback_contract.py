from __future__ import annotations

import json
import os
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


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_published_snapshot_report_uses_prevalidated_inode_without_reopening_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    source = tmp_path / f"private-{command}-source.sqlite3"
    destination = tmp_path / f"private-{command}-destination.sqlite3"
    _initialize_database(source)
    source_bytes_before = source.read_bytes()

    checked_paths: list[Path] = []
    checked_reports: list[replay_ops.DatabaseReadinessReport] = []
    published_pairs: list[tuple[Path, Path]] = []
    original_check_database = replay_ops.check_database
    original_link = os.link

    def record_check(
        database_path: str | os.PathLike[str],
        *,
        timeout_seconds: float = 5.0,
        _connection: sqlite3.Connection | None = None,
    ) -> replay_ops.DatabaseReadinessReport:
        report = original_check_database(
            database_path,
            timeout_seconds=timeout_seconds,
            _connection=_connection,
        )
        checked_paths.append(Path(database_path).resolve())
        checked_reports.append(report)
        return report

    def record_link(
        temporary_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        temporary = Path(temporary_path).resolve()
        publication_target = Path(destination_path).resolve()
        assert checked_paths
        assert checked_paths[-1] == temporary
        assert any(report.database_path == temporary for report in checked_reports)
        assert publication_target == destination.resolve()
        assert not publication_target.exists()
        original_link(temporary_path, destination_path)
        published_pairs.append((temporary, publication_target))
        assert os.path.samefile(temporary, publication_target)

    monkeypatch.setattr(replay_ops, "check_database", record_check)
    monkeypatch.setattr(os, "link", record_link)

    if command == "backup":
        arguments = [
            "backup",
            "--database",
            str(source),
            "--destination",
            str(destination),
            "--json",
        ]
    else:
        arguments = [
            "restore",
            "--backup",
            str(source),
            "--destination",
            str(destination),
            "--json",
        ]

    exit_code = replay_ops.main(arguments)
    captured = capsys.readouterr()

    assert exit_code == 0, captured.err
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    report = _read_report(captured.out)
    assert report["schema_version"] == 1
    assert report["action"] == command
    assert report["database"] == str(destination.resolve())
    assert report["integrity_status"] == "pass"
    assert report["evidence_records"] == checked_reports[-1].evidence_count == 0
    assert report["replay_claims"] == checked_reports[-1].replay_claim_count == 0
    assert report["expired_claims"] == checked_reports[-1].expired_claim_count == 0
    assert (
        report["pending_evidence_reconciliation"]
        == checked_reports[-1].pending_evidence_reconciliation_count
        == 0
    )
    assert report["sqlite_version"] == checked_reports[-1].sqlite_version
    assert report["journal_mode"] == checked_reports[-1].journal_mode
    assert report["policy_gates"] == {}
    assert report["exit_code"] == 0

    # Only the source and private temporary snapshot are opened for readiness
    # checks. Publication uses an atomic hard link to the already-verified inode;
    # it does not re-open or destructively roll back the destination by path.
    assert checked_paths[0] == source.resolve()
    assert len(checked_paths) == 2
    temporary = checked_paths[1]
    assert temporary != destination.resolve()
    assert len(published_pairs) == 1
    assert published_pairs[0] == (temporary, destination.resolve())
    assert not temporary.exists()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))

    assert source.is_file()
    assert source.read_bytes() == source_bytes_before
    assert destination.is_file()
    published_report = original_check_database(destination)
    assert published_report.evidence_count == 0
    assert published_report.replay_claim_count == 0
