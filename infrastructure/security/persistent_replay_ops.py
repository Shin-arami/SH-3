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
from dataclasses import dataclass, field
from pathlib import Path

from foundation.utils.hash import short_id
from infrastructure.security import EvidenceRecord

__all__ = [
    "DatabaseReadinessReport",
    "PendingEvidenceReconciliation",
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
_EXIT_PENDING_RECONCILIATION_POLICY_GATE = 2
_EXIT_EXPIRED_CLAIM_POLICY_GATE = 3


class PersistentReplayReadinessError(RuntimeError):
    """Raised when a persistent replay database fails an operational check."""


@dataclass(frozen=True, slots=True)
class PendingEvidenceReconciliation:
    """Minimal read-only details for a terminal-evidence/claim finalize gap."""

    cycle_id: str = field(repr=False)
    claim_state: str
    generation: int
    attempts: int
    evidence_id: str
    lease_expires_at: float | None
    lease_expired: bool | None

    def __post_init__(self) -> None:
        if not isinstance(self.cycle_id, str) or not self.cycle_id.strip():
            raise ValueError("cycle_id must not be empty")
        if not isinstance(self.claim_state, str) or self.claim_state not in {
            "claimed",
            "released",
        }:
            raise ValueError("claim_state must be claimed or released")
        if (
            isinstance(self.generation, bool)
            or not isinstance(self.generation, int)
            or self.generation < 1
        ):
            raise ValueError("generation must be a positive integer")
        if (
            isinstance(self.attempts, bool)
            or not isinstance(self.attempts, int)
            or self.attempts < 0
        ):
            raise ValueError("attempts must be a non-negative integer")
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError("evidence_id must not be empty")
        if self.claim_state == "claimed":
            lease_expiry = self.lease_expires_at
            if (
                isinstance(lease_expiry, bool)
                or not isinstance(lease_expiry, (int, float))
                or not math.isfinite(float(lease_expiry))
                or not isinstance(self.lease_expired, bool)
            ):
                raise ValueError("claimed detail requires lease information")
            object.__setattr__(self, "lease_expires_at", float(lease_expiry))
        elif self.lease_expires_at is not None or self.lease_expired is not None:
            raise ValueError("released detail cannot contain lease information")


@dataclass(frozen=True, slots=True)
class DatabaseReadinessReport:
    database_path: Path
    sqlite_version: str
    journal_mode: str
    evidence_count: int
    replay_claim_count: int
    expired_claim_count: int
    pending_evidence_reconciliation_count: int = 0
    pending_evidence_reconciliations: tuple[PendingEvidenceReconciliation, ...] = field(default=(), repr=False)


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
    *,
    primary_key: str,
    not_null: set[str],
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    actual = {str(row["name"]): row for row in rows}
    if not required.issubset(actual):
        missing = ", ".join(sorted(required - set(actual)))
        raise PersistentReplayReadinessError(
            f"database schema is missing required columns in {table}: {missing}"
        )

    primary_keys = tuple(
        str(row["name"])
        for row in sorted(rows, key=lambda item: int(item["pk"]))
        if int(row["pk"]) > 0
    )
    if primary_keys != (primary_key,):
        raise PersistentReplayReadinessError(
            f"database table {table} must use {primary_key} as its sole primary key"
        )

    nullable = sorted(
        column
        for column in not_null
        if not bool(actual[column]["notnull"])
    )
    if nullable:
        raise PersistentReplayReadinessError(
            f"database schema requires NOT NULL columns in {table}: "
            + ", ".join(nullable)
        )



def _require_replay_claim_state_schema(connection: sqlite3.Connection) -> None:
    table_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (_CLAIM_TABLE,),
    ).fetchone()
    table_sql = "" if table_row is None or table_row[0] is None else str(table_row[0])
    normalized_sql = "".join(table_sql.lower().split())
    required_check = "statetextnotnullcheck(statein('claimed','completed','released'))"
    if required_check not in normalized_sql:
        raise PersistentReplayReadinessError(
            "database table sh3_replay_claims does not enforce the required replay claim states"
        )

    index_rows = connection.execute(
        "PRAGMA index_list(sh3_replay_claims)"
    ).fetchall()
    index_row = next(
        (
            row
            for row in index_rows
            if str(row["name"]) == "sh3_replay_claims_state_idx"
        ),
        None,
    )
    if index_row is None:
        raise PersistentReplayReadinessError(
            "database is missing required index sh3_replay_claims_state_idx"
        )
    if bool(index_row["unique"]) or bool(index_row["partial"]):
        raise PersistentReplayReadinessError(
            "index sh3_replay_claims_state_idx must be non-unique and non-partial"
        )

    index_columns = tuple(
        str(row["name"])
        for row in connection.execute(
            "PRAGMA index_info(sh3_replay_claims_state_idx)"
        ).fetchall()
    )
    if index_columns != ("state", "lease_expires_at"):
        raise PersistentReplayReadinessError(
            "index sh3_replay_claims_state_idx must use ordered columns "
            "(state, lease_expires_at)"
        )


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value

def _validate_terminal_evidence_link(
    cycle_id: str,
    evidence_id: str,
    evidence_links: Mapping[str, tuple[str, str, object, str, object]],
    *,
    claim_state: str,
) -> None:
    evidence_link = evidence_links.get(evidence_id)
    if evidence_link is None:
        raise PersistentReplayReadinessError(
            f"{claim_state} replay claim references missing evidence: {cycle_id}"
        )
    (
        evidence_kind,
        evidence_source,
        evidence_cycle_id,
        evidence_subject_id,
        evidence_result_id,
    ) = evidence_link
    if (
        evidence_kind != "learning.closed_loop"
        or evidence_source != "kernel.learning_feedback_loop"
    ):
        raise PersistentReplayReadinessError(
            f"{claim_state} replay claim does not reference terminal "
            f"closed-loop evidence: {cycle_id}"
        )
    if evidence_cycle_id != cycle_id:
        raise PersistentReplayReadinessError(
            f"{claim_state} replay claim evidence cycle identity "
            f"mismatch: {cycle_id}"
        )
    if evidence_id != short_id(cycle_id, prefix="learning-closed-loop:"):
        raise PersistentReplayReadinessError(
            f"{claim_state} replay claim evidence identifier is not "
            f"canonical for cycle: {cycle_id}"
        )
    if (
        not isinstance(evidence_result_id, str)
        or not evidence_result_id.strip()
        or evidence_subject_id != evidence_result_id
    ):
        raise PersistentReplayReadinessError(
            f"{claim_state} replay claim evidence result identity "
            f"mismatch: {cycle_id}"
        )


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
                _require_columns(
                    connection,
                    _EVIDENCE_TABLE,
                    _EVIDENCE_COLUMNS,
                    primary_key="evidence_id",
                    not_null=_EVIDENCE_COLUMNS,
                )
                _require_columns(
                    connection,
                    _CLAIM_TABLE,
                    _CLAIM_COLUMNS,
                    primary_key="cycle_id",
                    not_null={
                        "cycle_id",
                        "fingerprint",
                        "state",
                        "generation",
                        "attempts",
                        "updated_at",
                    },
                )
                _require_replay_claim_state_schema(connection)

                evidence_links: dict[str, tuple[str, str, object, str, object]] = {}
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
                    evidence_links[record.evidence_id] = (
                        record.kind,
                        record.source,
                        record.payload.get("cycle_id"),
                        record.subject_id,
                        record.payload.get("result_id"),
                    )
                    evidence_count += 1

                now = time.time()
                replay_claim_count = 0
                expired_claim_count = 0
                pending_evidence_reconciliation_count = 0
                pending_evidence_reconciliations: list[PendingEvidenceReconciliation] = []
                claim_rows = connection.execute(
                    "SELECT cycle_id, fingerprint, state, generation, attempts, "
                    "owner_token, lease_expires_at, evidence_id "
                    "FROM sh3_replay_claims ORDER BY cycle_id"
                )
                for row in claim_rows:
                    claim_is_expired = _validate_claim(row, now)
                    if claim_is_expired:
                        expired_claim_count += 1
                    cycle_id = str(row["cycle_id"])
                    state = str(row["state"])
                    if state == "completed":
                        _validate_terminal_evidence_link(
                            cycle_id,
                            str(row["evidence_id"]),
                            evidence_links,
                            claim_state="completed",
                        )
                    else:
                        # Evidence and claim completion use separate transactions.
                        # A canonical record here may be a live finalize window or
                        # a crash that the next run can reconcile safely.
                        candidate_evidence_id = short_id(
                            cycle_id, prefix="learning-closed-loop:"
                        )
                        if candidate_evidence_id in evidence_links:
                            _validate_terminal_evidence_link(
                                cycle_id,
                                candidate_evidence_id,
                                evidence_links,
                                claim_state="pending",
                            )
                            raw_lease = row["lease_expires_at"]
                            if state == "claimed":
                                lease_expires_at = float(raw_lease)
                                lease_expired: bool | None = lease_expires_at <= now
                            else:
                                lease_expires_at = None
                                lease_expired = None
                            pending_evidence_reconciliations.append(
                                PendingEvidenceReconciliation(
                                    cycle_id=cycle_id,
                                    claim_state=state,
                                    generation=int(row["generation"]),
                                    attempts=int(row["attempts"]),
                                    evidence_id=candidate_evidence_id,
                                    lease_expires_at=lease_expires_at,
                                    lease_expired=lease_expired,
                                )
                            )
                            pending_evidence_reconciliation_count += 1
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
        pending_evidence_reconciliation_count=pending_evidence_reconciliation_count,
        pending_evidence_reconciliations=tuple(pending_evidence_reconciliations),
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


def _print_report(
    report: DatabaseReadinessReport,
    *,
    action: str,
    include_pending_details: bool = False,
    json_output: bool = False,
    policy_gates: Mapping[str, str] | None = None,
    exit_code: int = 0,
) -> None:
    if json_output:
        payload: dict[str, object] = {
            "schema_version": 1,
            "action": action.lower(),
            "database": str(report.database_path),
            "sqlite_version": report.sqlite_version,
            "journal_mode": report.journal_mode,
            "integrity_status": "pass",
            "evidence_records": report.evidence_count,
            "replay_claims": report.replay_claim_count,
            "expired_claims": report.expired_claim_count,
            "pending_evidence_reconciliation": report.pending_evidence_reconciliation_count,
            "policy_gates": dict(policy_gates or {}),
            "exit_code": exit_code,
        }
        if include_pending_details:
            payload["pending_reconciliations"] = [
                {
                    "cycle_id": pending.cycle_id,
                    "claim_state": pending.claim_state,
                    "generation": pending.generation,
                    "attempts": pending.attempts,
                    "lease_expired": pending.lease_expired,
                    "lease_expires_at": pending.lease_expires_at,
                    "evidence_id": pending.evidence_id,
                }
                for pending in report.pending_evidence_reconciliations
            ]
        print(json.dumps(payload, sort_keys=True))
        return
    print(f"{action}: PASS")
    print(f"database={report.database_path}")
    print(f"sqlite_version={report.sqlite_version}")
    print(f"journal_mode={report.journal_mode}")
    print(f"evidence_records={report.evidence_count}")
    print(f"replay_claims={report.replay_claim_count}")
    print(f"expired_claims={report.expired_claim_count}")
    print(
        "pending_evidence_reconciliation="
        f"{report.pending_evidence_reconciliation_count}"
    )
    if report.pending_evidence_reconciliation_count:
        print(
            "warning=canonical terminal evidence exists for a claim not yet "
            "marked completed; it may be an active finalize window or require "
            "reconciliation after interruption"
        )
    if include_pending_details:
        for index, pending in enumerate(
            report.pending_evidence_reconciliations, start=1
        ):
            lease_expired = (
                "unknown"
                if pending.lease_expired is None
                else str(pending.lease_expired).lower()
            )
            lease_expires_at = (
                "none"
                if pending.lease_expires_at is None
                else f"{pending.lease_expires_at:.6f}"
            )
            print(f"pending[{index}].cycle_id={pending.cycle_id}")
            print(f"pending[{index}].claim_state={pending.claim_state}")
            print(f"pending[{index}].generation={pending.generation}")
            print(f"pending[{index}].attempts={pending.attempts}")
            print(f"pending[{index}].lease_expired={lease_expired}")
            print(f"pending[{index}].lease_expires_at={lease_expires_at}")
            print(f"pending[{index}].evidence_id={pending.evidence_id}")
    if report.expired_claim_count:
        print(
            "warning=expired claims are present; verify that no stale worker can "
            "still cause external effects before recovery/replay"
        )


def _json_error_code(error: Exception) -> str:
    if isinstance(error, PersistentReplayReadinessError):
        return "readiness_check_failed"
    if isinstance(error, FileNotFoundError):
        return "database_not_found"
    if isinstance(error, PermissionError):
        return "permission_denied"
    if isinstance(error, sqlite3.Error):
        return "sqlite_error"
    if isinstance(error, ValueError):
        return "invalid_argument"
    return "operating_system_error"


def _print_json_error(
    *,
    action: str,
    error_code: str,
    error_type: str,
    exit_code: int = 1,
) -> None:
    payload: dict[str, object] = {
        "schema_version": 1,
        "action": action,
        "integrity_status": "error",
        "policy_gates": {},
        "error": {"code": error_code, "type": error_type},
        "exit_code": exit_code,
    }
    print(json.dumps(payload, sort_keys=True))


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
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="write a machine-readable JSON readiness report to stdout",
    )
    check_parser.add_argument(
        "--include-pending-cycle-ids",
        action="store_true",
        help="print pending cycle identifiers; they may reveal application identifiers",
    )
    check_parser.add_argument(
        "--fail-on-pending-reconciliation",
        action="store_true",
        help=(
            "exit with code 2 when terminal evidence exists beside a "
            "non-completed claim"
        ),
    )
    check_parser.add_argument(
        "--fail-on-expired-claims",
        action="store_true",
        help=(
            "exit with code 3 when one or more replay claim leases have expired"
        ),
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
            policy_gate_exit_code = 0
            policy_gate_results: dict[str, str] = {}
            if args.fail_on_pending_reconciliation:
                pending_count = report.pending_evidence_reconciliation_count
                if pending_count:
                    policy_gate_results["pending_reconciliation"] = "fail"
                    policy_gate_exit_code = _EXIT_PENDING_RECONCILIATION_POLICY_GATE
                else:
                    policy_gate_results["pending_reconciliation"] = "pass"
            if args.fail_on_expired_claims:
                expired_count = report.expired_claim_count
                if expired_count:
                    policy_gate_results["expired_claims"] = "fail"
                    if policy_gate_exit_code == 0:
                        policy_gate_exit_code = _EXIT_EXPIRED_CLAIM_POLICY_GATE
                else:
                    policy_gate_results["expired_claims"] = "pass"

            _print_report(
                report,
                action="CHECK",
                include_pending_details=args.include_pending_cycle_ids,
                json_output=args.json,
                policy_gates=policy_gate_results,
                exit_code=policy_gate_exit_code,
            )
            if args.fail_on_pending_reconciliation:
                if policy_gate_results["pending_reconciliation"] == "fail":
                    print("PENDING_RECONCILIATION_GATE: FAIL", file=sys.stderr)
                    print(
                        "ERROR: --fail-on-pending-reconciliation requires zero "
                        "pending evidence reconciliations; "
                        f"found {report.pending_evidence_reconciliation_count}",
                        file=sys.stderr,
                    )
                elif not args.json:
                    print("PENDING_RECONCILIATION_GATE: PASS")
            if args.fail_on_expired_claims:
                if policy_gate_results["expired_claims"] == "fail":
                    print("EXPIRED_CLAIM_GATE: FAIL", file=sys.stderr)
                    print(
                        "ERROR: --fail-on-expired-claims requires zero expired "
                        f"replay claim leases; found {report.expired_claim_count}",
                        file=sys.stderr,
                    )
                elif not args.json:
                    print("EXPIRED_CLAIM_GATE: PASS")
            if policy_gate_exit_code:
                return policy_gate_exit_code
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
        if args.command == "check" and args.json:
            _print_json_error(
                action="check",
                error_code=_json_error_code(exc),
                error_type=type(exc).__name__,
            )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except PersistentReplayReadinessError as exc:
        if args.command == "check" and args.json:
            _print_json_error(
                action="check",
                error_code=_json_error_code(exc),
                error_type=type(exc).__name__,
            )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
