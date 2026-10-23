from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_replay_ops import DatabaseReadinessReport
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)

_REQUIRED_INDEX = "sh3_replay_claims_state_idx"
_STALE_MARKER = b"part11-116 pre-existing stale publication artifact"
_RACE_WINNER = b"part11-116 concurrent publisher destination sentinel\n"


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _index_definition(
    database: Path,
) -> tuple[str, bool, bool, tuple[str, ...]]:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
        isolation_level=None,
    )
    try:
        owner_row = connection.execute(
            "SELECT tbl_name FROM sqlite_master "
            "WHERE type = 'index' AND name = ?",
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
        columns = connection.execute(
            f"PRAGMA index_info({_REQUIRED_INDEX})"
        ).fetchall()
        return (
            str(owner_row[0]),
            bool(index_row[2]),
            bool(index_row[4]),
            tuple(str(row[2]) for row in columns),
        )
    finally:
        connection.close()


def _residual_artifact_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_stale_partial_is_preserved_across_publication_race_and_retry(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"publication-race-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"publication-race-{scenario}-input.sqlite3"
    destination = tmp_path / f"publication-race-{scenario}-destination.sqlite3"
    _initialize_database(source)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases: tuple[Path, ...] = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_bytes = {
        database: database.read_bytes() for database in protected_databases
    }
    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    assert _index_definition(input_database) == canonical_definition
    assert not destination.exists()

    stale_main = tmp_path / f".{destination.name}.stale.partial"
    stale_contents = {
        stale_main: _STALE_MARKER,
        Path(f"{stale_main}-wal"): _STALE_MARKER + b" WAL",
        Path(f"{stale_main}-shm"): _STALE_MARKER + b" SHM",
        Path(f"{stale_main}-journal"): _STALE_MARKER + b" journal",
    }
    for artifact, contents in stale_contents.items():
        artifact.write_bytes(contents)
    stale_names_before = _residual_artifact_names(tmp_path, destination)
    assert stale_names_before == tuple(sorted(path.name for path in stale_contents))

    def publish_snapshot() -> DatabaseReadinessReport:
        if scenario == "backup-destination":
            return replay_ops.backup_database(input_database, destination)
        return replay_ops.restore_database(input_database, destination)

    real_link = os.link
    publication_race_injected = False

    def race_link(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        nonlocal publication_race_injected
        assert Path(destination_path) == destination
        if not publication_race_injected:
            publication_race_injected = True
            Path(destination_path).write_bytes(_RACE_WINNER)
        real_link(source_path, destination_path)

    monkeypatch.setattr(os, "link", race_link)
    with pytest.raises(
        FileExistsError,
        match="refusing to overwrite existing destination",
    ):
        publish_snapshot()

    assert publication_race_injected
    assert destination.is_file()
    assert destination.read_bytes() == _RACE_WINNER
    assert _residual_artifact_names(tmp_path, destination) == stale_names_before
    for artifact, contents in stale_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents
    for database in protected_databases:
        assert database.read_bytes() == protected_bytes[database]

    # Re-enable the real publication primitive, then remove only the simulated
    # race winner. Pre-existing stale artifacts remain untouched throughout retry.
    monkeypatch.setattr(os, "link", real_link)
    destination.unlink()
    assert not destination.exists()
    published_report = publish_snapshot()
    checked_report = replay_ops.check_database(destination)

    assert published_report.database_path == destination.resolve()
    assert published_report.evidence_count == input_report.evidence_count
    assert published_report.replay_claim_count == input_report.replay_claim_count
    assert published_report.expired_claim_count == input_report.expired_claim_count
    assert checked_report.evidence_count == input_report.evidence_count
    assert checked_report.replay_claim_count == input_report.replay_claim_count
    assert _index_definition(destination) == canonical_definition
    assert _residual_artifact_names(tmp_path, destination) == stale_names_before
    for artifact, contents in stale_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents
    for database in protected_databases:
        assert database.read_bytes() == protected_bytes[database]

    expected_json: dict[str, object] = {
        "schema_version": 1,
        "action": "check",
        "database": str(destination.resolve()),
        "sqlite_version": checked_report.sqlite_version,
        "journal_mode": checked_report.journal_mode,
        "integrity_status": "pass",
        "evidence_records": checked_report.evidence_count,
        "replay_claims": checked_report.replay_claim_count,
        "expired_claims": checked_report.expired_claim_count,
        "pending_evidence_reconciliation": (
            checked_report.pending_evidence_reconciliation_count
        ),
        "policy_gates": {},
        "exit_code": 0,
    }
    cli_reports: list[dict[str, Any]] = []
    for _ in range(2):
        exit_code = replay_ops.main(
            ["check", "--database", str(destination), "--json"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.err == ""
        report = _read_report(captured.out)
        assert report == expected_json
        assert _index_definition(destination) == canonical_definition
        assert _residual_artifact_names(tmp_path, destination) == stale_names_before
        for artifact, contents in stale_contents.items():
            assert artifact.read_bytes() == contents
        for database in protected_databases:
            assert database.read_bytes() == protected_bytes[database]
        cli_reports.append(report)

    assert cli_reports[0] == cli_reports[1]
