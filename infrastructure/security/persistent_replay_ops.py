from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
import tempfile
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from infrastructure.security import EvidenceRecord

__all__ = [
    "DatabaseReadinessReport",
    "PersistentReplayReadinessError",
    "backup_database",
    "check_database",
    "main",
    "restore_database",
]

_EVIDENCE_TABLE = "sh3_evidence_records"
_CLAIM_TABLE = "sh3_replay_claims"
_EVIDENCE_COLUMNS = {"evidence_id", "record_json", "integrity", "created_at"}
_CLAIM_COLUMNS = {
    "cycle_id",
    "fingerprint",
    "state",
    "generation",
    "attempts",
    "owner_token",
    "lease_expires_at",
    "evidence_id",
    "updated_at",
}
_CLAIM_STATES = {"claimed", "completed", "released"}
_DEFAULT_TIMEOUT_SECONDS = 5.0


class PersistentReplayReadinessError(RuntimeError):
    """Raised when a persistent replay database fails an operational check."""


@dataclass(frozen=True, slots=True)
class DatabaseReadinessReport:
    database_path: Path
    sqlite_version: str
    journal_mode: str
    evidence_count: int
    replay_claim_count: int
    expired_claim_count: int


def _timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("timeout_seconds must be a real number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout_seconds must be finite and greater than zero")
    return float(value)


def _existing_database(path_value: str | os.PathLike[str]) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"SQLite database file does not exist: {path}")
    return path


@contextmanager
def _readonly_connection(
    path: Path,
    *,
    timeout_seconds: float,
) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(
        f"{path.as_uri()}?mode=ro",
        uri=True,
        timeout=timeout_seconds,
        isolation_level=None,
    )
    try:
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}")
        yield connection
    finally:
        connection.close()


def _require_columns(
    connection: sqlite3.Connection,
    table: str,
    required: set[str],
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    actual = {str(row["name"]) for row in rows}
    if not required.issubset(actual):
        missing = ", ".join(sorted(required - actual))
        raise PersistentReplayReadinessError(
            f"database schema is missing required columns in {table}: {missing}"
        )



def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value

def _validate_claim(row: sqlite3.Row, now: float) -> bool:
    cycle_id = row["cycle_id"]
    fingerprint = row["fingerprint"]
    state = row["state"]
    generation = row["generation"]
    attempts = row["attempts"]
    owner_token = row["owner_token"]
    lease_expires_at = row["lease_expires_at"]
    evidence_id = row["evidence_id"]

    if not isinstance(cycle_id, str) or not cycle_id.strip():
        raise PersistentReplayReadinessError("replay claim has an empty cycle_id")
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        raise PersistentReplayReadinessError(
            f"replay claim has an empty fingerprint: {cycle_id}"
        )
    if state not in _CLAIM_STATES:
        raise PersistentReplayReadinessError(
            f"replay claim has an unknown state: {cycle_id}"
        )
    if not isinstance(generation, int) or generation < 1:
        raise PersistentReplayReadinessError(
            f"replay claim has an invalid generation: {cycle_id}"
        )
    if not isinstance(attempts, int) or attempts < 0:
        raise PersistentReplayReadinessError(
            f"replay claim has an invalid attempt count: {cycle_id}"
        )

    if state == "claimed":
        if not isinstance(owner_token, str) or not owner_token.strip():
            raise PersistentReplayReadinessError(
                f"claimed replay has no owner token: {cycle_id}"
            )
        if (
            not isinstance(lease_expires_at, (int, float))
            or isinstance(lease_expires_at, bool)
            or not math.isfinite(float(lease_expires_at))
        ):
            raise PersistentReplayReadinessError(
                f"claimed replay has an invalid lease expiry: {cycle_id}"
            )
        if evidence_id is not None:
            raise PersistentReplayReadinessError(
                f"claimed replay unexpectedly references terminal evidence: {cycle_id}"
            )
        return float(lease_expires_at) <= now

    if owner_token is not None or lease_expires_at is not None:
        raise PersistentReplayReadinessError(
            f"non-claimed replay retains active lease ownership: {cycle_id}"
        )
    if state == "completed" and (
        not isinstance(evidence_id, str) or not evidence_id.strip()
    ):
        raise PersistentReplayReadinessError(
            f"completed replay has no terminal evidence identifier: {cycle_id}"
        )
    if state == "released" and evidence_id is not None:
        raise PersistentReplayReadinessError(
            f"released replay unexpectedly references terminal evidence: {cycle_id}"
        )
    return False


def check_database(
    database_path: str | os.PathLike[str],
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> DatabaseReadinessReport:
    """Run read-only SQLite and SH-3 evidence/claim consistency checks."""
    timeout = _timeout(timeout_seconds)
    path = _existing_database(database_path)
    try:
        with _readonly_connection(path, timeout_seconds=timeout) as connection:
            connection.execute("BEGIN")
            try:
                integrity_rows = tuple(
                    str(row[0]) for row in connection.execute("PRAGMA integrity_check")
                )
                if integrity_rows != ("ok",):
                    raise PersistentReplayReadinessError(
                        "SQLite integrity_check failed: "
                        + "; ".join(integrity_rows[:5])
                    )
                foreign_key_errors = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                if foreign_key_errors:
                    raise PersistentReplayReadinessError(
                        "SQLite foreign_key_check found "
                        f"{len(foreign_key_errors)} violation(s)"
                    )

                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                missing_tables = {_EVIDENCE_TABLE, _CLAIM_TABLE} - tables
                if missing_tables:
                    raise PersistentReplayReadinessError(
                        "database is missing SH-3 table(s): "
                        + ", ".join(sorted(missing_tables))
                    )
                _require_columns(connection, _EVIDENCE_TABLE, _EVIDENCE_COLUMNS)
                _require_columns(connection, _CLAIM_TABLE, _CLAIM_COLUMNS)

                evidence_count = 0
                evidence_rows = connection.execute(
                    "SELECT evidence_id, record_json, integrity "
                    "FROM sh3_evidence_records ORDER BY rowid"
                )
                for row in evidence_rows:
                    try:
                        raw = json.loads(str(row["record_json"]))
                        if not isinstance(raw, Mapping):
                            raise TypeError("stored evidence must be a JSON object")
                        row_integrity = row["integrity"]
                        if raw.get("integrity") != row_integrity:
                            raise ValueError(
                                "row and document integrity metadata differ"
                            )
                        payload = raw.get("payload")
                        if not isinstance(payload, Mapping):
                            raise TypeError(
                                "stored evidence payload must be a JSON object"
                            )
                        record = EvidenceRecord.create(
                            evidence_id=_required_text(
                                "evidence_id", raw.get("evidence_id")
                            ),
                            kind=_required_text("kind", raw.get("kind")),
                            source=_required_text("source", raw.get("source")),
                            subject_id=_required_text(
                                "subject_id", raw.get("subject_id")
                            ),
                            version=_required_text("version", raw.get("version")),
                            trace_id=raw.get("trace_id"),
                            collected_at=_required_text(
                                "collected_at", raw.get("collected_at")
                            ),
                            payload=payload,
                        )
                        if record.integrity != row_integrity or not record.verify():
                            raise ValueError(
                                "stored evidence integrity digest is invalid"
                            )
                    except (KeyError, TypeError, ValueError) as exc:
                        raise PersistentReplayReadinessError(
                            "evidence row "
                            f"{evidence_count + 1} failed application "
                            "integrity verification"
                        ) from exc
                    if record.evidence_id != row["evidence_id"]:
                        raise PersistentReplayReadinessError(
                            f"evidence row {evidence_count + 1} key does not "
                            "match its record"
                        )
                    evidence_count += 1

                now = time.time()
                replay_claim_count = 0
                expired_claim_count = 0
                claim_rows = connection.execute(
                    "SELECT cycle_id, fingerprint, state, generation, attempts, "
                    "owner_token, lease_expires_at, evidence_id "
                    "FROM sh3_replay_claims ORDER BY cycle_id"
                )
                for row in claim_rows:
                    if _validate_claim(row, now):
                        expired_claim_count += 1
                    replay_claim_count += 1

                journal_row = connection.execute("PRAGMA journal_mode").fetchone()
                journal_mode = str(journal_row[0]).lower() if journal_row else "unknown"
            finally:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
    except PersistentReplayReadinessError:
        raise
    except sqlite3.Error as exc:
        raise PersistentReplayReadinessError(
            f"SQLite inspection failed for {path.name}: {exc}"
        ) from exc

    return DatabaseReadinessReport(
        database_path=path,
        sqlite_version=sqlite3.sqlite_version,
        journal_mode=journal_mode,
        evidence_count=evidence_count,
        replay_claim_count=replay_claim_count,
        expired_claim_count=expired_claim_count,
    )


def _prepare_destination(
    destination_value: str | os.PathLike[str],
    source: Path,
) -> Path:
    requested = Path(destination_value).expanduser()
    if requested.is_symlink():
        raise PersistentReplayReadinessError(
            "backup/restore destination must not be a symbolic link"
        )
    destination = requested.parent.resolve() / requested.name
    if destination == source:
        raise PersistentReplayReadinessError(
            "source and destination database paths must be different"
        )
    if destination.exists():
        raise FileExistsError(
            f"refusing to overwrite existing destination: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(
            f"refusing to overwrite existing destination: {destination}"
        )
    return destination


def _backup_to_temporary(
    source: Path,
    destination: Path,
    *,
    timeout_seconds: float,
) -> None:
    source_connection: sqlite3.Connection | None = None
    destination_connection: sqlite3.Connection | None = None
    try:
        source_connection = sqlite3.connect(
            f"{source.as_uri()}?mode=ro",
            uri=True,
            timeout=timeout_seconds,
            isolation_level=None,
        )
        source_connection.execute(
            f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}"
        )
        destination_connection = sqlite3.connect(
            destination,
            timeout=timeout_seconds,
            isolation_level=None,
        )
        destination_connection.execute(
            f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}"
        )
        source_connection.backup(destination_connection, pages=256, sleep=0.05)
    except sqlite3.Error as exc:
        raise PersistentReplayReadinessError(
            f"SQLite online backup failed from {source.name}: {exc}"
        ) from exc
    finally:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()


def _create_verified_snapshot(
    source_path: str | os.PathLike[str],
    destination_path: str | os.PathLike[str],
    *,
    timeout_seconds: float,
) -> DatabaseReadinessReport:
    timeout = _timeout(timeout_seconds)
    source = _existing_database(source_path)
    check_database(source, timeout_seconds=timeout)
    destination = _prepare_destination(destination_path, source)

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".partial",
        dir=destination.parent,
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        _backup_to_temporary(source, temporary, timeout_seconds=timeout)
        check_database(temporary, timeout_seconds=timeout)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            raise FileExistsError(
                f"refusing to overwrite existing destination: {destination}"
            ) from None
        except OSError as exc:
            raise PersistentReplayReadinessError(
                "could not publish the verified snapshot without overwriting; "
                "check destination permissions and same-filesystem hard-link support"
            ) from exc
        return check_database(destination, timeout_seconds=timeout)
    finally:
        temporary.unlink(missing_ok=True)


def backup_database(
    database_path: str | os.PathLike[str],
    destination_path: str | os.PathLike[str],
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> DatabaseReadinessReport:
    """Create and verify an online SQLite backup without overwriting a file."""
    return _create_verified_snapshot(
        database_path,
        destination_path,
        timeout_seconds=timeout_seconds,
    )


def restore_database(
    backup_path: str | os.PathLike[str],
    destination_path: str | os.PathLike[str],
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> DatabaseReadinessReport:
    """Restore a verified backup to a new database path without replacing data."""
    return _create_verified_snapshot(
        backup_path,
        destination_path,
        timeout_seconds=timeout_seconds,
    )


def _print_report(report: DatabaseReadinessReport, *, action: str) -> None:
    print(f"{action}: PASS")
    print(f"database={report.database_path}")
    print(f"sqlite_version={report.sqlite_version}")
    print(f"journal_mode={report.journal_mode}")
    print(f"evidence_records={report.evidence_count}")
    print(f"replay_claims={report.replay_claim_count}")
    print(f"expired_claims={report.expired_claim_count}")
    if report.expired_claim_count:
        print(
            "warning=expired claims are present; verify that no stale worker can "
            "still cause external effects before recovery/replay"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check, back up, and restore SH-3 persistent replay SQLite storage."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check", help="run read-only SQLite and SH-3 integrity checks"
    )
    check_parser.add_argument("--database", type=Path, required=True)
    check_parser.add_argument(
        "--timeout-seconds", type=float, default=_DEFAULT_TIMEOUT_SECONDS
    )

    backup_parser = subparsers.add_parser(
        "backup", help="create and verify a consistent online backup"
    )
    backup_parser.add_argument("--database", type=Path, required=True)
    backup_parser.add_argument("--destination", type=Path, required=True)
    backup_parser.add_argument(
        "--timeout-seconds", type=float, default=_DEFAULT_TIMEOUT_SECONDS
    )

    restore_parser = subparsers.add_parser(
        "restore", help="restore to a new destination without overwriting"
    )
    restore_parser.add_argument("--backup", type=Path, required=True)
    restore_parser.add_argument("--destination", type=Path, required=True)
    restore_parser.add_argument(
        "--timeout-seconds", type=float, default=_DEFAULT_TIMEOUT_SECONDS
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "check":
            report = check_database(
                args.database,
                timeout_seconds=args.timeout_seconds,
            )
            _print_report(report, action="CHECK")
        elif args.command == "backup":
            report = backup_database(
                args.database,
                args.destination,
                timeout_seconds=args.timeout_seconds,
            )
            _print_report(report, action="BACKUP")
        else:
            report = restore_database(
                args.backup,
                args.destination,
                timeout_seconds=args.timeout_seconds,
            )
            _print_report(report, action="RESTORE")
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except PersistentReplayReadinessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
