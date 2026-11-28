from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _partial_artifact_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


def _evidence_count(database: Path) -> int:
    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
        isolation_level=None,
    )
    try:
        row = connection.execute(
            "SELECT COUNT(*) FROM sh3_evidence_records"
        ).fetchone()
        assert row is not None
        return int(row[0])
    finally:
        connection.close()


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_preexisting_destination_is_rejected_before_snapshot_allocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"preexisting-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"preexisting-{scenario}-input.sqlite3"
    destination = tmp_path / f"preexisting-{scenario}-destination.sqlite3"
    _initialize_database(source)
    SQLiteEvidenceStore(source).register(
        EvidenceRecord.create(
            evidence_id=f"part11-123-source-{scenario}",
            kind="preflight-contract",
            source="source",
            subject_id="source-database",
            collected_at="2026-10-23T00:00:00+00:00",
            payload={"part": 123, "role": "source"},
        )
    )

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
    else:
        input_database = source

    _initialize_database(destination)
    SQLiteEvidenceStore(destination).register(
        EvidenceRecord.create(
            evidence_id=f"part11-123-existing-destination-{scenario}",
            kind="preflight-contract",
            source="existing-destination",
            subject_id="protected-destination",
            collected_at="2026-10-23T00:00:01+00:00",
            payload={"part": 123, "role": "destination"},
        )
    )
    SQLiteEvidenceStore(destination).register(
        EvidenceRecord.create(
            evidence_id=f"part11-123-existing-destination-extra-{scenario}",
            kind="preflight-contract",
            source="existing-destination",
            subject_id="protected-destination-extra",
            collected_at="2026-10-23T00:00:02+00:00",
            payload={"part": 123, "role": "destination-extra"},
        )
    )

    source_bytes = input_database.read_bytes()
    destination_bytes = destination.read_bytes()
    source_count = _evidence_count(input_database)
    destination_count = _evidence_count(destination)
    partials_before = _partial_artifact_names(tmp_path, destination)
    assert partials_before == ()
    assert source_count != destination_count

    calls = {"mkstemp": 0, "link": 0}

    def unexpected_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
        calls["mkstemp"] += 1
        raise AssertionError(
            "snapshot temporary allocation must not happen when destination exists"
        )

    def unexpected_link(
        source_path: str | os.PathLike[str],
        destination_path: str | os.PathLike[str],
        *,
        follow_symlinks: bool = True,
    ) -> None:
        del source_path, destination_path, follow_symlinks
        calls["link"] += 1
        raise AssertionError(
            "snapshot publication must not happen when destination exists"
        )

    monkeypatch.setattr(tempfile, "mkstemp", unexpected_mkstemp)
    monkeypatch.setattr(os, "link", unexpected_link)

    with pytest.raises(
        FileExistsError,
        match="refusing to overwrite existing destination",
    ) as caught:
        if scenario == "backup-destination":
            replay_ops.backup_database(input_database, destination)
        else:
            replay_ops.restore_database(input_database, destination)

    assert str(destination.resolve()) in str(caught.value)
    assert caught.value.__cause__ is None
    assert calls == {"mkstemp": 0, "link": 0}
    assert input_database.read_bytes() == source_bytes
    assert destination.read_bytes() == destination_bytes
    assert _evidence_count(input_database) == source_count
    assert _evidence_count(destination) == destination_count
    assert _partial_artifact_names(tmp_path, destination) == partials_before
