from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Any

from cognition.contracts import CognitiveContext, CognitiveGoal, CognitiveResult
from infrastructure.event_bus import EventPublisher
from infrastructure.events import EventPropagationContext
from infrastructure.security.persistent_replay_runtime import PersistentReplayStores
from kernel.core import SH3Kernel
from kernel.learning_feedback_loop import LearningClosedLoopReport
from kernel.persistent_factory import (
    PersistentKernelRuntime,
    create_persistent_sh3_kernel,
)

__all__ = [
    "PersistentApplicationRun",
    "PersistentApplicationRuntime",
    "create_persistent_application_runtime",
]

_DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class PersistentApplicationRun:
    """The typed cognition result and its durable closed-loop report."""

    cognitive_result: CognitiveResult
    closed_loop_report: LearningClosedLoopReport

    def __post_init__(self) -> None:
        if not isinstance(self.cognitive_result, CognitiveResult):
            raise TypeError("cognitive_result must be CognitiveResult")
        if not isinstance(self.closed_loop_report, LearningClosedLoopReport):
            raise TypeError("closed_loop_report must be LearningClosedLoopReport")
        if self.closed_loop_report.result_id != self.cognitive_result.result_id:
            raise ValueError("closed-loop report result_id does not match cognitive result")
        if self.closed_loop_report.goal_id != self.cognitive_result.goal_id:
            raise ValueError("closed-loop report goal_id does not match cognitive result")


@dataclass(frozen=True, slots=True)
class PersistentApplicationRuntime:
    """Application-layer composition root for the persistent closed loop."""

    kernel_runtime: PersistentKernelRuntime

    def __post_init__(self) -> None:
        if not isinstance(self.kernel_runtime, PersistentKernelRuntime):
            raise TypeError("kernel_runtime must be PersistentKernelRuntime")

    @property
    def kernel(self) -> SH3Kernel:
        """Return the kernel wired to persistent evidence and replay claims."""
        return self.kernel_runtime.kernel

    @property
    def stores(self) -> PersistentReplayStores:
        """Return the evidence and replay-claim stores used by the kernel."""
        return self.kernel_runtime.stores

    @property
    def database_path(self) -> Path:
        """Return the resolved SQLite path for the application runtime."""
        return self.kernel_runtime.database_path

    def process_result(
        self,
        cognitive_result: CognitiveResult,
        *,
        context: EventPropagationContext | None = None,
        optimize: bool = True,
        recover: bool = True,
    ) -> PersistentApplicationRun:
        """Send a typed cognition result through the durable closed-loop coordinator."""
        if not isinstance(cognitive_result, CognitiveResult):
            raise TypeError("cognitive_result must be CognitiveResult")
        if not isinstance(optimize, bool):
            raise TypeError("optimize must be bool")
        if not isinstance(recover, bool):
            raise TypeError("recover must be bool")

        report = self.kernel.learning_feedback_loop.run(
            cognitive_result,
            context=context,
            optimize=optimize,
            recover=recover,
        )
        return PersistentApplicationRun(
            cognitive_result=cognitive_result,
            closed_loop_report=report,
        )

    def execute_contract(
        self,
        goal: CognitiveGoal | str,
        *,
        context: CognitiveContext | None = None,
        policy: Callable[[list[str]], str | None] | None = None,
        operation: str | None = None,
        payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
        optimize: bool = True,
        recover: bool = True,
    ) -> PersistentApplicationRun:
        """Execute a typed cognition contract and persist its closed-loop result.

        The application must register any domain execution operations required by
        its goals on the configured runtime execution backend before calling this
        method. An unregistered operation is returned as a typed failure result
        and is still passed to the closed-loop coordinator for recovery/evidence.
        """
        if not isinstance(optimize, bool):
            raise TypeError("optimize must be bool")
        if not isinstance(recover, bool):
            raise TypeError("recover must be bool")

        result = self.kernel.cognition.execute_contract(
            goal,
            context=context,
            policy=policy,
            operation=operation,
            payload=payload,
            created_at=created_at,
        )
        return self.process_result(
            result,
            context=(
                EventPropagationContext.create(
                    correlation_id=result.correlation_id,
                    causation_id=result.causation_id,
                    trace_id=result.trace_id,
                    tenant_id=result.tenant_id,
                )
            ),
            optimize=optimize,
            recover=recover,
        )


def create_persistent_application_runtime(
    database_path: str | PathLike[str] | None = None,
    *,
    event_publisher: EventPublisher | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    create_if_missing: bool = False,
    environ: Mapping[str, str] | None = None,
) -> PersistentApplicationRuntime:
    """Create the application runtime without silently provisioning a database.

    The evidence store and replay-claim store are created and validated by the
    Kernel factory. A missing database fails by default. Set
    ``create_if_missing=True`` only during an explicitly controlled first-use
    provisioning step; normal application startup should leave it false.
    """
    kernel_runtime = create_persistent_sh3_kernel(
        database_path,
        event_publisher=event_publisher,
        timeout_seconds=timeout_seconds,
        create_if_missing=create_if_missing,
        environ=environ,
    )
    return PersistentApplicationRuntime(kernel_runtime=kernel_runtime)
