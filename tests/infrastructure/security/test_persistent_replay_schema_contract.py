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


def test_check_rejects_evidence_table_without_canonical_primary_key(
    tmp_path: Path,
) -> None:
    database = tmp_path / "evidence-without-primary-key.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE sh3_evidence_records ("
            "evidence_id TEXT NOT NULL, record_json TEXT NOT NULL, "
            "integrity TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
    SQLiteReplayClaimStore(database)

    with pytest.raises(
        PersistentReplayReadinessError,
        match="sh3_evidence_records must use evidence_id as its sole primary key",
    ):
        check_database(database)


def test_check_rejects_claim_table_without_canonical_primary_key(
    tmp_path: Path,
) -> None:
    database = tmp_path / "claims-without-primary-key.sqlite3"
    SQLiteEvidenceStore(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE sh3_replay_claims ("
            "cycle_id TEXT NOT NULL, fingerprint TEXT NOT NULL, "
            "state TEXT NOT NULL, generation INTEGER NOT NULL, "
            "attempts INTEGER NOT NULL, owner_token TEXT, "
            "lease_expires_at REAL, evidence_id TEXT, updated_at REAL NOT NULL)"
        )

    with pytest.raises(
        PersistentReplayReadinessError,
        match="sh3_replay_claims must use cycle_id as its sole primary key",
    ):
        check_database(database)


def test_check_rejects_nullable_required_evidence_column(tmp_path: Path) -> None:
    database = tmp_path / "nullable-evidence-column.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE sh3_evidence_records ("
            "evidence_id TEXT PRIMARY KEY NOT NULL, record_json TEXT, "
            "integrity TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
    SQLiteReplayClaimStore(database)

    with pytest.raises(
        PersistentReplayReadinessError,
        match="NOT NULL columns in sh3_evidence_records: record_json",
    ):
        check_database(database)


def test_check_accepts_store_created_schema(tmp_path: Path) -> None:
    database = tmp_path / "canonical-schema.sqlite3"
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)

    report = check_database(database)

    assert report.evidence_count == 0
    assert report.replay_claim_count == 0


def test_check_rejects_nullable_required_claim_column(tmp_path: Path) -> None:
    database = tmp_path / "nullable-claim-column.sqlite3"
    SQLiteEvidenceStore(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE sh3_replay_claims ("
            "cycle_id TEXT PRIMARY KEY NOT NULL, fingerprint TEXT, "
            "state TEXT NOT NULL CHECK (state IN ('claimed', 'completed', "
            "'released')), "
            "generation INTEGER NOT NULL, attempts INTEGER NOT NULL, "
            "owner_token TEXT, lease_expires_at REAL, evidence_id TEXT, "
            "updated_at REAL NOT NULL)"
        )

    with pytest.raises(
        PersistentReplayReadinessError,
        match="NOT NULL columns in sh3_replay_claims: fingerprint",
    ):
        check_database(database)
