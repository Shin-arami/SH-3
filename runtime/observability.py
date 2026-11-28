from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC
from typing import Any

from foundation.utils.logging import event as log_event
from infrastructure.security.evidence import EvidenceRecord, EvidenceStore

from .execution import ExecutionSnapshot
from .execution_cleanup import CleanupResult

__all__ = ["RuntimeExecutionObservability"]


class RuntimeExecutionObservability:
    __slots__ = ("_evidence_store", "_logger_name")

    def __init__(
        self,
        evidence_store: EvidenceStore | None = None,
        *,
        logger_name: str = "sh3.runtime",
    ) -> None:
        if evidence_store is not None and not isinstance(evidence_store, EvidenceStore):
            raise TypeError("evidence_store must be EvidenceStore")
        if not isinstance(logger_name, str) or not logger_name:
            raise ValueError("logger_name must not be empty")
        self._evidence_store = evidence_store or EvidenceStore()
        self._logger_name = logger_name

    @property
    def evidence_store(self) -> EvidenceStore:
        return self._evidence_store

    @property
    def logger_name(self) -> str:
        return self._logger_name

    def record(
        self,
        snapshot: ExecutionSnapshot,
        *,
        result: Any = None,
        error: BaseException | None = None,
        cleanup: CleanupResult | None = None,
    ) -> EvidenceRecord:
        if not isinstance(snapshot, ExecutionSnapshot):
            raise TypeError("snapshot must be ExecutionSnapshot")
        if cleanup is not None and not isinstance(cleanup, CleanupResult):
            raise TypeError("cleanup must be CleanupResult")

        evidence_id = f"runtime.execution:{snapshot.execution_id}"
        existing = self._evidence_store.get(evidence_id)
        if existing is not None:
            if not existing.verify():
                raise ValueError(f"runtime evidence integrity verification failed: {evidence_id}")
            return existing

        payload = self._build_payload(
            snapshot,
            result=result,
            error=error,
            cleanup=cleanup,
        )
        record = EvidenceRecord.create(
            evidence_id=evidence_id,
            kind="runtime.execution",
            source="runtime",
            subject_id=snapshot.execution_id,
            version=snapshot.event_schema_version,
            payload=payload,
            trace_id=snapshot.trace_id,
        )
        registered = self._evidence_store.register(record)
        self._log_recorded(registered, payload)
        return registered

    def get(self, execution_id: str) -> EvidenceRecord | None:
        if not isinstance(execution_id, str) or not execution_id:
            raise ValueError("execution_id must not be empty")
        return self._evidence_store.get(f"runtime.execution:{execution_id}")

    def verify(self, execution_id: str) -> bool:
        if not isinstance(execution_id, str) or not execution_id:
            raise ValueError("execution_id must not be empty")
        return self._evidence_store.verify(f"runtime.execution:{execution_id}")

    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(
            record
            for record in self._evidence_store.records()
            if record.kind == "runtime.execution"
        )

    def _build_payload(
        self,
        snapshot: ExecutionSnapshot,
        *,
        result: Any,
        error: BaseException | None,
        cleanup: CleanupResult | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "execution_id": snapshot.execution_id,
            "operation": snapshot.operation,
            "state": snapshot.state.value,
            "priority": snapshot.priority.value,
            "created_at": snapshot.created_at,
            "queued_at": snapshot.queued_at,
            "started_at": snapshot.started_at,
            "completed_at": snapshot.completed_at,
            "timeout": snapshot.timeout,
            "attempt": snapshot.attempt,
            "result": result if snapshot.state.value == "completed" else None,
            "error_type": snapshot.error_type,
            "error_message": snapshot.error_message,
            "duration_seconds": self._duration(snapshot),
            "correlation_id": snapshot.correlation_id,
            "causation_id": snapshot.causation_id,
            "trace_id": snapshot.trace_id,
            "tenant_id": snapshot.tenant_id,
            "metadata": dict(snapshot.metadata),
            "event_schema_version": snapshot.event_schema_version,
            "cleanup": self._cleanup_payload(cleanup),
        }
        if error is not None:
            payload["error_type"] = type(error).__name__
            payload["error_message"] = str(error)
        return payload

    @staticmethod
    def _duration(snapshot: ExecutionSnapshot) -> float | None:
        if snapshot.started_at is None or snapshot.completed_at is None:
            return None
        started = snapshot.started_at
        completed = snapshot.completed_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=UTC)
        return max(0.0, (completed - started).total_seconds())

    @staticmethod
    def _cleanup_payload(cleanup: CleanupResult | None) -> dict[str, Any]:
        if cleanup is None:
            return {
                "attempted": False,
                "completed": False,
                "failed": False,
                "failures": (),
            }
        failures = tuple(
            {
                "name": failure.name,
                "error_type": failure.error_type,
                "error_message": failure.error_message,
            }
            for failure in cleanup.failures
        )
        return {
            "attempted": cleanup.attempted,
            "completed": cleanup.completed,
            "failed": cleanup.failed,
            "failures": failures,
        }

    def _log_recorded(
        self,
        record: EvidenceRecord,
        payload: Mapping[str, Any],
    ) -> None:
        data = {
            "evidence_id": record.evidence_id,
            "execution_id": record.subject_id,
            "state": payload["state"],
            "operation": payload["operation"],
            "duration_seconds": payload["duration_seconds"],
            "attempt": payload["attempt"],
            "correlation_id": payload["correlation_id"],
            "trace_id": payload["trace_id"],
            "tenant_id": payload["tenant_id"],
        }
        try:
            log_event(
                "RuntimeExecutionEvidenceRecorded",
                payload=data,
                logger=self._logger_name,
            )
        except Exception:
            return
