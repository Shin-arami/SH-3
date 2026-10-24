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
            expected[artifact] = (
                artifact.read_bytes() if artifact.is_file() else None
            )
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
def test_destination_collision_error_remains_primary_when_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"collision-cleanup-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"collision-cleanup-{scenario}-input.sqlite3"
    winner_snapshot = tmp_path / f"collision-cleanup-{scenario}-winner.sqlite3"
    destination = tmp_path / f"collision-cleanup-{scenario}-destination.sqlite3"
    retry_destination = tmp_path / f"collision-cleanup-{scenario}-retry.sqlite3"
    _initialize_database(source)
    replay_ops.backup_database(source, winner_snapshot)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases: tuple[Path, ...] = (
            source,
            backup_input,
            winner_snapshot,
        )
    else:
        input_database = source
        protected_databases = (source, winner_snapshot)

    input_report = replay_ops.check_database(input_database)
    canonical_definition = _index_definition(input_database)
    winner_report = replay_ops.check_database(winner_snapshot)
    assert winner_report.evidence_count == input_report.evidence_count
    assert winner_report.replay_claim_count == input_report.replay_claim_count
    assert _index_definition(winner_snapshot) == canonical_definition
    winner_bytes = winner_snapshot.read_bytes()
    protected_artifacts = _capture_database_artifacts(protected_databases)
    assert not destination.exists()

    def publish_snapshot(target: Path) -> DatabaseReadinessReport:
        if scenario == "backup-destination":
            return replay_ops.backup_database(input_database, target)
        return replay_ops.restore_database(input_database, target)

    temporary_paths: list[Path] = []
    attempted_cleanup_paths: list[Path] = []
    injected_failure_paths: set[Path] = set()
    real_link = os.link
    real_unlink = Path.unlink

    def race_publication(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        temporary = Path(source_path)
        target = Path(destination_path)
        assert target == destination
        temporary_paths.append(temporary)
        wal_sidecar = Path(f"{temporary}-wal")
        wal_sidecar.write_bytes(b"injected temporary WAL sidecar")
        injected_failure_paths.update((wal_sidecar, temporary))
        real_link(winner_snapshot, target)
        raise FileExistsError("competing publisher created destination")

    def fail_selected_unlinks(path: Path, missing_ok: bool = False) -> None:
        attempted_cleanup_paths.append(path)
        if path in injected_failure_paths:
            raise PermissionError(f"injected unlink failure: {path.name}")
        real_unlink(path, missing_ok=missing_ok)

    with monkeypatch.context() as patch:
        patch.setattr(os, "link", race_publication)
        patch.setattr(Path, "unlink", fail_selected_unlinks)
        with pytest.raises(
            FileExistsError,
            match="refusing to overwrite existing destination",
        ) as publication_error:
            publish_snapshot(destination)

    assert not isinstance(
        publication_error.value, replay_ops.PersistentReplayReadinessError
    )
    assert publication_error.value.__cause__ is None
    assert len(temporary_paths) == 1
    temporary_snapshot = temporary_paths[0]
    wal_sidecar = Path(f"{temporary_snapshot}-wal")
    shm_sidecar = Path(f"{temporary_snapshot}-shm")
    journal_sidecar = Path(f"{temporary_snapshot}-journal")
    cleanup_paths = (
        wal_sidecar,
        shm_sidecar,
        journal_sidecar,
        temporary_snapshot,
    )
    assert all(path in attempted_cleanup_paths for path in cleanup_paths)
    assert attempted_cleanup_paths.index(wal_sidecar) < attempted_cleanup_paths.index(
        temporary_snapshot
    )
    assert injected_failure_paths == {wal_sidecar, temporary_snapshot}

    # Collision remains the primary error; cleanup diagnostics are additive.
    notes = tuple(getattr(publication_error.value, "__notes__", ()))
    assert len(notes) == 1
    cleanup_note = notes[0]
    assert "temporary snapshot cleanup was incomplete (2 item(s))" in cleanup_note
    assert "one or more temporary artifacts may remain" in cleanup_note
    assert "inspect matching .partial files and SQLite sidecars" in cleanup_note

    # The concurrent publisher's destination is untouched and remains its hard link.
    assert destination.is_file()
    assert destination.samefile(winner_snapshot)
    assert destination.read_bytes() == winner_bytes
    assert winner_snapshot.read_bytes() == winner_bytes
    assert temporary_snapshot.is_file()
    assert wal_sidecar.read_bytes() == b"injected temporary WAL sidecar"
    assert not shm_sidecar.exists()
    assert not journal_sidecar.exists()
    assert _partial_artifact_names(tmp_path, destination) == tuple(
        sorted((temporary_snapshot.name, wal_sidecar.name))
    )
    _assert_database_artifacts_unchanged(protected_artifacts)

    # Remove only the injected orphan artifacts; never remove the winner.
    real_unlink(wal_sidecar, missing_ok=True)
    real_unlink(temporary_snapshot, missing_ok=True)
    assert not any(path.exists() for path in cleanup_paths)
    assert destination.samefile(winner_snapshot)
    assert destination.read_bytes() == winner_bytes
    assert _partial_artifact_names(tmp_path, destination) == ()

    retry_report = publish_snapshot(retry_destination)
    checked_retry = replay_ops.check_database(retry_destination)
    assert retry_report.database_path == retry_destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert checked_retry.evidence_count == input_report.evidence_count
    assert checked_retry.replay_claim_count == input_report.replay_claim_count
    assert _index_definition(retry_destination) == canonical_definition
    assert destination.samefile(winner_snapshot)
    assert destination.read_bytes() == winner_bytes
    assert _partial_artifact_names(tmp_path, destination) == ()
    _assert_database_artifacts_unchanged(protected_artifacts)
