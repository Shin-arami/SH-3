from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import (
    PersistentReplayReadinessError,
    check_database,
)
from infrastructure.security.persistent_replay_runtime import (
    PERSISTENT_REPLAY_DATABASE_ENV,
    PersistentReplayConfigurationError,
    PersistentReplayStores,
    create_persistent_replay_stores,
    resolve_persistent_replay_database_path,
)
from infrastructure.security.persistent_store import (
    ReplayClaimStatus,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)
from kernel.core import SH3Kernel


def _evidence(evidence_id: str = "learning.closed_loop:runtime-wiring") -> EvidenceRecord:
    return EvidenceRecord.create(
        evidence_id=evidence_id,
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id="result:runtime-wiring",
        version="1.1.0",
        trace_id="trace:runtime-wiring",
        collected_at="2026-10-16T00:00:00+00:00",
        payload={"cycle_id": "learning-cycle:runtime-wiring", "status": "completed"},
    )


def test_runtime_configuration_fails_closed_when_path_is_not_configured() -> None:
    with pytest.raises(
        PersistentReplayConfigurationError,
        match=PERSISTENT_REPLAY_DATABASE_ENV,
    ):
        resolve_persistent_replay_database_path(environ={})


def test_explicit_path_overrides_environment_and_resolution_is_side_effect_free(
    tmp_path: Path,
) -> None:
    environment_path = tmp_path / "environment" / "evidence.sqlite3"
    explicit_path = tmp_path / "explicit" / "evidence.sqlite3"
    environment = {PERSISTENT_REPLAY_DATABASE_ENV: str(environment_path)}

    resolved_environment = resolve_persistent_replay_database_path(environ=environment)
    resolved_explicit = resolve_persistent_replay_database_path(
        explicit_path,
        environ=environment,
    )

    assert resolved_environment == environment_path.resolve()
    assert resolved_explicit == explicit_path.resolve()
    assert not environment_path.parent.exists()
    assert not explicit_path.parent.exists()


def test_missing_database_does_not_silently_create_an_empty_store(tmp_path: Path) -> None:
    database = tmp_path / "misspelled" / "evidence.sqlite3"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        create_persistent_replay_stores(database)

    assert not database.exists()
    assert not database.parent.exists()


def test_explicit_provisioning_creates_one_valid_database_and_wires_kernel(
    tmp_path: Path,
) -> None:
    database = tmp_path / "data" / "evidence.sqlite3"
    stores = create_persistent_replay_stores(
        create_if_missing=True,
        environ={PERSISTENT_REPLAY_DATABASE_ENV: str(database)},
    )

    assert database.is_file()
    assert stores.database_path == database.resolve()
    assert stores.evidence_store.database_path == stores.database_path
    assert stores.replay_claim_store.database_path == stores.database_path
    report = check_database(database)
    assert report.evidence_count == 0
    assert report.replay_claim_count == 0
    assert report.journal_mode == "wal"

    kernel = SH3Kernel(
        evidence_store=stores.evidence_store,
        replay_claim_store=stores.replay_claim_store,
    )
    assert kernel.optimizer_evidence_boundary.evidence_store is stores.evidence_store
    assert (
        kernel.learning_closed_loop_evidence_boundary.evidence_store
        is stores.evidence_store
    )


def test_runtime_store_bundle_reopens_persisted_state_across_instances(
    tmp_path: Path,
) -> None:
    database = tmp_path / "persistent" / "evidence.sqlite3"
    first = create_persistent_replay_stores(database, create_if_missing=True)
    evidence = _evidence()
    first.evidence_store.register(evidence)
    claim = first.replay_claim_store.claim(
        "learning-cycle:runtime-wiring",
        "sha256:runtime-wiring",
        lease_seconds=300.0,
    )

    second = create_persistent_replay_stores(database)
    loaded_evidence = second.evidence_store.get(evidence.evidence_id)
    loaded_claim = second.replay_claim_store.get("learning-cycle:runtime-wiring")

    assert loaded_evidence is not None and loaded_evidence.verify()
    assert loaded_evidence.evidence_id == evidence.evidence_id
    assert loaded_claim is not None
    assert loaded_claim.status is ReplayClaimStatus.CLAIMED
    assert loaded_claim.owner_token == claim.owner_token
    assert loaded_claim.generation == claim.generation
    assert check_database(database).evidence_count == 1
    assert check_database(database).replay_claim_count == 1


def test_bundle_rejects_stores_that_point_to_different_database_files(
    tmp_path: Path,
) -> None:
    evidence_database = tmp_path / "evidence.sqlite3"
    claim_database = tmp_path / "claims.sqlite3"
    evidence_store = SQLiteEvidenceStore(evidence_database)
    claim_store = SQLiteReplayClaimStore(claim_database)

    with pytest.raises(ValueError, match="database path does not match"):
        PersistentReplayStores(
            database_path=evidence_database.resolve(),
            evidence_store=evidence_store,
            replay_claim_store=claim_store,
        )


def test_memory_database_and_invalid_timeouts_are_rejected_without_side_effects(
    tmp_path: Path,
) -> None:
    with pytest.raises(PersistentReplayConfigurationError, match="file-backed"):
        resolve_persistent_replay_database_path(":memory:")

    database = tmp_path / "invalid-timeout" / "evidence.sqlite3"
    with pytest.raises(ValueError, match="greater than zero"):
        create_persistent_replay_stores(database, timeout_seconds=0.0)

    assert not database.exists()
    assert not database.parent.exists()

def test_existing_unrecognized_database_is_not_silently_initialized(
    tmp_path: Path,
) -> None:
    database = tmp_path / "unrecognized.sqlite3"
    original = b"not a SQLite database"
    database.write_bytes(original)

    with pytest.raises(PersistentReplayReadinessError):
        create_persistent_replay_stores(database, create_if_missing=True)

    assert database.read_bytes() == original
