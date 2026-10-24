from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_replay_ops import (
    DatabaseReadinessReport,
    PersistentReplayReadinessError,
)
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _capture_artifacts(databases: tuple[Path, ...]) -> dict[Path, bytes | None]:
    artifacts: dict[Path, bytes | None] = {}
    for database in databases:
        for path in (
            database,
            Path(f"{database}-wal"),
            Path(f"{database}-shm"),
            Path(f"{database}-journal"),
        ):
            artifacts[path] = path.read_bytes() if path.is_file() else None
    return artifacts


def _assert_artifacts_unchanged(expected: dict[Path, bytes | None]) -> None:
    for path, original in expected.items():
        if original is None:
            assert not path.exists()
        else:
            assert path.is_file()
            assert path.read_bytes() == original


def _partial_names(directory: Path, destination: Path) -> tuple[str, ...]:
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
def test_prepublication_verification_error_survives_multiple_cleanup_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"verification-cleanup-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"verification-cleanup-{scenario}-input.sqlite3"
    destination = tmp_path / f"verification-cleanup-{scenario}-destination.sqlite3"
    retry_destination = tmp_path / f"verification-cleanup-{scenario}-retry.sqlite3"
    _initialize_database(source)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases: tuple[Path, ...] = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_artifacts = _capture_artifacts(protected_databases)
    assert not destination.exists()

    def publish_snapshot(target: Path) -> DatabaseReadinessReport:
        if scenario == "backup-destination":
            return replay_ops.backup_database(input_database, target)
        return replay_ops.restore_database(input_database, target)

    verification_error = PersistentReplayReadinessError(
        "injected snapshot verification failure before publication"
    )
    temporary_paths: list[Path] = []
    attempted_cleanup_paths: list[Path] = []
    injected_failure_paths: set[Path] = set()
    publication_calls: list[tuple[Path, Path]] = []
    real_check_database = replay_ops.check_database
    real_link = os.link
    real_unlink = Path.unlink

    def fail_snapshot_verification(
        database_path: str | os.PathLike[str],
        *,
        timeout_seconds: float = 5.0,
        _connection: sqlite3.Connection | None = None,
    ) -> DatabaseReadinessReport:
        report = real_check_database(
            database_path,
            timeout_seconds=timeout_seconds,
            _connection=_connection,
        )
        candidate = Path(database_path)
        if candidate.name.endswith(".partial"):
            temporary_paths.append(candidate)
            wal_sidecar = Path(f"{candidate}-wal")
            journal_sidecar = Path(f"{candidate}-journal")
            wal_sidecar.write_bytes(b"injected verification WAL sidecar")
            journal_sidecar.write_bytes(b"injected verification journal sidecar")
            injected_failure_paths.update((wal_sidecar, candidate))
            raise verification_error
        return report

    def record_publication(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        publication_calls.append((Path(source_path), Path(destination_path)))
        real_link(source_path, destination_path)

    def fail_selected_unlinks(path: Path, missing_ok: bool = False) -> None:
        attempted_cleanup_paths.append(path)
        if path in injected_failure_paths:
            raise PermissionError(f"injected unlink failure: {path.name}")
        real_unlink(path, missing_ok=missing_ok)

    with monkeypatch.context() as patch:
        patch.setattr(replay_ops, "check_database", fail_snapshot_verification)
        patch.setattr(os, "link", record_publication)
        patch.setattr(Path, "unlink", fail_selected_unlinks)
        with pytest.raises(
            PersistentReplayReadinessError,
            match="injected snapshot verification failure before publication",
        ) as caught:
            publish_snapshot(destination)

    assert caught.value is verification_error
    assert publication_calls == []
    assert len(temporary_paths) == 1
    temporary_snapshot = temporary_paths[0]
    wal_sidecar = Path(f"{temporary_snapshot}-wal")
    journal_sidecar = Path(f"{temporary_snapshot}-journal")
    cleanup_paths = (
        wal_sidecar,
        Path(f"{temporary_snapshot}-shm"),
        journal_sidecar,
        temporary_snapshot,
    )
    assert all(path in attempted_cleanup_paths for path in cleanup_paths)
    assert attempted_cleanup_paths.index(wal_sidecar) < attempted_cleanup_paths.index(
        temporary_snapshot
    )
    assert injected_failure_paths == {wal_sidecar, temporary_snapshot}
    notes = " ".join(getattr(caught.value, "__notes__", ()))
    assert "temporary snapshot cleanup was incomplete (2 item(s))" in notes
    assert "inspect matching .partial files" in notes
    assert "one or more temporary artifacts may remain" in notes

    # Verification failed before publication; only the injected orphan remains.
    assert not destination.exists()
    assert temporary_snapshot.is_file()
    assert wal_sidecar.read_bytes() == b"injected verification WAL sidecar"
    assert not journal_sidecar.exists()
    assert _partial_names(tmp_path, destination) == (
        temporary_snapshot.name,
        wal_sidecar.name,
    )
    _assert_artifacts_unchanged(protected_artifacts)

    # Recover the orphan names after the injected filesystem fault has ended.
    real_unlink(wal_sidecar, missing_ok=True)
    real_unlink(temporary_snapshot, missing_ok=True)
    assert not wal_sidecar.exists()
    assert not temporary_snapshot.exists()
    assert not destination.exists()
    assert _partial_names(tmp_path, destination) == ()

    retry_report = publish_snapshot(retry_destination)
    retry_check = replay_ops.check_database(retry_destination)
    assert retry_report.database_path == retry_destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert retry_check.evidence_count == input_report.evidence_count
    assert retry_check.replay_claim_count == input_report.replay_claim_count
    assert _partial_names(tmp_path, destination) == ()
    _assert_artifacts_unchanged(protected_artifacts)
