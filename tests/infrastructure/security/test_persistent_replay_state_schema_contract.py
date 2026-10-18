from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from infrastructure.security.persistent_replay_ops import (
    PersistentReplayReadinessError,
    check_database,
)
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialized_database(database: Path) -> Path:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)
    return database


def test_check_accepts_adapter_state_constraint_and_index(tmp_path: Path) -> None:
    database = _initialized_database(tmp_path / "valid-state-schema.sqlite3")

    report = check_database(database)

    assert report.evidence_count == 0
    assert report.replay_claim_count == 0


def test_check_rejects_replay_claim_table_without_state_check_constraint(
    tmp_path: Path,
) -> None:
    database = _initialized_database(tmp_path / "missing-state-check.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX sh3_replay_claims_state_idx")
        connection.execute(
            "ALTER TABLE sh3_replay_claims RENAME TO sh3_replay_claims_old"
        )
        connection.execute(
            """
            CREATE TABLE sh3_replay_claims (
                cycle_id TEXT PRIMARY KEY NOT NULL,
                fingerprint TEXT NOT NULL,
                state TEXT NOT NULL,
                generation INTEGER NOT NULL,
                attempts INTEGER NOT NULL,
                owner_token TEXT,
                lease_expires_at REAL,
                evidence_id TEXT,
                updated_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO sh3_replay_claims SELECT * FROM sh3_replay_claims_old"
        )
        connection.execute("DROP TABLE sh3_replay_claims_old")
        connection.execute(
            "CREATE INDEX sh3_replay_claims_state_idx "
            "ON sh3_replay_claims(state, lease_expires_at)"
        )

    with pytest.raises(
        PersistentReplayReadinessError,
        match="does not enforce the required replay claim states",
    ):
        check_database(database)


def test_check_rejects_missing_replay_claim_state_index(tmp_path: Path) -> None:
    database = _initialized_database(tmp_path / "missing-state-index.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX sh3_replay_claims_state_idx")

    with pytest.raises(
        PersistentReplayReadinessError,
        match="missing required index sh3_replay_claims_state_idx",
    ):
        check_database(database)


def test_check_rejects_replay_claim_state_index_with_wrong_column_order(
    tmp_path: Path,
) -> None:
    database = _initialized_database(tmp_path / "wrong-state-index.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX sh3_replay_claims_state_idx")
        connection.execute(
            "CREATE INDEX sh3_replay_claims_state_idx "
            "ON sh3_replay_claims(lease_expires_at, state)"
        )

    with pytest.raises(
        PersistentReplayReadinessError,
        match="must use ordered columns",
    ):
        check_database(database)


def test_check_rejects_partial_replay_claim_state_index(tmp_path: Path) -> None:
    database = _initialized_database(tmp_path / "partial-state-index.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX sh3_replay_claims_state_idx")
        connection.execute(
            "CREATE INDEX sh3_replay_claims_state_idx "
            "ON sh3_replay_claims(state, lease_expires_at) "
            "WHERE state = 'claimed'"
        )

    with pytest.raises(
        PersistentReplayReadinessError,
        match="must be non-unique and non-partial",
    ):
        check_database(database)
