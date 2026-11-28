from __future__ import annotations

import sqlite3
from os import PathLike
from pathlib import Path

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "PersistentSchemaError",
    "PersistentSchemaMigrationRequiredError",
    "UnsupportedPersistentSchemaVersionError",
    "apply_schema_v1",
    "ensure_schema_for_store",
    "read_schema_version",
    "validate_schema_v1_objects",
]

CURRENT_SCHEMA_VERSION = 1
_SCHEMA_METADATA_TABLE = "sh3_schema_metadata"
_SCHEMA_TABLES = frozenset(
    {
        _SCHEMA_METADATA_TABLE,
        "sh3_evidence_records",
        "sh3_replay_claims",
        "sh3_replay_stage_executions",
        "sh3_replay_operations",
        "sh3_replay_operation_plans",
    }
)
_SCHEMA_INDEXES = frozenset(
    {
        "sh3_replay_claims_state_idx",
        "sh3_replay_stage_cycle_state_idx",
        "sh3_replay_operations_cycle_state_idx",
        "sh3_replay_operations_parent_stage_idx",
    }
)


class PersistentSchemaError(RuntimeError):
    """Base error for an unsupported or incomplete persistent database schema."""


class PersistentSchemaMigrationRequiredError(PersistentSchemaError):
    """Raised when an existing unversioned database requires explicit migration."""


class UnsupportedPersistentSchemaVersionError(PersistentSchemaError):
    """Raised when the database schema version is newer or otherwise unsupported."""


def _user_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        if not str(row[0]).startswith("sqlite_")
    }


def read_schema_version(connection: sqlite3.Connection) -> int:
    """Read SH-3's schema version without taking ownership of PRAGMA user_version.

    Historical SH-3 snapshot/restore contracts preserve ``PRAGMA user_version``
    as an independent SQLite application marker. Schema lifecycle metadata is
    therefore kept in the dedicated ``sh3_schema_metadata`` table.
    """
    metadata_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (_SCHEMA_METADATA_TABLE,),
    ).fetchone()
    if metadata_exists is None:
        return 0

    columns = {
        str(row[1])
        for row in connection.execute(
            f"PRAGMA table_info({_SCHEMA_METADATA_TABLE})"
        )
    }
    if not {"singleton", "schema_version", "updated_at"}.issubset(columns):
        raise PersistentSchemaError(
            "schema metadata table has an incompatible column layout"
        )

    rows = connection.execute(
        f"SELECT singleton, schema_version FROM {_SCHEMA_METADATA_TABLE}"
    ).fetchall()
    if len(rows) != 1 or rows[0][0] != 1:
        raise PersistentSchemaError(
            "schema metadata table must contain exactly one singleton row"
        )
    version_value = rows[0][1]
    if isinstance(version_value, bool) or not isinstance(version_value, int):
        raise PersistentSchemaError("database schema version must be an integer")
    return int(version_value)


def validate_schema_v1_objects(connection: sqlite3.Connection) -> None:
    tables = _user_tables(connection)
    missing_tables = _SCHEMA_TABLES - tables
    if missing_tables:
        raise PersistentSchemaError(
            "version-1 database is missing table(s): "
            + ", ".join(sorted(missing_tables))
        )
    indexes = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
    }
    missing_indexes = _SCHEMA_INDEXES - indexes
    if missing_indexes:
        raise PersistentSchemaError(
            "version-1 database is missing index(es): "
            + ", ".join(sorted(missing_indexes))
        )


def apply_schema_v1(connection: sqlite3.Connection) -> None:
    """Apply the complete schema without changing existing rows.

    This function is used only by first-use initialization and the explicit
    migration runner. DDL and the SH-3 schema metadata row participate in the
    caller's transaction when one is already active. PRAGMA user_version is
    intentionally left untouched for backward compatibility.
    """
    owns_transaction = not connection.in_transaction
    if owns_transaction:
        connection.execute("BEGIN IMMEDIATE")
    try:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS sh3_schema_metadata (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sh3_evidence_records (
                evidence_id TEXT PRIMARY KEY NOT NULL,
                record_json TEXT NOT NULL,
                integrity TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sh3_replay_claims (
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
            """,
            "CREATE INDEX IF NOT EXISTS sh3_replay_claims_state_idx "
            "ON sh3_replay_claims(state, lease_expires_at)",
            """
            CREATE TABLE IF NOT EXISTS sh3_replay_stage_executions (
                idempotency_key TEXT PRIMARY KEY NOT NULL,
                cycle_id TEXT NOT NULL,
                cycle_fingerprint TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('claimed', 'completed')),
                generation INTEGER NOT NULL CHECK (generation >= 1),
                attempts INTEGER NOT NULL CHECK (attempts >= 1),
                owner_token TEXT,
                result_json TEXT,
                result_integrity TEXT,
                updated_at REAL NOT NULL,
                FOREIGN KEY (cycle_id) REFERENCES sh3_replay_claims(cycle_id),
                CHECK (
                    (state = 'claimed' AND owner_token IS NOT NULL
                     AND result_json IS NULL AND result_integrity IS NULL)
                    OR
                    (state = 'completed' AND owner_token IS NULL
                     AND result_json IS NOT NULL AND result_integrity IS NOT NULL)
                )
            )
            """,
            "CREATE INDEX IF NOT EXISTS sh3_replay_stage_cycle_state_idx "
            "ON sh3_replay_stage_executions(cycle_id, state)",
            """
            CREATE TABLE IF NOT EXISTS sh3_replay_operations (
                tenant_scope TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                cycle_fingerprint TEXT NOT NULL,
                parent_stage_key TEXT NOT NULL,
                operation_kind TEXT NOT NULL CHECK (operation_kind IN ('action', 'rollback')),
                operation_name TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
                parent_operation_key TEXT,
                input_fingerprint TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('claimed', 'completed')),
                generation INTEGER NOT NULL CHECK (generation >= 1),
                attempts INTEGER NOT NULL CHECK (attempts >= 1),
                owner_token TEXT,
                result_json TEXT,
                result_integrity TEXT,
                updated_at REAL NOT NULL,
                PRIMARY KEY (tenant_scope, idempotency_key),
                FOREIGN KEY (cycle_id) REFERENCES sh3_replay_claims(cycle_id),
                FOREIGN KEY (parent_stage_key)
                    REFERENCES sh3_replay_stage_executions(idempotency_key),
                FOREIGN KEY (tenant_scope, parent_operation_key)
                    REFERENCES sh3_replay_operations(tenant_scope, idempotency_key),
                CHECK (
                    (operation_kind = 'action' AND parent_operation_key IS NULL)
                    OR
                    (operation_kind = 'rollback' AND parent_operation_key IS NOT NULL)
                ),
                CHECK (
                    (state = 'claimed' AND owner_token IS NOT NULL
                     AND result_json IS NULL AND result_integrity IS NULL)
                    OR
                    (state = 'completed' AND owner_token IS NULL
                     AND result_json IS NOT NULL AND result_integrity IS NOT NULL)
                )
            )
            """,
            "CREATE INDEX IF NOT EXISTS sh3_replay_operations_cycle_state_idx "
            "ON sh3_replay_operations(cycle_id, state)",
            "CREATE INDEX IF NOT EXISTS sh3_replay_operations_parent_stage_idx "
            "ON sh3_replay_operations(parent_stage_key, operation_kind, ordinal)",
            """
            CREATE TABLE IF NOT EXISTS sh3_replay_operation_plans (
                tenant_scope TEXT NOT NULL,
                parent_stage_key TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                cycle_fingerprint TEXT NOT NULL,
                plan_version INTEGER NOT NULL CHECK (plan_version >= 1),
                actions_json TEXT NOT NULL,
                actions_integrity TEXT NOT NULL,
                generation INTEGER NOT NULL CHECK (generation >= 1),
                owner_token TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (tenant_scope, parent_stage_key),
                FOREIGN KEY (cycle_id) REFERENCES sh3_replay_claims(cycle_id),
                FOREIGN KEY (parent_stage_key)
                    REFERENCES sh3_replay_stage_executions(idempotency_key)
            )
            """,
        )
        for statement in statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO sh3_schema_metadata (singleton, schema_version) "
            "VALUES (1, ?) ON CONFLICT(singleton) DO NOTHING",
            (CURRENT_SCHEMA_VERSION,),
        )
        version = read_schema_version(connection)
        if version != CURRENT_SCHEMA_VERSION:
            raise UnsupportedPersistentSchemaVersionError(
                f"database schema version {version} is not supported by this migration"
            )
        validate_schema_v1_objects(connection)
        if owns_transaction:
            connection.execute("COMMIT")
    except Exception:
        if owns_transaction and connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def ensure_schema_for_store(
    database_path: str | PathLike[str],
    *,
    timeout_seconds: float,
) -> None:
    """Validate an existing schema or initialize only a truly empty database.

    Existing unversioned SH-3 databases are never repaired by a store
    constructor. They must go through the explicit migration command.
    """
    path = Path(database_path)
    existed_before = path.exists()
    was_empty_file = existed_before and path.stat().st_size == 0
    try:
        connection = sqlite3.connect(
            path,
            timeout=timeout_seconds,
            isolation_level=None,
        )
    except sqlite3.Error:
        raise
    try:
        connection.execute(f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}")
        connection.execute("PRAGMA foreign_keys = ON")
        version = read_schema_version(connection)
        tables = _user_tables(connection)
        if version == CURRENT_SCHEMA_VERSION:
            validate_schema_v1_objects(connection)
            return
        if version != 0:
            raise UnsupportedPersistentSchemaVersionError(
                f"database schema version {version} is unsupported; "
                f"this build supports version {CURRENT_SCHEMA_VERSION}"
            )
        if tables:
            raise PersistentSchemaMigrationRequiredError(
                "existing database has schema version 0 and requires the explicit "
                "persistent replay migration command; store constructors do not "
                "upgrade existing databases"
            )
        if existed_before and not was_empty_file:
            raise PersistentSchemaError(
                "refusing to initialize a non-empty SQLite file with no schema; "
                "use explicit first-use provisioning for a new database"
            )
        connection.execute("PRAGMA journal_mode = WAL")
        apply_schema_v1(connection)
    finally:
        connection.close()
