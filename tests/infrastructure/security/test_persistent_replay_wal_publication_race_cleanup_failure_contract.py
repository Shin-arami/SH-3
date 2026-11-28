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
_RACE_WINNER_INDEX = "sh3_replay_part11_117_race_winner_idx"
_STALE_MARKER = b"part11-117 pre-existing stale publication artifact"


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


def _capture_database_artifacts(
    databases: tuple[Path, ...],
) -> dict[Path, bytes | None]:
    expected: dict[Path, bytes | None] = {}
    for database in databases:
        for artifact in (
            database,
            Path(f"{database}-wal"),
            Path(f"{database}-shm"),
            Path(f"{database}-journal"),
        ):
            expected[artifact] = artifact.read_bytes() if artifact.is_file() else None
    return expected


def _assert_database_artifacts_unchanged(expected: dict[Path, bytes | None]) -> None:
    for artifact, expected_bytes in expected.items():
        if expected_bytes is None:
            assert not artifact.exists()
        else:
            assert artifact.is_file()
            assert artifact.read_bytes() == expected_bytes


def _has_index(database: Path, index_name: str) -> bool:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
        isolation_level=None,
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


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _expected_report(
    database: Path,
    report: DatabaseReadinessReport,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "action": "check",
        "database": str(database.resolve()),
        "sqlite_version": report.sqlite_version,
        "journal_mode": report.journal_mode,
        "integrity_status": "pass",
        "evidence_records": report.evidence_count,
        "replay_claims": report.replay_claim_count,
        "expired_claims": report.expired_claim_count,
        "pending_evidence_reconciliation": (
            report.pending_evidence_reconciliation_count
        ),
        "policy_gates": {},
        "exit_code": 0,
    }


def _remove_inspection_created_snapshot_sidecars(
    snapshot: Path,
    expected_artifacts: dict[Path, bytes | None],
) -> None:
    """Remove only sidecars created by reading the published hard-link alias.

    The competing publisher links the immutable winner snapshot to the requested
    destination. SQLite inspection through that alias can materialize sidecars
    beside the winner's pathname, even though the publication operation never
    opened or modified the winner. Sidecars that existed in the baseline are
    never removed here.
    """
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(f"{snapshot}{suffix}")
        if sidecar not in expected_artifacts or expected_artifacts[sidecar] is not None:
            continue
        sidecar.unlink(missing_ok=True)
        assert not sidecar.exists()

@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_publication_race_cleanup_failure_preserves_winner_and_retry(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"publication-cleanup-race-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"publication-cleanup-race-{scenario}-input.sqlite3"
    winner_snapshot = tmp_path / f"publication-cleanup-race-{scenario}-winner.sqlite3"
    destination = tmp_path / f"publication-cleanup-race-{scenario}-destination.sqlite3"
    retry_destination = tmp_path / f"publication-cleanup-race-{scenario}-retry.sqlite3"
    _initialize_database(source)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases: tuple[Path, ...] = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    winner_report = replay_ops.backup_database(input_database, winner_snapshot)
    protected_databases = (*protected_databases, winner_snapshot)
    protected_artifacts = _capture_database_artifacts(protected_databases)
    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    assert _index_definition(input_database) == canonical_definition
    assert _index_definition(winner_snapshot) == canonical_definition
    winner_bytes = winner_snapshot.read_bytes()
    assert winner_report.evidence_count == input_report.evidence_count
    assert winner_report.replay_claim_count == input_report.replay_claim_count
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

    temporary_paths: list[Path] = []
    publication_race_injected = False
    cleanup_failure_injected = False
    real_link = os.link
    real_unlink = Path.unlink

    def publish_snapshot(target: Path) -> DatabaseReadinessReport:
        if scenario == "backup-destination":
            return replay_ops.backup_database(input_database, target)
        return replay_ops.restore_database(input_database, target)

    def racing_link(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        nonlocal publication_race_injected
        assert Path(destination_path) == destination
        if not publication_race_injected:
            publication_race_injected = True
            temporary_paths.append(Path(source_path))
            # A competing publisher wins the destination race with a separate,
            # already-verified snapshot; the current publication must lose safely.
            real_link(winner_snapshot, destination)
            real_link(source_path, destination_path)
            return
        real_link(source_path, destination_path)

    def fail_temporary_unlink(path: Path, missing_ok: bool = False) -> None:
        nonlocal cleanup_failure_injected
        if (
            temporary_paths
            and path == temporary_paths[0]
            and not cleanup_failure_injected
        ):
            cleanup_failure_injected = True
            raise PermissionError("injected temporary snapshot unlink failure")
        real_unlink(path, missing_ok=missing_ok)

    with monkeypatch.context() as publication_patch:
        publication_patch.setattr(os, "link", racing_link)
        publication_patch.setattr(Path, "unlink", fail_temporary_unlink)
        with pytest.raises(
            FileExistsError,
            match="refusing to overwrite existing destination",
        ) as publication_error:
            publish_snapshot(destination)

    assert publication_race_injected
    assert cleanup_failure_injected
    assert len(temporary_paths) == 1
    temporary_snapshot = temporary_paths[0]
    assert temporary_snapshot.is_file()
    # Production cleanup must remove SQLite sidecars before we open the orphan.
    # Inspecting a surviving WAL-mode database can itself create fresh sidecars.
    for suffix in ("-wal", "-shm", "-journal"):
        assert not Path(f"{temporary_snapshot}{suffix}").exists()
    notes = getattr(publication_error.value, "__notes__", ())
    assert any(
        "temporary snapshot cleanup was incomplete" in str(note)
        for note in notes
    )
    assert destination.is_file()
    assert destination.read_bytes() == winner_bytes
    assert _index_definition(destination) == canonical_definition
    assert _has_index(destination, _REQUIRED_INDEX)
    assert not _has_index(destination, _RACE_WINNER_INDEX)
    assert _index_definition(temporary_snapshot) == canonical_definition
    # The read-only inspection above may create fresh empty WAL-mode sidecars.
    # Remove only those inspection-created sidecars after proving production
    # cleanup had already removed them before the inspection opened the file.
    for suffix in ("-wal", "-shm", "-journal"):
        real_unlink(Path(f"{temporary_snapshot}{suffix}"), missing_ok=True)
        assert not Path(f"{temporary_snapshot}{suffix}").exists()
    assert _residual_artifact_names(tmp_path, destination) == tuple(
        sorted((*stale_names_before, temporary_snapshot.name))
    )
    for artifact, contents in stale_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents
    _remove_inspection_created_snapshot_sidecars(winner_snapshot, protected_artifacts)
    _assert_database_artifacts_unchanged(protected_artifacts)

    # The failed attempt did not overwrite the competing winner. A direct retry
    # to that occupied path must continue to refuse replacement.
    with pytest.raises(
        FileExistsError, match="refusing to overwrite existing destination"
    ):
        publish_snapshot(destination)
    assert destination.read_bytes() == winner_bytes
    assert temporary_snapshot.is_file()
    assert _residual_artifact_names(tmp_path, destination) == tuple(
        sorted((*stale_names_before, temporary_snapshot.name))
    )

    # Explicit cleanup removes only the orphan created by the losing attempt.
    # Pre-existing stale artifacts and the competing winner remain untouched.
    for suffix in ("-wal", "-shm", "-journal"):
        assert not Path(f"{temporary_snapshot}{suffix}").exists()
    temporary_snapshot.unlink()
    assert not temporary_snapshot.exists()
    assert destination.read_bytes() == winner_bytes
    assert _residual_artifact_names(tmp_path, destination) == stale_names_before
    for artifact, contents in stale_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents
    _remove_inspection_created_snapshot_sidecars(winner_snapshot, protected_artifacts)
    _assert_database_artifacts_unchanged(protected_artifacts)

    # Retrying to a fresh destination succeeds without mutating the race winner.
    retry_report = publish_snapshot(retry_destination)
    checked_retry = replay_ops.check_database(retry_destination)
    checked_winner = replay_ops.check_database(destination)
    assert retry_report.database_path == retry_destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert checked_retry.evidence_count == input_report.evidence_count
    assert checked_retry.replay_claim_count == input_report.replay_claim_count
    assert checked_winner.evidence_count == winner_report.evidence_count
    assert checked_winner.replay_claim_count == winner_report.replay_claim_count
    assert _index_definition(retry_destination) == canonical_definition
    assert _index_definition(destination) == canonical_definition
    assert _residual_artifact_names(tmp_path, destination) == stale_names_before
    _remove_inspection_created_snapshot_sidecars(winner_snapshot, protected_artifacts)
    _assert_database_artifacts_unchanged(protected_artifacts)

    cli_outputs: list[dict[str, Any]] = []
    for database, report in (
        (destination, checked_winner),
        (retry_destination, checked_retry),
    ):
        reports: list[dict[str, Any]] = []
        for _ in range(2):
            exit_code = replay_ops.main(
                ["check", "--database", str(database), "--json"]
            )
            captured = capsys.readouterr()
            assert exit_code == 0
            assert captured.err == ""
            parsed = _read_report(captured.out)
            assert parsed == _expected_report(database, report)
            reports.append(parsed)
        assert reports[0] == reports[1]
        cli_outputs.extend(reports)

    assert cli_outputs[0] == cli_outputs[1]
    assert cli_outputs[2] == cli_outputs[3]
    assert destination.read_bytes() == winner_bytes
    assert _residual_artifact_names(tmp_path, destination) == stale_names_before
    for artifact, contents in stale_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents
    _remove_inspection_created_snapshot_sidecars(winner_snapshot, protected_artifacts)
    _assert_database_artifacts_unchanged(protected_artifacts)
