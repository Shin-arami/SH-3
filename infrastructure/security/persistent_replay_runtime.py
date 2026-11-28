from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from infrastructure.security.persistent_operation_store import (
    SQLiteReplayOperationStore,
)
from infrastructure.security.persistent_replay_ops import check_database
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)

__all__ = [
    "PERSISTENT_REPLAY_DATABASE_ENV",
    "PersistentReplayConfigurationError",
    "PersistentReplayStores",
    "create_persistent_replay_stores",
    "resolve_persistent_replay_database_path",
]

PERSISTENT_REPLAY_DATABASE_ENV = "SH3_PERSISTENT_REPLAY_DATABASE"
_DEFAULT_TIMEOUT_SECONDS = 5.0


class PersistentReplayConfigurationError(ValueError):
    """Raised when persistent replay runtime configuration is incomplete or unsafe."""


def _validate_timeout(timeout_seconds: float) -> float:
    if isinstance(timeout_seconds, bool) or not isinstance(
        timeout_seconds, (int, float)
    ):
        raise TypeError("timeout_seconds must be a real number")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and greater than zero")
    return float(timeout_seconds)


def resolve_persistent_replay_database_path(
    database_path: str | PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve an explicit path or ``SH3_PERSISTENT_REPLAY_DATABASE``.

    This function is side-effect free: it does not create the directory or file.
    An explicit path takes precedence over the environment variable.
    """
    configured_environment = os.environ if environ is None else environ
    raw_path: str | PathLike[str] | None = database_path
    if raw_path is None:
        raw_path = configured_environment.get(PERSISTENT_REPLAY_DATABASE_ENV)
    if raw_path is None:
        raise PersistentReplayConfigurationError(
            f"set {PERSISTENT_REPLAY_DATABASE_ENV} or pass database_path explicitly"
        )
    if isinstance(raw_path, bool):
        raise TypeError("database_path must be a path string or PathLike object")

    rendered_path = str(raw_path).strip()
    if not rendered_path:
        raise PersistentReplayConfigurationError("database_path must not be empty")
    if rendered_path == ":memory:":
        raise PersistentReplayConfigurationError(
            "persistent replay requires a file-backed SQLite database, not :memory:"
        )

    resolved_path = Path(rendered_path).expanduser().resolve()
    if resolved_path.exists() and not resolved_path.is_file():
        raise PersistentReplayConfigurationError(
            f"database_path must identify a file, not a directory: {resolved_path}"
        )
    return resolved_path


@dataclass(frozen=True, slots=True)
class PersistentReplayStores:
    """One validated database path and its persistent replay stores."""

    database_path: Path
    evidence_store: SQLiteEvidenceStore
    replay_claim_store: SQLiteReplayClaimStore
    replay_stage_store: SQLiteReplayStageStore | None = None
    replay_operation_store: SQLiteReplayOperationStore | None = None

    def __post_init__(self) -> None:
        path = Path(self.database_path).expanduser().resolve()
        if not isinstance(self.evidence_store, SQLiteEvidenceStore):
            raise TypeError("evidence_store must be SQLiteEvidenceStore")
        if not isinstance(self.replay_claim_store, SQLiteReplayClaimStore):
            raise TypeError("replay_claim_store must be SQLiteReplayClaimStore")
        if self.evidence_store.database_path != path:
            raise ValueError("evidence_store database path does not match database_path")
        if self.replay_claim_store.database_path != path:
            raise ValueError("replay_claim_store database path does not match database_path")
        if self.replay_stage_store is not None:
            if not isinstance(self.replay_stage_store, SQLiteReplayStageStore):
                raise TypeError(
                    "replay_stage_store must be SQLiteReplayStageStore or None"
                )
            if self.replay_stage_store.database_path != path:
                raise ValueError(
                    "replay_stage_store database path does not match database_path"
                )
        if self.replay_operation_store is not None:
            if self.replay_stage_store is None:
                raise ValueError(
                    "replay_operation_store requires replay_stage_store"
                )
            if not isinstance(
                self.replay_operation_store, SQLiteReplayOperationStore
            ):
                raise TypeError(
                    "replay_operation_store must be SQLiteReplayOperationStore or None"
                )
            if self.replay_operation_store.database_path != path:
                raise ValueError(
                    "replay_operation_store database path does not match database_path"
                )
        object.__setattr__(self, "database_path", path)


def create_persistent_replay_stores(
    database_path: str | PathLike[str] | None = None,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    create_if_missing: bool = False,
    environ: Mapping[str, str] | None = None,
) -> PersistentReplayStores:
    """Create runtime stores after checking database lifecycle state.

    Existing databases are validated before either store is opened. Missing
    databases fail closed by default so a misspelled path cannot silently start
    an empty history. Set ``create_if_missing=True`` only for deliberate first-
    time provisioning. This factory holds no long-lived SQLite connections.
    """
    timeout = _validate_timeout(timeout_seconds)
    if not isinstance(create_if_missing, bool):
        raise TypeError("create_if_missing must be bool")

    path = resolve_persistent_replay_database_path(
        database_path,
        environ=environ,
    )
    existed_before = path.exists()
    if existed_before:
        if not path.is_file():
            raise PersistentReplayConfigurationError(
                f"database_path must identify a regular file: {path}"
            )
        # Check before the adapters' CREATE TABLE IF NOT EXISTS statements, so
        # a damaged or unrelated file is never silently repaired on startup.
        check_database(path, timeout_seconds=timeout)
    elif not create_if_missing:
        raise FileNotFoundError(
            f"persistent replay database does not exist: {path}; "
            "provision it explicitly with create_if_missing=True only for first use"
        )

    evidence_store = SQLiteEvidenceStore(path, timeout_seconds=timeout)
    replay_claim_store = SQLiteReplayClaimStore(path, timeout_seconds=timeout)
    replay_stage_store = SQLiteReplayStageStore(path, timeout_seconds=timeout)
    replay_operation_store = SQLiteReplayOperationStore(
        path, timeout_seconds=timeout
    )
    check_database(path, timeout_seconds=timeout)
    return PersistentReplayStores(
        database_path=path,
        evidence_store=evidence_store,
        replay_claim_store=replay_claim_store,
        replay_stage_store=replay_stage_store,
        replay_operation_store=replay_operation_store,
    )
