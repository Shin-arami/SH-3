from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialize_database(database: Path, cycle_suffix: str) -> None:
    SQLiteEvidenceStore(database)
    claims = SQLiteReplayClaimStore(database)
    claims.claim(
        f"learning-cycle:part11-137-{cycle_suffix}",
        f"sha256:part11-137-{cycle_suffix}",
        lease_seconds=3600.0,
    )


def _capture_artifacts(databases: tuple[Path, ...]) -> dict[Path, bytes | None]:
    expected: dict[Path, bytes | None] = {}
    for database in databases:
        for suffix in ("", "-wal", "-shm", "-journal"):
            artifact = database if not suffix else Path(f"{database}{suffix}")
            expected[artifact] = artifact.read_bytes() if artifact.is_file() else None
    return expected


def _assert_artifacts_unchanged(expected: dict[Path, bytes | None]) -> None:
    for artifact, expected_bytes in expected.items():
        if expected_bytes is None:
            assert not artifact.exists()
        else:
            assert artifact.is_file()
            assert artifact.read_bytes() == expected_bytes


def _matching_partials(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            item.name
            for item in directory.iterdir()
            if item.name.startswith(prefix) and ".partial" in item.name
        )
    )


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_source_identity_is_rechecked_after_snapshot_verification_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"identity-before-publish-{scenario}-source.sqlite3"
    backup = tmp_path / f"identity-before-publish-{scenario}-backup.sqlite3"
    destination = tmp_path / f"identity-before-publish-{scenario}-destination.sqlite3"
    _initialize_database(source, scenario)

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup)
        input_database = backup
        protected_databases: tuple[Path, ...] = (source, backup)
    else:
        input_database = source
        protected_databases = (source,)

    input_report = replay_ops.check_database(input_database)
    protected_artifacts = _capture_artifacts(protected_databases)
    assert not destination.exists()
    assert _matching_partials(tmp_path, destination) == ()

    original_identity = replay_ops._source_file_identity
    original_check_database = replay_ops.check_database
    original_link = os.link
    snapshot_verified = False
    snapshot_verification_paths: list[Path] = []
    publication_attempts: list[tuple[Path, Path]] = []

    def drift_identity(path: Path) -> tuple[int, int]:
        identity = original_identity(path)
        if snapshot_verified and path.resolve() == input_database.resolve():
            return identity[0], identity[1] + 1
        return identity

    def record_snapshot_verification(
        database_path: str | os.PathLike[str],
        *,
        timeout_seconds: float = 5.0,
        _connection: sqlite3.Connection | None = None,
    ) -> replay_ops.DatabaseReadinessReport:
        nonlocal snapshot_verified
        report = original_check_database(
            database_path,
            timeout_seconds=timeout_seconds,
            _connection=_connection,
        )
        candidate = Path(database_path).resolve()
        if (
            _connection is None
            and candidate != input_database.resolve()
            and candidate.parent == tmp_path.resolve()
            and candidate.name.startswith(f".{destination.name}.")
            and candidate.name.endswith(".partial")
        ):
            snapshot_verification_paths.append(candidate)
            snapshot_verified = True
        return report

    def record_publication(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
    ) -> None:
        publication_attempts.append((Path(source_path), Path(destination_path)))
        original_link(source_path, destination_path)

    def publish(target: Path) -> replay_ops.DatabaseReadinessReport:
        if scenario == "backup-destination":
            return replay_ops.backup_database(input_database, target)
        return replay_ops.restore_database(input_database, target)

    with monkeypatch.context() as patch:
        patch.setattr(replay_ops, "_source_file_identity", drift_identity)
        patch.setattr(replay_ops, "check_database", record_snapshot_verification)
        patch.setattr(os, "link", record_publication)
        with pytest.raises(
            replay_ops.PersistentReplayReadinessError,
            match="source database file identity changed before snapshot publication",
        ):
            publish(destination)

    assert snapshot_verified
    assert len(snapshot_verification_paths) == 1
    assert snapshot_verification_paths[0].parent == tmp_path.resolve()
    assert publication_attempts == []
    assert not destination.exists()
    assert _matching_partials(tmp_path, destination) == ()
    _assert_artifacts_unchanged(protected_artifacts)

    # Retry to the same destination after removing the injected identity drift.
    retry_report = publish(destination)
    checked_destination = replay_ops.check_database(destination)
    assert retry_report.database_path == destination.resolve()
    assert retry_report.evidence_count == input_report.evidence_count
    assert retry_report.replay_claim_count == input_report.replay_claim_count
    assert checked_destination.evidence_count == input_report.evidence_count
    assert checked_destination.replay_claim_count == input_report.replay_claim_count
    assert destination.is_file()
    assert _matching_partials(tmp_path, destination) == ()
    _assert_artifacts_unchanged(protected_artifacts)
