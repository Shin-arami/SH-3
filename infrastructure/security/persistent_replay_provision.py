from __future__ import annotations

import argparse
import math
import os
import sqlite3
import sys
from collections.abc import Mapping, Sequence
from os import PathLike
from pathlib import Path

from infrastructure.security.persistent_operation_store import (
    SQLiteReplayOperationStore,
)
from infrastructure.security.persistent_replay_ops import (
    DatabaseReadinessReport,
    PersistentReplayReadinessError,
    check_database,
)
from infrastructure.security.persistent_replay_runtime import (
    PERSISTENT_REPLAY_DATABASE_ENV,
    resolve_persistent_replay_database_path,
)
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)

__all__ = ["main", "provision_persistent_replay_database"]

_DEFAULT_TIMEOUT_SECONDS = 5.0


def _validate_timeout(timeout_seconds: float) -> float:
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise TypeError("timeout_seconds must be a real number")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and greater than zero")
    return float(timeout_seconds)


def provision_persistent_replay_database(
    database_path: str | PathLike[str] | None = None,
    *,
    confirm_first_use: bool = False,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    environ: Mapping[str, str] | None = None,
) -> DatabaseReadinessReport:
    """Provision a new SH-3 SQLite database without opening an existing path.

    The target's parent directory must already exist. Exclusive file creation
    prevents this command from opening or replacing an existing file. On an
    initialization failure, the newly reserved file is preserved for operator
    inspection rather than being deleted automatically.
    """
    if not isinstance(confirm_first_use, bool):
        raise TypeError("confirm_first_use must be bool")
    if not confirm_first_use:
        raise ValueError("first-use provisioning requires confirm_first_use=True")

    timeout = _validate_timeout(timeout_seconds)
    configured_environment = os.environ if environ is None else environ
    raw_path: str | PathLike[str] | None = database_path
    if raw_path is None:
        raw_path = configured_environment.get(PERSISTENT_REPLAY_DATABASE_ENV)

    # Refuse to follow a caller-supplied symlink during destructive lifecycle setup.
    if raw_path is not None:
        if isinstance(raw_path, bool):
            raise TypeError("database_path must be a path string or PathLike object")
        requested_path = Path(raw_path).expanduser()
        if requested_path.is_symlink():
            raise ValueError("database_path must not be a symbolic link")

    path = resolve_persistent_replay_database_path(
        database_path,
        environ=configured_environment,
    )
    if not path.parent.is_dir():
        raise FileNotFoundError(
            f"database parent directory must already exist: {path.parent}"
        )

    try:
        # 'xb' is atomic with respect to path creation and never truncates an
        # existing target. The empty reservation becomes the SQLite database.
        with path.open("xb") as reservation:
            reservation.flush()
            os.fsync(reservation.fileno())
    except FileExistsError as exc:
        raise FileExistsError(
            f"refusing to provision an existing database path: {path}"
        ) from exc

    # These constructors initialize all persistent replay schemas in the
    # reserved file. Keep it on error for operator inspection.
    SQLiteEvidenceStore(path, timeout_seconds=timeout)
    SQLiteReplayClaimStore(path, timeout_seconds=timeout)
    SQLiteReplayStageStore(path, timeout_seconds=timeout)
    SQLiteReplayOperationStore(path, timeout_seconds=timeout)
    return check_database(path, timeout_seconds=timeout)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly provision a new SH-3 persistent replay SQLite database. "
            "Existing paths are never overwritten."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help=f"new database path (defaults to {PERSISTENT_REPLAY_DATABASE_ENV})",
    )
    parser.add_argument(
        "--confirm-first-use",
        action="store_true",
        required=True,
        help="confirm that this is a deliberate first-time database creation",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=_DEFAULT_TIMEOUT_SECONDS,
    )
    return parser


def _print_report(report: DatabaseReadinessReport) -> None:
    print("PROVISION: PASS")
    print(f"database={report.database_path}")
    print(f"sqlite_version={report.sqlite_version}")
    print(f"journal_mode={report.journal_mode}")
    print(f"evidence_records={report.evidence_count}")
    print(f"replay_claims={report.replay_claim_count}")
    print(f"expired_claims={report.expired_claim_count}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = provision_persistent_replay_database(
            args.database,
            confirm_first_use=args.confirm_first_use,
            timeout_seconds=args.timeout_seconds,
        )
        _print_report(report)
    except (OSError, TypeError, ValueError, sqlite3.Error, PersistentReplayReadinessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
