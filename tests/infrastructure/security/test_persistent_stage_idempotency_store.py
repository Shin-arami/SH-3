from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from infrastructure.security.persistent_replay_ops import (
    PersistentReplayReadinessError,
    check_database,
)
from infrastructure.security.persistent_store import (
    PersistentEvidenceIntegrityError,
    ReplayClaimOwnershipError,
    ReplayClaimStatus,
    ReplayStageBusyError,
    ReplayStageConflictError,
    ReplayStageKey,
    ReplayStageStatus,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def _stores(
    database: Path,
) -> tuple[SQLiteReplayClaimStore, SQLiteReplayStageStore]:
    SQLiteEvidenceStore(database)
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    return claims, stages


def _key() -> ReplayStageKey:
    return ReplayStageKey.create(
        "learning-cycle:stage-idempotency",
        "sha256:cycle-input",
        "learning.record",
        {
            "result_id": "result:stage-idempotency",
            "goal_id": "goal:stage-idempotency",
            "success": True,
            "score": 0.8,
        },
    )


def test_stage_key_is_stable_and_scoped_to_logical_stage_input() -> None:
    first = _key()
    replay = _key()
    different_input = ReplayStageKey.create(
        first.cycle_id,
        first.cycle_fingerprint,
        first.stage_name,
        {"result_id": "different", "success": True, "score": 0.8},
    )
    different_stage = ReplayStageKey.create(
        first.cycle_id,
        first.cycle_fingerprint,
        "learning.optimize",
        {
            "result_id": "result:stage-idempotency",
            "goal_id": "goal:stage-idempotency",
            "success": True,
            "score": 0.8,
        },
    )

    assert first == replay
    assert first.idempotency_key == replay.idempotency_key
    assert first.idempotency_key != different_input.idempotency_key
    assert first.idempotency_key != different_stage.idempotency_key


def test_completed_stage_result_survives_store_reopen_and_is_reused(
    tmp_path: Path,
) -> None:
    database = tmp_path / "stage-result.sqlite3"
    claims, stages = _stores(database)
    owner = claims.claim(
        "learning-cycle:stage-idempotency",
        "sha256:cycle-input",
        lease_seconds=60.0,
        now=NOW,
    )
    assert owner.status is ReplayClaimStatus.CLAIMED
    assert owner.owner_token is not None

    key = _key()
    started = stages.begin(
        key,
        owner.owner_token,
        owner.generation,
        now=NOW,
    )
    assert started.status is ReplayStageStatus.CLAIMED
    assert started.attempts == 1

    result = {
        "loop_id": "learning-loop:stage-idempotency",
        "score": 0.8,
        "memory_key": "memory:stage-idempotency",
    }
    completed = stages.complete(
        key,
        owner.owner_token,
        owner.generation,
        result,
        now=NOW + timedelta(seconds=1),
    )
    assert completed.status is ReplayStageStatus.COMPLETED
    assert completed.result == result

    reopened = SQLiteReplayStageStore(database)
    replay = reopened.begin(
        key,
        owner.owner_token,
        owner.generation,
        now=NOW + timedelta(seconds=2),
    )

    assert replay.status is ReplayStageStatus.COMPLETED
    assert replay.result == result
    assert replay.attempts == 1

    readiness = check_database(database)
    assert readiness.replay_stage_execution_count == 1


def test_incomplete_stage_is_taken_over_by_new_generation_and_stale_owner_is_fenced(
    tmp_path: Path,
) -> None:
    database = tmp_path / "stage-takeover.sqlite3"
    claims, stages = _stores(database)
    key = _key()

    first_owner = claims.claim(
        key.cycle_id,
        key.cycle_fingerprint,
        lease_seconds=5.0,
        now=NOW,
    )
    assert first_owner.owner_token is not None

    first_stage = stages.begin(
        key,
        first_owner.owner_token,
        first_owner.generation,
        now=NOW,
    )
    assert first_stage.status is ReplayStageStatus.CLAIMED

    takeover_time = NOW + timedelta(seconds=6)
    second_owner = claims.claim(
        key.cycle_id,
        key.cycle_fingerprint,
        lease_seconds=30.0,
        now=takeover_time,
    )
    assert second_owner.status is ReplayClaimStatus.CLAIMED
    assert second_owner.owner_token is not None
    assert second_owner.generation == first_owner.generation + 1

    second_stage = stages.begin(
        key,
        second_owner.owner_token,
        second_owner.generation,
        now=takeover_time,
    )
    assert second_stage.status is ReplayStageStatus.CLAIMED
    assert second_stage.generation == second_owner.generation
    assert second_stage.attempts == 2
    assert second_stage.key.idempotency_key == first_stage.key.idempotency_key

    with pytest.raises(ReplayClaimOwnershipError):
        stages.complete(
            key,
            first_owner.owner_token,
            first_owner.generation,
            {"score": 0.1},
            now=takeover_time + timedelta(seconds=1),
        )

    completed = stages.complete(
        key,
        second_owner.owner_token,
        second_owner.generation,
        {"score": 0.9},
        now=takeover_time + timedelta(seconds=1),
    )
    assert completed.status is ReplayStageStatus.COMPLETED
    assert completed.result == {"score": 0.9}

    replay = stages.begin(
        key,
        second_owner.owner_token,
        second_owner.generation,
        now=takeover_time + timedelta(seconds=2),
    )
    assert replay.status is ReplayStageStatus.COMPLETED
    assert replay.result == {"score": 0.9}


def test_same_generation_concurrent_stage_begin_is_atomic(
    tmp_path: Path,
) -> None:
    database = tmp_path / "stage-concurrent.sqlite3"
    claims, _ = _stores(database)
    owner = claims.claim(
        "learning-cycle:stage-concurrent",
        "sha256:stage-concurrent",
        lease_seconds=60.0,
        now=NOW,
    )
    assert owner.owner_token is not None

    key = ReplayStageKey.create(
        owner.cycle_id,
        owner.fingerprint,
        "learning.record",
        {"result_id": "result:stage-concurrent"},
    )
    stores = tuple(SQLiteReplayStageStore(database) for _ in range(8))

    def attempt(store: SQLiteReplayStageStore) -> ReplayStageStatus | None:
        try:
            result = store.begin(
                key,
                owner.owner_token or "",
                owner.generation,
                now=NOW,
            )
        except ReplayStageBusyError:
            return None
        return result.status

    with ThreadPoolExecutor(max_workers=len(stores)) as executor:
        outcomes = tuple(executor.map(attempt, stores))

    assert outcomes.count(ReplayStageStatus.CLAIMED) == 1
    assert outcomes.count(None) == len(stores) - 1


def test_stage_result_integrity_tampering_fails_closed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "stage-tamper.sqlite3"
    claims, stages = _stores(database)
    owner = claims.claim(
        "learning-cycle:stage-tamper",
        "sha256:stage-tamper",
        lease_seconds=60.0,
        now=NOW,
    )
    assert owner.owner_token is not None

    key = ReplayStageKey.create(
        owner.cycle_id,
        owner.fingerprint,
        "learning.record",
        {"result_id": "result:stage-tamper"},
    )
    stages.begin(
        key,
        owner.owner_token,
        owner.generation,
        now=NOW,
    )
    stages.complete(
        key,
        owner.owner_token,
        owner.generation,
        {"score": 0.8},
        now=NOW + timedelta(seconds=1),
    )

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sh3_replay_stage_executions "
            "SET result_json = ? WHERE idempotency_key = ?",
            ('{"score":0.1}', key.idempotency_key),
        )

    with pytest.raises(PersistentEvidenceIntegrityError):
        stages.get(key)

    with pytest.raises(
        PersistentReplayReadinessError,
        match="replay stage execution failed application integrity",
    ):
        check_database(database)

def test_stage_row_cycle_id_mismatch_is_rejected_by_all_store_reads(
    tmp_path: Path,
) -> None:
    database = tmp_path / "stage-cycle-id-tamper.sqlite3"
    claims, stages = _stores(database)
    key = _key()
    owner = claims.claim(
        key.cycle_id,
        key.cycle_fingerprint,
        lease_seconds=60.0,
        now=NOW,
    )
    assert owner.owner_token is not None

    stages.begin(key, owner.owner_token, owner.generation, now=NOW)
    alternate_cycle_id = "learning-cycle:alternate-parent"
    alternate_claim = claims.claim(
        alternate_cycle_id,
        key.cycle_fingerprint,
        lease_seconds=60.0,
        now=NOW,
    )
    assert alternate_claim.status is ReplayClaimStatus.CLAIMED

    # Keep the database FK valid while corrupting the logical Stage identity.
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sh3_replay_stage_executions SET cycle_id = ? "
            "WHERE idempotency_key = ?",
            (alternate_cycle_id, key.idempotency_key),
        )

    with pytest.raises(ReplayStageConflictError, match="identity conflicts"):
        stages.get(key)
    with pytest.raises(ReplayStageConflictError, match="identity conflicts"):
        stages.begin(
            key, owner.owner_token, owner.generation,
            now=NOW + timedelta(seconds=1),
        )
    with pytest.raises(ReplayStageConflictError, match="identity conflicts"):
        stages.complete(
            key, owner.owner_token, owner.generation, {"score": 0.9},
            now=NOW + timedelta(seconds=1),
        )


def test_readiness_rejects_stage_table_without_parent_claim_foreign_key(
    tmp_path: Path,
) -> None:
    database = tmp_path / "stage-missing-parent-fk.sqlite3"
    _stores(database)

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE sh3_replay_stage_executions")
        connection.execute(
            """
            CREATE TABLE sh3_replay_stage_executions (
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
                CHECK (
                    (state = 'claimed' AND owner_token IS NOT NULL
                        AND result_json IS NULL AND result_integrity IS NULL)
                    OR
                    (state = 'completed' AND owner_token IS NULL
                        AND result_json IS NOT NULL AND result_integrity IS NOT NULL)
                )
            )
            """
        )
        connection.execute(
            "CREATE INDEX sh3_replay_stage_cycle_state_idx "
            "ON sh3_replay_stage_executions(cycle_id, state)"
        )

    with pytest.raises(
        PersistentReplayReadinessError,
        match=r"exactly one.*foreign key",
    ):
        check_database(database)
