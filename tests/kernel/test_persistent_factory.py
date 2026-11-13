from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.security.persistent_replay_runtime import (
    PERSISTENT_REPLAY_DATABASE_ENV,
)
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)
from kernel import SH3Kernel, create_persistent_sh3_kernel
from kernel.persistent_factory import PersistentKernelRuntime


def test_factory_creates_kernel_with_paired_persistent_stores(tmp_path: Path) -> None:
    database = tmp_path / "runtime.sqlite3"

    runtime = create_persistent_sh3_kernel(
        database,
        create_if_missing=True,
    )

    assert isinstance(runtime, PersistentKernelRuntime)
    assert isinstance(runtime.kernel, SH3Kernel)
    assert isinstance(runtime.stores.evidence_store, SQLiteEvidenceStore)
    assert isinstance(runtime.stores.replay_claim_store, SQLiteReplayClaimStore)
    assert isinstance(runtime.stores.replay_stage_store, SQLiteReplayStageStore)
    assert runtime.database_path == database.resolve()
    assert runtime.stores.evidence_store.database_path == runtime.database_path
    assert runtime.stores.replay_claim_store.database_path == runtime.database_path
    assert runtime.stores.replay_stage_store.database_path == runtime.database_path
    assert (
        runtime.kernel.cognitive_learning_boundary.replay_stage_store
        is runtime.stores.replay_stage_store
    )
    assert database.is_file()


def test_factory_uses_environment_path_when_explicit_path_is_omitted(
    tmp_path: Path,
) -> None:
    database = tmp_path / "environment.sqlite3"

    runtime = create_persistent_sh3_kernel(
        create_if_missing=True,
        environ={PERSISTENT_REPLAY_DATABASE_ENV: str(database)},
    )

    assert runtime.database_path == database.resolve()
    assert database.is_file()


def test_factory_fails_closed_when_database_is_missing(tmp_path: Path) -> None:
    database = tmp_path / "missing.sqlite3"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        create_persistent_sh3_kernel(database)

    assert not database.exists()


def test_explicit_path_takes_precedence_over_environment_path(tmp_path: Path) -> None:
    explicit_database = tmp_path / "explicit.sqlite3"
    environment_database = tmp_path / "environment.sqlite3"

    runtime = create_persistent_sh3_kernel(
        explicit_database,
        create_if_missing=True,
        environ={PERSISTENT_REPLAY_DATABASE_ENV: str(environment_database)},
    )

    assert runtime.database_path == explicit_database.resolve()
    assert explicit_database.is_file()
    assert not environment_database.exists()
