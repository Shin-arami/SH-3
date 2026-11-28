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
_COLLISION_ATTEMPTS = 3


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


def _claim_state_index_definition(
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


def _attempt_duplicate_index_creation(database: Path) -> None:
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        connection.execute(
            f"CREATE INDEX {_REQUIRED_INDEX} "
            "ON sh3_replay_claims(lease_expires_at, state)"
        )
    finally:
        connection.close()


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_repeated_duplicate_index_name_collisions_are_side_effect_free(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"repeated-collision-{scenario}-source.sqlite3"
    backup = tmp_path / f"repeated-collision-{scenario}-backup.sqlite3"
    destination = tmp_path / f"repeated-collision-{scenario}-destination.sqlite3"
    _initialize_database(source)
    protected_sources = _prepare_destination(
        source,
        backup,
        destination,
        scenario=scenario,
    )
    source_bytes_before = {path: path.read_bytes() for path in protected_sources}
    readiness = replay_ops.check_database(destination)

    temporary_main = (
        tmp_path / f".{destination.name}.part11-82-collision-retry.partial"
    )
    residual_contents = {
        temporary_main: b"repeated index-name collision temporary snapshot body",
        Path(f"{temporary_main}-wal"): b"repeated collision WAL residue",
        Path(f"{temporary_main}-shm"): b"repeated collision SHM residue",
        Path(f"{temporary_main}-journal"): b"repeated collision journal residue",
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    assert _claim_state_index_definition(destination) == canonical_definition
    destination_bytes_before = destination.read_bytes()
    collision_messages: list[str] = []
    reports: list[dict[str, Any]] = []

    for _ in range(_COLLISION_ATTEMPTS):
        with pytest.raises(sqlite3.OperationalError, match="already exists") as error:
            _attempt_duplicate_index_creation(destination)
        collision_messages.append(str(error.value))

        # A failed repair retry must not replace the canonical definition or
        # mutate the destination, protected source files, or residual artifacts.
        assert destination.read_bytes() == destination_bytes_before
        assert _claim_state_index_definition(destination) == canonical_definition
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        for protected_source in protected_sources:
            assert protected_source.read_bytes() == source_bytes_before[protected_source]

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
        assert _claim_state_index_definition(destination) == canonical_definition
        assert destination.read_bytes() == destination_bytes_before
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.is_file()
            assert artifact.read_bytes() == contents
        for protected_source in protected_sources:
            assert protected_source.read_bytes() == source_bytes_before[protected_source]
        reports.append(report)

    assert len(collision_messages) == _COLLISION_ATTEMPTS
    assert len(set(collision_messages)) == 1
    assert len(reports) == _COLLISION_ATTEMPTS
    assert all(report == reports[0] for report in reports[1:])
