from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any, cast

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialize_database(database: Path, cycle_id: str) -> None:
    SQLiteEvidenceStore(database)
    claims = SQLiteReplayClaimStore(database)
    claims.claim(
        cycle_id,
        f"sha256:{cycle_id}",
        lease_seconds=3600.0,
    )


def _operation(
    scenario: str,
    source: Path,
    backup_input: Path,
    destination: Path,
) -> replay_ops.DatabaseReadinessReport:
    if scenario == "backup-destination":
        return replay_ops.backup_database(source, destination)
    return replay_ops.restore_database(backup_input, destination)


def _partial_artifacts(directory: Path, destination: Path) -> tuple[Path, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_source_connection_close_failure_after_successful_online_backup_prevents_publication_and_retry_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    source = tmp_path / f"post-backup-close-{scenario}-source.sqlite3"
    backup_input = tmp_path / f"post-backup-close-{scenario}-input.sqlite3"
    destination = tmp_path / f"post-backup-close-{scenario}-destination.sqlite3"
    _initialize_database(source, f"learning-cycle:part11-136-{scenario}")

    if scenario == "restore-destination":
        replay_ops.backup_database(source, backup_input)
        input_database = backup_input
        protected_databases: tuple[Path, ...] = (source, backup_input)
    else:
        input_database = source
        protected_databases = (source,)

    expected_report = replay_ops.check_database(input_database)
    assert expected_report.replay_claim_count == 1
    protected_bytes = {
        database: database.read_bytes() for database in protected_databases
    }
    allocated_temporaries: list[Path] = []
    close_calls: list[sqlite3.Connection] = []
    copied_claim_counts: list[int] = []
    close_error_text = "injected destination close failure after successful backup"
    original_connect = sqlite3.connect
    original_mkstemp = tempfile.mkstemp

    class FailingCloseConnection(sqlite3.Connection):
        def close(self) -> None:
            close_calls.append(self)
            row = self.execute(
                "SELECT COUNT(*) FROM sh3_replay_claims"
            ).fetchone()
            assert row is not None
            copied_claim_counts.append(int(row[0]))
            super().close()
            raise sqlite3.OperationalError(close_error_text)

    def record_mkstemp(*args: Any, **kwargs: Any) -> tuple[int, str]:
        descriptor, name = original_mkstemp(*args, **kwargs)
        allocated_temporaries.append(Path(name))
        return descriptor, name

    def tracked_connect(
        database: str | Path,
        *args: Any,
        **kwargs: Any,
    ) -> sqlite3.Connection:
        if (
            allocated_temporaries
            and not kwargs.get("uri", False)
            and Path(database) == allocated_temporaries[-1]
        ):
            kwargs["factory"] = FailingCloseConnection
        return cast(sqlite3.Connection, original_connect(database, *args, **kwargs))

    with monkeypatch.context() as patch:
        patch.setattr(tempfile, "mkstemp", record_mkstemp)
        patch.setattr(sqlite3, "connect", tracked_connect)
        with pytest.raises(sqlite3.OperationalError, match=close_error_text):
            _operation(scenario, source, backup_input, destination)

    assert len(allocated_temporaries) == 1
    temporary = allocated_temporaries[0]
    assert len(close_calls) == 1
    assert copied_claim_counts == [1]
    assert not temporary.exists()
    assert _partial_artifacts(tmp_path, destination) == ()
    assert not destination.exists()
    for database, original_bytes in protected_bytes.items():
        assert database.is_file()
        assert database.read_bytes() == original_bytes

    # Once the injected close failure is removed, the same destination is reusable.
    result = _operation(scenario, source, backup_input, destination)
    checked = replay_ops.check_database(destination)
    assert result.database_path == destination.resolve()
    assert result.replay_claim_count == expected_report.replay_claim_count == 1
    assert checked.replay_claim_count == 1
    assert checked.evidence_count == expected_report.evidence_count
    assert _partial_artifacts(tmp_path, destination) == ()
    for database, original_bytes in protected_bytes.items():
        assert database.read_bytes() == original_bytes
