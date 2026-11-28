from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from autonomy.persistent_runtime import create_persistent_application_runtime
from cognition.contracts import CognitiveResultStatus
from infrastructure.event_bus import EventBus, EventBusPublisher
from infrastructure.security.persistent_replay_ops import check_database
from kernel import create_persistent_sh3_kernel
from runtime.execution_engine import RuntimeExecutionEngine


def _accept_operation(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"accepted": True, "marker": payload.get("marker")}


def test_persistent_application_shares_store_with_cognition_and_runtime(
    tmp_path: Path,
) -> None:
    database = tmp_path / "persistent-evidence.sqlite3"
    runtime = create_persistent_application_runtime(database, create_if_missing=True)
    backend = runtime.kernel.cognition.execution_boundary.backend

    assert isinstance(backend, RuntimeExecutionEngine)
    assert runtime.kernel.cognition.observability.evidence_store is (
        runtime.stores.evidence_store
    )
    assert backend.evidence_store is runtime.stores.evidence_store

    backend.register_operation("test.accept", _accept_operation)
    application_run = runtime.execute_contract(
        "audit persistent evidence propagation",
        operation="test.accept",
        payload={"marker": "part11-27"},
        optimize=False,
        recover=False,
    )
    cognitive_result = application_run.cognitive_result
    assert cognitive_result.status is CognitiveResultStatus.SUCCESS

    execution = cognitive_result.output.get("execution")
    assert isinstance(execution, Mapping)
    execution_id = execution.get("execution_id")
    assert isinstance(execution_id, str)

    expected_evidence_ids = (
        f"cognition.result:{cognitive_result.result_id}",
        f"cognition.execution:{execution_id}",
        f"runtime.execution:{execution_id}",
    )
    for evidence_id in expected_evidence_ids:
        record = runtime.stores.evidence_store.get(evidence_id)
        assert record is not None, evidence_id
        assert record.verify(), evidence_id

    readiness = check_database(database)
    assert readiness.evidence_count >= len(expected_evidence_ids)
    assert readiness.replay_claim_count == 1
    assert readiness.expired_claim_count == 0


def test_persistent_kernel_publisher_update_reaches_execution_engine(
    tmp_path: Path,
) -> None:
    runtime = create_persistent_sh3_kernel(
        tmp_path / "publisher.sqlite3",
        create_if_missing=True,
    )
    backend = runtime.kernel.cognition.execution_boundary.backend
    assert isinstance(backend, RuntimeExecutionEngine)

    publisher = EventBusPublisher(EventBus())
    runtime.kernel.set_event_publisher(publisher)

    assert runtime.kernel.event_publisher is publisher
    assert runtime.kernel.cognition.observability.event_publisher is publisher
    assert backend.event_publisher is publisher
