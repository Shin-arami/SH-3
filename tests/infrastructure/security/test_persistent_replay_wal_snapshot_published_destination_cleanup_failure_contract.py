from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_replay_ops import DatabaseReadinessReport
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)

_REQUIRED_INDEX = "sh3_replay_claims_state_idx"


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


def _assert_database_artifacts_unchanged(
    expected: dict[Path, bytes | None],
) -> None:
    for artifact, expected_bytes in expected.items():
        if expected_bytes is None:
            assert not artifact.exists()
        else:
            assert artifact.is_file()
            assert artifact.read_bytes() == expected_bytes


def _partial_artifact_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_published_destination_survives_temporary_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"published-cleanup-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"published-cleanup-{scenario}-input.sqlite3"
    destination = tmp_path / f"published-cleanup-{scenario}-destination.sqlite3"
    retry_destination = tmp_path / f"published-cleanup-{scenario}-retry.sqlite3"
    _initialize_database(source)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases: tuple[Path, ...] = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_artifacts = _capture_database_artifacts(protected_databases)
    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    assert _index_definition(input_database) == canonical_definition
    assert not destination.exists()

    def publish_snapshot(target: Path) -> DatabaseReadinessReport:
        if scenario == "backup-destination":
            return replay_ops.backup_database(input_database, target)
        return replay_ops.restore_database(input_database, target)

    temporary_paths: list[Path] = []
    cleanup_failure_injected = False
    real_link = os.link
    real_unlink = Path.unlink

    def record_publication(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        if Path(destination_path) == destination:
            temporary_paths.append(Path(source_path))
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

    with monkeypatch.context() as cleanup_patch:
        cleanup_patch.setattr(os, "link", record_publication)
        cleanup_patch.setattr(Path, "unlink", fail_temporary_unlink)
        with pytest.raises(
            OSError,
            match="snapshot was published, but temporary cleanup was incomplete",
        ) as cleanup_error:
            publish_snapshot(destination)

    assert cleanup_failure_injected
    assert len(temporary_paths) == 1
    temporary_snapshot = temporary_paths[0]
    assert temporary_snapshot.is_file()
    assert destination.is_file()
    assert os.path.samefile(temporary_snapshot, destination)
    assert isinstance(cleanup_error.value.__cause__, PermissionError)
    assert "Verify the destination before retrying" in str(cleanup_error.value)
    assert "inspect matching .partial files" in str(cleanup_error.value)
    assert _partial_artifact_names(tmp_path, destination) == (
        temporary_snapshot.name,
    )
    # Sidecars are cleaned before unlinking the main temporary snapshot.
    for suffix in ("-wal", "-shm", "-journal"):
        assert not Path(f"{temporary_snapshot}{suffix}").exists()

    published_bytes = destination.read_bytes()
    published_report = replay_ops.check_database(destination)
    assert published_report.evidence_count == input_report.evidence_count
    assert published_report.replay_claim_count == input_report.replay_claim_count
    assert published_report.expired_claim_count == input_report.expired_claim_count
    assert _index_definition(destination) == canonical_definition
    assert destination.read_bytes() == published_bytes
    assert temporary_snapshot.read_bytes() == published_bytes
    _assert_database_artifacts_unchanged(protected_artifacts)

    # Remove only the orphan name. Its published hard-link alias must remain valid.
    temporary_snapshot.unlink()
    assert not temporary_snapshot.exists()
    assert destination.is_file()
    assert destination.read_bytes() == published_bytes
    assert _partial_artifact_names(tmp_path, destination) == ()
    checked_destination = replay_ops.check_database(destination)
    assert checked_destination.evidence_count == input_report.evidence_count
    assert checked_destination.replay_claim_count == input_report.replay_claim_count
    assert _index_definition(destination) == canonical_definition

    # A clean retry to a new path succeeds without changing the prior publication.
    retry_report = publish_snapshot(retry_destination)
    checked_retry = replay_ops.check_database(retry_destination)
    assert retry_report.database_path == retry_destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert checked_retry.evidence_count == input_report.evidence_count
    assert checked_retry.replay_claim_count == input_report.replay_claim_count
    assert _index_definition(retry_destination) == canonical_definition
    assert destination.read_bytes() == published_bytes
    assert _partial_artifact_names(tmp_path, destination) == ()
    _assert_database_artifacts_unchanged(protected_artifacts)
