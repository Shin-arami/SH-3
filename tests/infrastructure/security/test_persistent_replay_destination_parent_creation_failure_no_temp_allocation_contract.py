from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_replay_ops import DatabaseReadinessReport
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
        for artifact in (
            database,
            Path(f"{database}-wal"),
            Path(f"{database}-shm"),
            Path(f"{database}-journal"),
        ):
            artifacts[artifact] = artifact.read_bytes() if artifact.is_file() else None
    return artifacts


def _assert_artifacts_unchanged(expected: dict[Path, bytes | None]) -> None:
    for artifact, expected_bytes in expected.items():
        if expected_bytes is None:
            assert not artifact.exists()
        else:
            assert artifact.is_file()
            assert artifact.read_bytes() == expected_bytes


def _partial_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.rglob("*")
            if path.is_file()
            and path.name.startswith(prefix)
            and ".partial" in path.name
        )
    )


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_destination_parent_creation_failure_prevents_snapshot_allocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"parent-create-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"parent-create-{scenario}-input.sqlite3"
    destination_parent = tmp_path / f"parent-create-{scenario}-missing-parent"
    destination = destination_parent / f"{scenario}-destination.sqlite3"
    retry_destination = destination_parent / f"{scenario}-retry.sqlite3"
    _initialize_database(source)

    protected_databases: tuple[Path, ...]
    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_artifacts = _capture_artifacts(protected_databases)
    assert not destination_parent.exists()
    assert not destination.exists()

    def publish_snapshot(target: Path) -> DatabaseReadinessReport:
        if scenario == "backup-destination":
            return replay_ops.backup_database(input_database, target)
        return replay_ops.restore_database(input_database, target)

    parent_error = PermissionError(
        "injected destination parent creation failure"
    )
    mkdir_calls: list[Path] = []
    allocation_calls: list[Path] = []
    backup_calls: list[tuple[Path, Path]] = []
    publication_calls: list[tuple[Path, Path]] = []
    real_mkdir = Path.mkdir

    def fail_destination_parent_creation(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if path == destination_parent:
            mkdir_calls.append(path)
            raise parent_error
        real_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    def reject_snapshot_allocation(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | os.PathLike[str] | None = None,
        text: bool = False,
    ) -> tuple[int, str]:
        del suffix, prefix, dir, text
        allocation_calls.append(destination_parent)
        raise AssertionError("snapshot allocation must not follow parent failure")

    def reject_backup(
        source_path: Path,
        temporary_path: Path,
        *,
        timeout_seconds: float,
        source_connection: sqlite3.Connection | None = None,
    ) -> None:
        del timeout_seconds, source_connection
        backup_calls.append((source_path, temporary_path))
        raise AssertionError("online backup must not follow parent failure")

    def reject_publication(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        publication_calls.append((Path(source_path), Path(destination_path)))
        raise AssertionError("publication must not follow parent failure")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "mkdir", fail_destination_parent_creation)
        patch.setattr(tempfile, "mkstemp", reject_snapshot_allocation)
        patch.setattr(replay_ops, "_backup_to_temporary", reject_backup)
        patch.setattr(os, "link", reject_publication)
        with pytest.raises(
            PermissionError,
            match="injected destination parent creation failure",
        ) as caught:
            publish_snapshot(destination)

    assert caught.value is parent_error
    assert mkdir_calls == [destination_parent]
    assert allocation_calls == []
    assert backup_calls == []
    assert publication_calls == []
    assert not destination_parent.exists()
    assert not destination.exists()
    assert _partial_names(tmp_path, destination) == ()
    _assert_artifacts_unchanged(protected_artifacts)

    # Once the filesystem fault is removed, retrying can create the parent and
    # publish a verified snapshot without changing the failed destination path.
    retry_report = publish_snapshot(retry_destination)
    retry_check = replay_ops.check_database(retry_destination)
    assert retry_report.database_path == retry_destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert retry_check.evidence_count == input_report.evidence_count
    assert retry_check.replay_claim_count == input_report.replay_claim_count
    assert destination_parent.is_dir()
    assert retry_destination.is_file()
    assert not destination.exists()
    assert _partial_names(destination_parent, destination) == ()
    _assert_artifacts_unchanged(protected_artifacts)
