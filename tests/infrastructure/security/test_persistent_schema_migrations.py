from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_migrate import (
    migrate_persistent_replay_database,
)
from infrastructure.security.persistent_replay_ops import (
    PersistentReplayReadinessError,
    check_database,
)
from infrastructure.security.persistent_replay_runtime import (
    create_persistent_replay_stores,
)
from infrastructure.security.persistent_schema import CURRENT_SCHEMA_VERSION


def _legacy_database(path: Path) -> tuple[str, str]:
    """Create the supported pre-versioned evidence/claim schema and seed data."""
    record = EvidenceRecord.create(
        evidence_id="learning-closed-loop:migration-test",
        kind="learning.closed_loop",
        source="tests.schema_migration",
        subject_id="result:migration-test",
        version="1.1.0",
        trace_id="trace:migration-test",
        collected_at="2026-11-27T00:00:00+00:00",
        payload={"cycle_id": "learning-cycle:migration-test", "status": "completed"},
    )
    encoded = json.dumps(
        record.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE sh3_evidence_records (
                evidence_id TEXT PRIMARY KEY NOT NULL,
                record_json TEXT NOT NULL,
                integrity TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE sh3_replay_claims (
                cycle_id TEXT PRIMARY KEY NOT NULL,
                fingerprint TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('claimed', 'completed', 'released')),
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
            "CREATE INDEX sh3_replay_claims_state_idx "
            "ON sh3_replay_claims(state, lease_expires_at)"
        )
        connection.execute(
            "INSERT INTO sh3_evidence_records "
            "(evidence_id, record_json, integrity) VALUES (?, ?, ?)",
            (record.evidence_id, encoded, record.integrity),
        )
        connection.execute(
            "INSERT INTO sh3_replay_claims "
            "(cycle_id, fingerprint, state, generation, attempts, owner_token, "
            "lease_expires_at, evidence_id, updated_at) "
            "VALUES (?, ?, 'released', 1, 1, NULL, NULL, NULL, ?)",
            ("learning-cycle:migration-test", "sha256:migration-test", time.time()),
        )
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 115000")
    return record.evidence_id, record.integrity


def _schema_version(path: Path) -> int:
    from infrastructure.security.persistent_schema import read_schema_version

    with sqlite3.connect(path) as connection:
        return read_schema_version(connection)


def _table_names(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {str(row[0]) for row in rows}


def test_readiness_is_read_only_and_runtime_refuses_unversioned_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.sqlite3"
    _legacy_database(database)
    before_tables = _table_names(database)

    with pytest.raises(PersistentReplayReadinessError, match="schema version 0"):
        check_database(database)
    with pytest.raises(PersistentReplayReadinessError, match="schema version 0"):
        create_persistent_replay_stores(database)

    assert _schema_version(database) == 0
    assert _table_names(database) == before_tables
    assert "sh3_replay_operations" not in before_tables


def test_migration_0_to_1_preserves_evidence_and_claim_rows_and_creates_backup(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.sqlite3"
    backup = tmp_path / "legacy-before-migration.sqlite3"
    evidence_id, integrity = _legacy_database(database)

    report = migrate_persistent_replay_database(
        database,
        backup,
        confirm_migration=True,
    )

    assert report.source_schema_version == 0
    assert report.target_schema_version == CURRENT_SCHEMA_VERSION == 1
    assert report.applied_migrations == ("0001_complete_replay_schema",)
    assert report.already_current is False
    assert report.backup_path == backup.resolve()
    assert backup.is_file()
    assert report.readiness.schema_version == 1
    assert report.readiness.evidence_count == 1
    assert report.readiness.replay_claim_count == 1
    assert _schema_version(database) == 1
    assert {
        "sh3_schema_metadata",
        "sh3_evidence_records",
        "sh3_replay_claims",
        "sh3_replay_stage_executions",
        "sh3_replay_operations",
        "sh3_replay_operation_plans",
    }.issubset(_table_names(database))

    with sqlite3.connect(database) as connection:
        migrated_evidence = connection.execute(
            "SELECT record_json, integrity FROM sh3_evidence_records WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        migrated_claim = connection.execute(
            "SELECT fingerprint, state, generation, attempts FROM sh3_replay_claims "
            "WHERE cycle_id = ?",
            ("learning-cycle:migration-test",),
        ).fetchone()
    assert migrated_evidence is not None
    assert migrated_evidence[1] == integrity
    assert migrated_claim == ("sha256:migration-test", "released", 1, 1)

    stores = create_persistent_replay_stores(database)
    assert stores.database_path == database.resolve()
    assert check_database(database).schema_version == 1


def test_migration_requires_explicit_confirmation_and_verified_backup_path(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    _legacy_database(database)

    with pytest.raises(ValueError, match="confirm_migration=True"):
        migrate_persistent_replay_database(database, backup)
    assert _schema_version(database) == 0
    assert not backup.exists()

    backup.write_bytes(b"operator-owned backup")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        migrate_persistent_replay_database(
            database, backup, confirm_migration=True
        )
    assert _schema_version(database) == 0
    assert backup.read_bytes() == b"operator-owned backup"


def test_migration_failure_rolls_back_schema_and_keeps_verified_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from infrastructure.security import persistent_replay_migrate as migration_module

    database = tmp_path / "legacy.sqlite3"
    backup = tmp_path / "legacy-backup.sqlite3"
    _legacy_database(database)
    original_apply = migration_module.apply_schema_v1

    def fail_after_ddl(connection: sqlite3.Connection) -> None:
        original_apply(connection)
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(migration_module, "apply_schema_v1", fail_after_ddl)
    with pytest.raises(RuntimeError, match="injected migration failure"):
        migrate_persistent_replay_database(
            database, backup, confirm_migration=True
        )

    assert backup.is_file()
    assert _schema_version(database) == 0
    assert "sh3_replay_stage_executions" not in _table_names(database)
    assert check_database(
        database, _allow_unversioned_schema=True
    ).schema_version == 0
    assert check_database(
        backup, _allow_unversioned_schema=True
    ).schema_version == 0


def test_migration_rejects_future_schema_version_without_mutation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "future.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    _legacy_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sh3_schema_metadata ("
                           "singleton INTEGER PRIMARY KEY CHECK (singleton = 1), "
                           "schema_version INTEGER NOT NULL CHECK (schema_version >= 1), "
                           "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        connection.execute("INSERT INTO sh3_schema_metadata "
                           "(singleton, schema_version) VALUES (1, 2)")
    before_tables = _table_names(database)

    with pytest.raises(PersistentReplayReadinessError, match="no supported migration path"):
        migrate_persistent_replay_database(
            database, backup, confirm_migration=True
        )

    assert _schema_version(database) == 2
    assert _table_names(database) == before_tables
    assert not backup.exists()


def test_migration_is_idempotent_after_schema_reaches_current_version(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.sqlite3"
    backup = tmp_path / "legacy-backup.sqlite3"
    _legacy_database(database)

    first = migrate_persistent_replay_database(
        database, backup, confirm_migration=True
    )
    second = migrate_persistent_replay_database(
        database, backup, confirm_migration=True
    )

    assert first.already_current is False
    assert second.already_current is True
    assert second.backup_path is None
    assert second.applied_migrations == ()
    assert _schema_version(database) == CURRENT_SCHEMA_VERSION


def test_provisioning_sets_authoritative_database_schema_version(
    tmp_path: Path,
) -> None:
    from infrastructure.security.persistent_replay_provision import (
        provision_persistent_replay_database,
    )

    database = tmp_path / "new.sqlite3"
    report = provision_persistent_replay_database(
        database, confirm_first_use=True
    )
    assert report.schema_version == CURRENT_SCHEMA_VERSION
    assert _schema_version(database) == CURRENT_SCHEMA_VERSION
