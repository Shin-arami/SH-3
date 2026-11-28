from __future__ import annotations

import argparse
import math
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from infrastructure.security.persistent_replay_ops import (
    DatabaseReadinessReport,
    PersistentReplayReadinessError,
    _create_verified_snapshot,
    check_database,
)
from infrastructure.security.persistent_schema import (
    CURRENT_SCHEMA_VERSION,
    PersistentSchemaError,
    apply_schema_v1,
    read_schema_version,
    validate_schema_v1_objects,
)

__all__ = [
    "PersistentReplayMigrationReport",
    "apply_schema_v1",
    "main",
    "migrate_persistent_replay_database",
]

_DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class PersistentReplayMigrationReport:
    database_path: Path
    backup_path: Path | None
    source_schema_version: int
    target_schema_version: int
    applied_migrations: tuple[str, ...]
    already_current: bool
    readiness: DatabaseReadinessReport


def _timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("timeout_seconds must be a real number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout_seconds must be finite and greater than zero")
    return float(value)


def migrate_persistent_replay_database(
    database_path: str | PathLike[str],
    backup_path: str | PathLike[str],
    *,
    confirm_migration: bool = False,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> PersistentReplayMigrationReport:
    """Back up and transactionally migrate a supported version-0 database.

    Version-0 means a pre-versioned SH-3 database whose existing tables pass
    the read-only legacy schema/data checks. The only supported upgrade in this
    release is 0 -> 1. A migration backup is published and verified before any
    DDL is executed. DDL and the `sh3_schema_metadata.schema_version` update are committed in one transaction. The existing `PRAGMA user_version` value is preserved unchanged.
    """
    if not isinstance(confirm_migration, bool):
        raise TypeError("confirm_migration must be bool")
    if not confirm_migration:
        raise ValueError("migration requires confirm_migration=True")
    timeout = _timeout(timeout_seconds)

    requested_source = Path(database_path).expanduser()
    if requested_source.is_symlink():
        raise ValueError("database_path must not be a symbolic link")
    source = requested_source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"database file does not exist: {source}")

    connection = sqlite3.connect(
        source,
        timeout=timeout,
        isolation_level=None,
    )
    try:
        connection.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        source_version = read_schema_version(connection)

        if source_version == CURRENT_SCHEMA_VERSION:
            connection.execute("ROLLBACK")
            readiness = check_database(source, timeout_seconds=timeout)
            return PersistentReplayMigrationReport(
                database_path=source,
                backup_path=None,
                source_schema_version=source_version,
                target_schema_version=CURRENT_SCHEMA_VERSION,
                applied_migrations=(),
                already_current=True,
                readiness=readiness,
            )
        if source_version != 0:
            raise PersistentReplayReadinessError(
                f"database schema version {source_version} has no supported migration path"
            )

        # The write reservation prevents another process from changing the
        # source between legacy preflight, online backup, and migration commit.
        check_database(
            source,
            timeout_seconds=timeout,
            _allow_unversioned_schema=True,
        )
        backup = _create_verified_snapshot(
            source,
            backup_path,
            timeout_seconds=timeout,
            _allow_unversioned_schema=True,
        )

        apply_schema_v1(connection)
        validate_schema_v1_objects(connection)
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()

    readiness = check_database(source, timeout_seconds=timeout)
    return PersistentReplayMigrationReport(
        database_path=source,
        backup_path=backup.database_path,
        source_schema_version=source_version,
        target_schema_version=CURRENT_SCHEMA_VERSION,
        applied_migrations=("0001_complete_replay_schema",),
        already_current=False,
        readiness=readiness,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Back up and migrate a supported pre-versioned SH-3 persistent replay database."
        )
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument(
        "--confirm-migration",
        action="store_true",
        required=True,
        help="confirm the explicit version-0 to version-1 database migration",
    )
    parser.add_argument(
        "--timeout-seconds", type=float, default=_DEFAULT_TIMEOUT_SECONDS
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = migrate_persistent_replay_database(
            args.database,
            args.backup,
            confirm_migration=args.confirm_migration,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, TypeError, ValueError, sqlite3.Error, PersistentReplayReadinessError, PersistentSchemaError) as exc:
        print(f"MIGRATION: FAIL: {exc}", file=sys.stderr)
        return 1
    print("MIGRATION: ALREADY CURRENT" if report.already_current else "MIGRATION: PASS")
    print(f"database={report.database_path}")
    print(f"source_schema_version={report.source_schema_version}")
    print(f"target_schema_version={report.target_schema_version}")
    print(f"backup={report.backup_path if report.backup_path is not None else 'not-created'}")
    print(f"applied_migrations={','.join(report.applied_migrations) or 'none'}")
    print(f"evidence_records={report.readiness.evidence_count}")
    print(f"replay_claims={report.readiness.replay_claim_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
