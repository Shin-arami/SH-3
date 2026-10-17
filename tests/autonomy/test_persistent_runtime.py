from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from autonomy.persistent_runtime import (
    PersistentApplicationRuntime,
    create_persistent_application_runtime,
)
from cognition.contracts import CognitiveResultStatus
from infrastructure.security.persistent_replay_ops import (
    backup_database,
    check_database,
    restore_database,
)
from kernel.learning_feedback_loop import ClosedLoopStatus
from runtime.execution_engine import RuntimeExecutionEngine


def _successful_operation(payload: Mapping[str, Any]) -> dict[str, bool]:
    return {"accepted": True, "payload_received": bool(payload)}


def _register_test_operation(runtime: PersistentApplicationRuntime) -> None:
    backend = runtime.kernel.cognition.execution_boundary.backend
    assert isinstance(backend, RuntimeExecutionEngine)
    backend.register_operation("test.accept", _successful_operation)


def test_application_runtime_fails_closed_without_creating_missing_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing.sqlite3"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        create_persistent_application_runtime(database)

    assert not database.exists()


def test_application_runtime_wires_both_persistent_stores_to_the_kernel(
    tmp_path: Path,
) -> None:
    database = tmp_path / "runtime.sqlite3"
    runtime = create_persistent_application_runtime(
        database,
        create_if_missing=True,
    )

    assert runtime.database_path == database.resolve()
    assert runtime.stores.evidence_store.database_path == runtime.database_path
    assert runtime.stores.replay_claim_store.database_path == runtime.database_path
    assert runtime.kernel.optimizer_evidence_boundary.evidence_store is (
        runtime.stores.evidence_store
    )
    assert runtime.kernel.learning_feedback_loop._replay_claim_store is (
        runtime.stores.replay_claim_store
    )


def test_execute_contract_records_a_durable_terminal_result(tmp_path: Path) -> None:
    database = tmp_path / "runtime.sqlite3"
    runtime = create_persistent_application_runtime(
        database,
        create_if_missing=True,
    )
    _register_test_operation(runtime)

    application_run = runtime.execute_contract(
        "prepare release",
        operation="test.accept",
        payload={"release": "2.2"},
    )
    readiness = check_database(database)

    assert application_run.cognitive_result.status is CognitiveResultStatus.SUCCESS
    assert application_run.closed_loop_report.status is ClosedLoopStatus.COMPLETED
    assert application_run.closed_loop_report.cycle_id == (
        f"learning-cycle:{application_run.cognitive_result.result_id}"
    )
    assert readiness.evidence_count >= 1
    assert readiness.replay_claim_count == 1
    assert readiness.expired_claim_count == 0
    assert all(record.verify() for record in runtime.stores.evidence_store.records())


def test_backup_restore_and_replay_recover_the_same_terminal_report(
    tmp_path: Path,
) -> None:
    database = tmp_path / "runtime.sqlite3"
    backup = tmp_path / "runtime-backup.sqlite3"
    restored_database = tmp_path / "runtime-restored.sqlite3"

    original_runtime = create_persistent_application_runtime(
        database,
        create_if_missing=True,
    )
    _register_test_operation(original_runtime)
    original_run = original_runtime.execute_contract(
        "verify closed-loop recovery",
        operation="test.accept",
        payload={"check": "restore"},
    )
    source_report = check_database(database)

    backup_report = backup_database(database, backup)
    restore_report = restore_database(backup, restored_database)
    recovered_runtime = create_persistent_application_runtime(restored_database)
    replayed_run = recovered_runtime.process_result(original_run.cognitive_result)
    recovered_report = check_database(restored_database)

    assert backup_report.evidence_count == source_report.evidence_count
    assert backup_report.replay_claim_count == source_report.replay_claim_count
    assert restore_report.evidence_count == source_report.evidence_count
    assert restore_report.replay_claim_count == source_report.replay_claim_count
    assert replayed_run.closed_loop_report.cycle_id == original_run.closed_loop_report.cycle_id
    assert replayed_run.closed_loop_report.result_id == original_run.closed_loop_report.result_id
    assert replayed_run.closed_loop_report.status is original_run.closed_loop_report.status
    assert recovered_report.evidence_count == source_report.evidence_count
    assert recovered_report.replay_claim_count == source_report.replay_claim_count
    assert recovered_report.expired_claim_count == 0


def test_process_result_rejects_non_cognitive_result(tmp_path: Path) -> None:
    runtime = create_persistent_application_runtime(
        tmp_path / "runtime.sqlite3",
        create_if_missing=True,
    )

    with pytest.raises(TypeError, match="CognitiveResult"):
        runtime.process_result({"status": "completed"})  # type: ignore[arg-type]
