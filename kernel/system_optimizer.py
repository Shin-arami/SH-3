from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum, unique
from inspect import Parameter, signature
from threading import RLock, local
from typing import Any

from cognition.memory import MemoryCore
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error, info
from infrastructure.event_bus import EventPublisher
from infrastructure.events import EventPropagationContext
from infrastructure.events.model import Event
from infrastructure.security.persistent_operation_store import (
    ReplayOperationKey,
    ReplayOperationKind,
    ReplayOperationStatus,
    SQLiteReplayOperationStore,
)
from kernel.core import SH3Kernel
from kernel.replay_execution_context import (
    DurableOperationPersistenceError,
    ReplayExecutionContext,
)

__all__ = [
    "OptimizationAction",
    "OptimizationActionReplayPolicy",
    "OptimizationActionResult",
    "SystemOptimizer",
]


def _operation_json_value(value: Any) -> Any:
    """Normalize callback values to canonical-JSON-compatible data."""
    if isinstance(value, Enum):
        return _operation_json_value(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("optimizer Action datetimes must be timezone-aware")
        return value.astimezone(UTC).isoformat()
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("optimizer Action result mapping keys must be strings")
        return {key: _operation_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_operation_json_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _operation_json_value(getattr(value, item.name))
            for item in fields(value)
        }
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        rendered = to_dict()
        if isinstance(rendered, Mapping):
            return _operation_json_value(rendered)
    raise TypeError(
        "optimizer Action result contains a non-JSON value: "
        f"{type(value).__name__}"
    )


@unique
class OptimizationActionReplayPolicy(StrEnum):
    """Controls whether a completed Action result can cross Runtime restarts."""

    REUSE_RESULT = "reuse_result"
    REQUIRE_LOCAL_STATE = "require_local_state"


@dataclass(frozen=True, slots=True)
class OptimizationAction:
    name: str
    apply: Callable[[Mapping[str, Any]], Any]
    rollback: Callable[..., Any]
    description: str = ""
    replay_policy: OptimizationActionReplayPolicy = (
        OptimizationActionReplayPolicy.REQUIRE_LOCAL_STATE
    )
    contract_id: str | None = None
    implementation_version: str | None = None
    rollback_version: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not callable(self.apply):
            raise TypeError("apply must be callable")
        if not callable(self.rollback):
            raise TypeError("rollback must be callable")
        if not isinstance(self.replay_policy, OptimizationActionReplayPolicy):
            raise TypeError("replay_policy must be OptimizationActionReplayPolicy")
        compatibility_values = (
            ("contract_id", self.contract_id),
            ("implementation_version", self.implementation_version),
            ("rollback_version", self.rollback_version),
        )
        supplied = tuple(value is not None for _, value in compatibility_values)
        if any(supplied) and not all(supplied):
            raise ValueError(
                "contract_id, implementation_version, and rollback_version "
                "must be supplied together"
            )
        for field_name, value in compatibility_values:
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field_name} must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name, "description": self.description}
        if self.contract_id is not None:
            data.update(
                {
                    "contract_id": self.contract_id,
                    "implementation_version": self.implementation_version,
                    "rollback_version": self.rollback_version,
                }
            )
        return data


def _durable_action_contract(action: OptimizationAction) -> dict[str, str]:
    """Return explicit compatibility metadata required for durable replay."""
    if (
        action.contract_id is None
        or action.implementation_version is None
        or action.rollback_version is None
    ):
        raise DurableOperationPersistenceError(
            f"persistent optimizer Action {action.name!r} must declare contract_id, "
            "implementation_version, and rollback_version"
        )
    return {
        "name": action.name,
        "contract_id": action.contract_id,
        "implementation_version": action.implementation_version,
        "rollback_version": action.rollback_version,
        "replay_policy": action.replay_policy.value,
    }


@dataclass(frozen=True, slots=True)
class OptimizationActionResult:
    action: str
    success: bool
    result: Any = None
    rolled_back: bool = False
    error: str | None = None
    idempotency_key: str | None = None
    parent_idempotency_key: str | None = None
    rollback_idempotency_key: str | None = None
    state_uncertain: bool = False
    ordinal: int = field(default=0, compare=False, repr=False)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "action": self.action,
            "success": self.success,
            "result": self.result,
            "rolled_back": self.rolled_back,
            "error": self.error,
        }
        for name, value in (
            ("idempotency_key", self.idempotency_key),
            ("parent_idempotency_key", self.parent_idempotency_key),
            ("rollback_idempotency_key", self.rollback_idempotency_key),
        ):
            if value is not None:
                data[name] = value
        if self.state_uncertain:
            data["state_uncertain"] = True
        return data


def _action_idempotency_key(
    parent_idempotency_key: str,
    action: str,
    ordinal: int,
) -> str:
    if not isinstance(parent_idempotency_key, str) or not parent_idempotency_key.strip():
        raise ValueError("idempotency_key must not be empty")
    if not isinstance(ordinal, int) or ordinal < 0:
        raise ValueError("action ordinal must be a non-negative integer")
    return short_id(
        {
            "parent_idempotency_key": parent_idempotency_key,
            "action": action,
            "ordinal": ordinal,
        },
        length=24,
        prefix="optimizer-action:",
    )


def _rollback_idempotency_key(action_idempotency_key: str, action: str) -> str:
    return short_id(
        {
            "action_idempotency_key": action_idempotency_key,
            "action": action,
            "operation": "rollback",
        },
        length=24,
        prefix="optimizer-action-rollback:",
    )


def _accepts_keyword_argument(callback: Callable[..., Any], name: str) -> bool:
    try:
        parameters = signature(callback).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.kind is Parameter.VAR_KEYWORD
        or (
            parameter.name == name
            and parameter.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
        )
        for parameter in parameters
    )


class SystemOptimizer:
    __slots__ = (
        "_actions",
        "_event_publisher",
        "_history",
        "_last_event_id",
        "_last_propagation_context",
        "_local_operation_results",
        "_lock",
        "_propagation_context_local",
        "_replay_execution_context_local",
        "_replay_operation_store",
        "kernel",
        "memory",
        "optimizer_id",
    )

    def __init__(
        self,
        kernel: SH3Kernel,
        *,
        event_publisher: EventPublisher | None = None,
        replay_operation_store: SQLiteReplayOperationStore | None = None,
    ) -> None:
        if replay_operation_store is not None and not isinstance(
            replay_operation_store, SQLiteReplayOperationStore
        ):
            raise TypeError("replay_operation_store must be SQLiteReplayOperationStore or None")
        if replay_operation_store is not None:
            stage_store = getattr(kernel, "replay_stage_store", None)
            if stage_store is None or stage_store.database_path != replay_operation_store.database_path:
                raise ValueError(
                    "replay operation store requires a parent stage store on the same database"
                )
        self.kernel = kernel
        self.memory: MemoryCore = kernel.memory
        self.optimizer_id = short_id("system-optimizer")
        self._event_publisher = event_publisher
        self._last_event_id: str | None = None
        self._propagation_context_local = local()
        self._replay_execution_context_local = local()
        self._replay_operation_store = replay_operation_store
        self._local_operation_results: dict[tuple[str, str], OptimizationActionResult] = {}
        self._last_propagation_context: EventPropagationContext | None = None
        self._actions: dict[str, OptimizationAction] = {}
        self._history: list[OptimizationActionResult] = []
        self._lock = RLock()
        self._register_default_actions()

    @property
    def _propagation_context(self) -> EventPropagationContext | None:
        if hasattr(self._propagation_context_local, "value"):
            value = self._propagation_context_local.value
            return value if isinstance(value, EventPropagationContext) else None
        with self._lock:
            return self._last_propagation_context

    @_propagation_context.setter
    def _propagation_context(
        self,
        context: EventPropagationContext | None,
    ) -> None:
        self._propagation_context_local.value = context
        with self._lock:
            self._last_propagation_context = context

    @property
    def propagation_context(self) -> EventPropagationContext | None:
        return self._propagation_context

    def set_propagation_context(
        self,
        context: EventPropagationContext | None,
    ) -> None:
        if context is not None and not isinstance(context, EventPropagationContext):
            raise TypeError("context must be EventPropagationContext or None")
        self._propagation_context = context

    @property
    def replay_operation_store(self) -> SQLiteReplayOperationStore | None:
        return self._replay_operation_store

    @property
    def replay_execution_context(self) -> ReplayExecutionContext | None:
        value = getattr(self._replay_execution_context_local, "value", None)
        return value if isinstance(value, ReplayExecutionContext) else None

    @property
    def has_replay_execution_context(self) -> bool:
        return self.replay_execution_context is not None

    @contextmanager
    def replay_execution_scope(
        self,
        context: ReplayExecutionContext,
    ) -> Iterator[None]:
        if not isinstance(context, ReplayExecutionContext):
            raise TypeError("context must be ReplayExecutionContext")
        previous = getattr(self._replay_execution_context_local, "value", None)
        self._replay_execution_context_local.value = context
        try:
            yield
        finally:
            if previous is None:
                with suppress(AttributeError):
                    del self._replay_execution_context_local.value
            else:
                self._replay_execution_context_local.value = previous

    def _persisted_action_plan(self, actions: tuple[str, ...]) -> tuple[str, ...]:
        store = self._replay_operation_store
        if store is None:
            return actions
        replay = self.replay_execution_context
        if replay is None:
            raise DurableOperationPersistenceError(
                "persistent optimizer actions require an active ReplayExecutionContext"
            )

        action_contracts: list[dict[str, str]] = []
        missing_actions: list[str] = []
        for name in actions:
            action = self.get_action(name)
            if action is None:
                missing_actions.append(name)
                continue
            action_contracts.append(_durable_action_contract(action))
        if missing_actions:
            raise DurableOperationPersistenceError(
                "persisted optimizer Action plan contains unregistered Actions: "
                + ", ".join(missing_actions)
            )

        # The persisted plan is authoritative on replay. Build a registry snapshot
        # so the store can validate the contracts of the persisted Action names,
        # even when current optimization proposes a different (or empty) set.
        with self._lock:
            registered_actions = tuple(self._actions.values())
        registered_action_contracts: dict[str, dict[str, str]] = {}
        for registered_action in registered_actions:
            try:
                registered_action_contracts[registered_action.name] = (
                    _durable_action_contract(registered_action)
                )
            except DurableOperationPersistenceError:
                # An unrelated non-durable Action must not invalidate a plan.
                # If a persisted Action itself lacks a contract, the store will
                # reject it because its name will be absent from this mapping.
                continue

        try:
            return store.get_or_create_action_plan(
                tenant_id=replay.tenant_id,
                cycle_id=replay.cycle_id,
                cycle_fingerprint=replay.cycle_fingerprint,
                parent_stage_key=replay.parent_stage_key,
                owner_token=replay.owner_token,
                generation=replay.generation,
                actions=actions,
                action_contracts=tuple(action_contracts),
                registered_action_contracts=registered_action_contracts,
            )
        except Exception as exc:
            raise DurableOperationPersistenceError(
                "could not persist or restore the optimizer Action plan"
            ) from exc

    @property
    def event_publisher(self) -> EventPublisher | None:
        return self._event_publisher

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        self._event_publisher = publisher

    def register_action(self, action: OptimizationAction, *, replace: bool = False) -> None:
        if not isinstance(action, OptimizationAction):
            raise TypeError("action must be OptimizationAction")
        with self._lock:
            if action.name in self._actions and not replace:
                raise KeyError(f"optimization action already registered: {action.name}")
            self._actions[action.name] = action

    def unregister_action(self, name: str) -> OptimizationAction | None:
        with self._lock:
            return self._actions.pop(name, None)

    def get_action(self, name: str) -> OptimizationAction | None:
        with self._lock:
            return self._actions.get(name)

    @property
    def actions(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._actions))

    @property
    def history(self) -> tuple[OptimizationActionResult, ...]:
        with self._lock:
            return tuple(self._history)

    def _register_default_actions(self) -> None:
        self.register_action(
            OptimizationAction(
                "reduce_context_depth",
                self._apply_reduce_context_depth,
                self._rollback_context,
                "Reduce one runtime context level.",
                contract_id="sh3.optimizer.reduce_context_depth",
                implementation_version="1",
                rollback_version="1",
            )
        )
        self.register_action(
            OptimizationAction(
                "compress_memory",
                self._apply_compress_memory,
                self._rollback_noop,
                "Create a deterministic compressed memory view.",
                replay_policy=OptimizationActionReplayPolicy.REUSE_RESULT,
                contract_id="sh3.optimizer.compress_memory",
                implementation_version="1",
                rollback_version="1",
            )
        )
        self.register_action(
            OptimizationAction(
                "simplify_policy",
                self._apply_simplify_policy,
                self._rollback_policy,
                "Remove the lowest-weight policy rule.",
                contract_id="sh3.optimizer.simplify_policy",
                implementation_version="1",
                rollback_version="1",
            )
        )

    def _apply_reduce_context_depth(self, _: Mapping[str, Any]) -> dict[str, Any]:
        context = self.kernel.context_manager.pop()
        if context is None:
            return {"changed": False, "depth": 0, "context": None}
        return {"changed": True, "depth": len(self.kernel.context_manager), "context": context.to_dict()}

    def _rollback_context(
        self,
        result: Any,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        if not isinstance(result, Mapping) or not result.get("changed"):
            return
        data = result.get("context")
        if not isinstance(data, Mapping):
            return
        context = self.kernel.context_manager.push(str(data.get("name", "restored")))
        state = data.get("state", {})
        if isinstance(state, Mapping):
            context.update(state)

    def _apply_compress_memory(self, context: Mapping[str, Any]) -> dict[str, Any]:
        group_size = context.get("group_size", 5)
        groups = self.memory.compress(group_size)
        return {"changed": False, "groups": groups, "group_size": group_size}

    @staticmethod
    def _rollback_noop(
        _: Any,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        return None

    def _apply_simplify_policy(self, _: Mapping[str, Any]) -> dict[str, Any]:
        rules = self.kernel.policy.rules
        if not rules:
            return {"changed": False, "rule": None}
        index, rule = min(enumerate(rules), key=lambda item: (item[1].weight, item[0]))
        rules.pop(index)
        return {"changed": True, "index": index, "rule": rule}

    def _rollback_policy(
        self,
        result: Any,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        if not isinstance(result, Mapping) or not result.get("changed"):
            return
        rule = result.get("rule")
        index = result.get("index")
        if rule is None or not isinstance(index, int):
            return
        rules = self.kernel.policy.rules
        rules.insert(min(index, len(rules)), rule)

    def execute_action(
        self,
        name: str,
        context: Mapping[str, Any] | None = None,
    ) -> OptimizationActionResult:
        stored_context = dict(context or {})
        parent_idempotency_key = stored_context.get("idempotency_key")
        if (
            self._replay_operation_store is not None
            and self.replay_execution_context is not None
            and parent_idempotency_key is None
        ):
            raise DurableOperationPersistenceError(
                "persistent replay Action execution requires the parent Stage idempotency key"
            )
        if parent_idempotency_key is None:
            return self._execute_action(name, stored_context)
        action_idempotency_key = _action_idempotency_key(
            parent_idempotency_key,
            name,
            0,
        )
        return self._execute_action(
            name,
            stored_context,
            idempotency_key=action_idempotency_key,
            parent_idempotency_key=parent_idempotency_key,
        )

    def _execute_action(
        self,
        name: str,
        context: Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        parent_idempotency_key: str | None = None,
        ordinal: int = 0,
    ) -> OptimizationActionResult:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        action = self.get_action(name)
        if action is None:
            raise KeyError(f"unknown optimization action: {name}")
        stored_context = dict(context or {})
        key_fields: dict[str, Any] = {}
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise ValueError("idempotency_key must not be empty")
            if not isinstance(parent_idempotency_key, str) or not parent_idempotency_key.strip():
                raise ValueError("parent_idempotency_key must not be empty")
            stored_context["idempotency_key"] = idempotency_key
            stored_context["parent_idempotency_key"] = parent_idempotency_key
            key_fields = {
                "idempotency_key": idempotency_key,
                "parent_idempotency_key": parent_idempotency_key,
            }
        if idempotency_key is not None and self._replay_operation_store is not None:
            if parent_idempotency_key is None:
                raise ValueError("parent_idempotency_key must not be empty")
            return self._execute_durable_action(
                action,
                name,
                stored_context,
                idempotency_key,
                parent_idempotency_key,
                ordinal,
                key_fields,
            )
        try:
            value = action.apply(stored_context)
            result = OptimizationActionResult(
                action=name,
                success=True,
                result=value,
                idempotency_key=idempotency_key,
                parent_idempotency_key=parent_idempotency_key,
                ordinal=ordinal,
            )
        except Exception as exc:
            result = OptimizationActionResult(
                action=name,
                success=False,
                error=str(exc),
                idempotency_key=idempotency_key,
                parent_idempotency_key=parent_idempotency_key,
                ordinal=ordinal,
            )
            with self._lock:
                self._history.append(result)
            self._publish(
                "OptimizationFailed",
                EventType.FAILURE,
                {
                    "optimization_id": self.optimizer_id,
                    "action": name,
                    "error": str(exc),
                    **key_fields,
                },
            )
            return result
        with self._lock:
            self._history.append(result)
        return result

    @staticmethod
    def _durable_result_envelope(result: OptimizationActionResult) -> dict[str, Any]:
        return {
            "action": result.action,
            "success": result.success,
            "result": _operation_json_value(result.result),
            "rolled_back": result.rolled_back,
            "error": result.error,
            "state_uncertain": result.state_uncertain,
            "ordinal": result.ordinal,
        }

    @staticmethod
    def _restore_durable_result(
        envelope: Mapping[str, Any],
        *,
        idempotency_key: str,
        parent_idempotency_key: str | None,
        rollback_idempotency_key: str | None = None,
        ordinal: int = 0,
    ) -> OptimizationActionResult:
        action = envelope.get("action")
        success = envelope.get("success")
        rolled_back = envelope.get("rolled_back", False)
        state_uncertain = envelope.get("state_uncertain", False)
        error_value = envelope.get("error")
        stored_ordinal = envelope.get("ordinal", ordinal)
        if (
            not isinstance(action, str)
            or not action.strip()
            or not isinstance(success, bool)
            or not isinstance(rolled_back, bool)
            or not isinstance(state_uncertain, bool)
            or (error_value is not None and not isinstance(error_value, str))
            or isinstance(stored_ordinal, bool)
            or not isinstance(stored_ordinal, int)
            or stored_ordinal < 0
        ):
            raise ValueError("persisted optimizer Action result envelope is invalid")
        return OptimizationActionResult(
            action=action,
            success=success,
            result=envelope.get("result"),
            rolled_back=rolled_back,
            error=error_value,
            idempotency_key=idempotency_key,
            parent_idempotency_key=parent_idempotency_key,
            rollback_idempotency_key=rollback_idempotency_key,
            state_uncertain=state_uncertain,
            ordinal=stored_ordinal,
        )

    def _execute_durable_action(
        self,
        action: OptimizationAction,
        name: str,
        stored_context: Mapping[str, Any],
        idempotency_key: str,
        parent_idempotency_key: str,
        ordinal: int,
        key_fields: Mapping[str, Any],
    ) -> OptimizationActionResult:
        replay = self.replay_execution_context
        store = self._replay_operation_store
        if replay is None or store is None:
            raise DurableOperationPersistenceError(
                "durable Action execution requires the configured store and ReplayExecutionContext"
            )
        if not isinstance(parent_idempotency_key, str) or not parent_idempotency_key.strip():
            raise DurableOperationPersistenceError(
                "durable Action execution requires a non-empty parent Stage key"
            )
        if replay.parent_stage_key != parent_idempotency_key:
            raise DurableOperationPersistenceError(
                "Action parent key does not match the active Replay Stage"
            )
        action_contract = _durable_action_contract(action)
        volatile = {
            "idempotency_key",
            "parent_idempotency_key",
            "correlation_id",
            "causation_id",
            "trace_id",
            "tenant_id",
        }
        semantic_context = {
            key: value for key, value in stored_context.items() if key not in volatile
        }
        try:
            key = ReplayOperationKey.create(
                idempotency_key=idempotency_key,
                tenant_id=replay.tenant_id,
                cycle_id=replay.cycle_id,
                cycle_fingerprint=replay.cycle_fingerprint,
                parent_stage_key=replay.parent_stage_key,
                operation_kind=ReplayOperationKind.ACTION,
                operation_name=name,
                ordinal=ordinal,
                input_payload={
                    "action": name,
                    "ordinal": ordinal,
                    "replay_policy": action.replay_policy.value,
                    "action_contract": action_contract,
                    "context": _operation_json_value(semantic_context),
                },
            )
            cache_key = (key.tenant_scope, key.idempotency_key)
            existing = store.get(key)
            with self._lock:
                local_result = self._local_operation_results.get(cache_key)
            if (
                existing is not None
                and existing.status is ReplayOperationStatus.CLAIMED
                and existing.generation == replay.generation
                and existing.owner_token == replay.owner_token
                and local_result is not None
            ):
                store.complete(
                    key,
                    replay.owner_token,
                    replay.generation,
                    self._durable_result_envelope(local_result),
                )
                with self._lock:
                    if not any(item is local_result for item in self._history):
                        self._history.append(local_result)
                return local_result
            execution = store.begin(
                key,
                replay.owner_token,
                replay.generation,
            )
        except DurableOperationPersistenceError:
            raise
        except Exception as exc:
            raise DurableOperationPersistenceError(
                f"could not claim durable optimizer Action {name}"
            ) from exc
        cache_key = (key.tenant_scope, key.idempotency_key)
        with self._lock:
            local_result = self._local_operation_results.get(cache_key)
        if execution.status is ReplayOperationStatus.COMPLETED:
            if local_result is not None:
                return local_result
            if execution.result is None:
                raise DurableOperationPersistenceError(
                    "completed optimizer Action has no persisted outcome"
                )
            try:
                restored = self._restore_durable_result(
                    execution.result,
                    idempotency_key=idempotency_key,
                    parent_idempotency_key=parent_idempotency_key,
                    ordinal=ordinal,
                )
            except Exception as exc:
                raise DurableOperationPersistenceError(
                    "could not restore the completed optimizer Action outcome"
                ) from exc
            if restored.action != name or restored.ordinal != ordinal:
                raise DurableOperationPersistenceError(
                    "completed optimizer Action outcome does not match its ledger identity"
                )
            if (
                restored.success
                and (
                    not isinstance(restored.result, Mapping)
                    or restored.result.get("changed") is not False
                )
                and action.replay_policy
                is OptimizationActionReplayPolicy.REQUIRE_LOCAL_STATE
            ):
                restored = OptimizationActionResult(
                    action=name,
                    success=False,
                    result=restored.result,
                    error=(
                        "completed Action result exists, but this Runtime's in-memory "
                        "state was not restored; reconciliation is required"
                    ),
                    idempotency_key=idempotency_key,
                    parent_idempotency_key=parent_idempotency_key,
                    state_uncertain=True,
                    ordinal=ordinal,
                )
            with self._lock:
                self._history.append(restored)
            if not restored.success:
                self._publish(
                    "OptimizationFailed",
                    EventType.FAILURE,
                    {
                        "optimization_id": self.optimizer_id,
                        "action": name,
                        "error": restored.error or "persisted Action failed",
                        **dict(key_fields),
                        **({"state_uncertain": True} if restored.state_uncertain else {}),
                        "replayed": True,
                    },
                )
            return restored

        if local_result is not None:
            try:
                store.complete(
                    key,
                    replay.owner_token,
                    replay.generation,
                    self._durable_result_envelope(local_result),
                )
            except Exception as exc:
                raise DurableOperationPersistenceError(
                    f"could not finalize cached optimizer Action {name}"
                ) from exc
            with self._lock:
                if not any(item is local_result for item in self._history):
                    self._history.append(local_result)
            return local_result

        if (
            execution.attempts > 1
            and action.replay_policy
            is OptimizationActionReplayPolicy.REQUIRE_LOCAL_STATE
        ):
            result = OptimizationActionResult(
                action=name,
                success=False,
                error=(
                    "an earlier Action attempt was interrupted and its Runtime-local "
                    "state cannot be proven after ownership takeover"
                ),
                idempotency_key=idempotency_key,
                parent_idempotency_key=parent_idempotency_key,
                state_uncertain=True,
                ordinal=ordinal,
            )
            with self._lock:
                self._local_operation_results[cache_key] = result
            try:
                store.complete(
                    key,
                    replay.owner_token,
                    replay.generation,
                    self._durable_result_envelope(result),
                )
            except Exception as exc:
                raise DurableOperationPersistenceError(
                    f"could not persist uncertain optimizer Action {name}"
                ) from exc
            with self._lock:
                self._history.append(result)
            return result

        try:
            value = action.apply(dict(stored_context))
            result = OptimizationActionResult(
                action=name,
                success=True,
                result=value,
                idempotency_key=idempotency_key,
                parent_idempotency_key=parent_idempotency_key,
                ordinal=ordinal,
            )
        except Exception as exc:
            result = OptimizationActionResult(
                action=name,
                success=False,
                error=str(exc),
                idempotency_key=idempotency_key,
                parent_idempotency_key=parent_idempotency_key,
                state_uncertain=True,
                ordinal=ordinal,
            )
        with self._lock:
            self._local_operation_results[cache_key] = result
        try:
            store.complete(
                key,
                replay.owner_token,
                replay.generation,
                self._durable_result_envelope(result),
            )
        except Exception as exc:
            raise DurableOperationPersistenceError(
                f"could not persist optimizer Action outcome {name}"
            ) from exc
        with self._lock:
            self._history.append(result)
        if not result.success:
            self._publish(
                "OptimizationFailed",
                EventType.FAILURE,
                {
                    "optimization_id": self.optimizer_id,
                    "action": name,
                    "error": result.error or "optimizer Action failed",
                    **dict(key_fields),
                    "state_uncertain": result.state_uncertain,
                },
            )
        return result

    def _rollback_durable_action(
        self,
        result: OptimizationActionResult,
        action: OptimizationAction,
        rollback_key: str,
        rollback_key_fields: Mapping[str, Any],
    ) -> OptimizationActionResult:
        replay = self.replay_execution_context
        store = self._replay_operation_store
        if replay is None or store is None or result.idempotency_key is None:
            raise DurableOperationPersistenceError(
                "durable Rollback execution requires the active replay context and Action key"
            )
        action_contract = _durable_action_contract(action)
        try:
            operation_key = ReplayOperationKey.create(
                idempotency_key=rollback_key,
                tenant_id=replay.tenant_id,
                cycle_id=replay.cycle_id,
                cycle_fingerprint=replay.cycle_fingerprint,
                parent_stage_key=replay.parent_stage_key,
                operation_kind=ReplayOperationKind.ROLLBACK,
                operation_name=result.action,
                ordinal=result.ordinal,
                parent_operation_key=result.idempotency_key,
                input_payload={
                    "action": result.action,
                    "ordinal": result.ordinal,
                    "action_contract": action_contract,
                    "action_result": _operation_json_value(result.result),
                },
            )
            cache_key = (operation_key.tenant_scope, operation_key.idempotency_key)
            existing = store.get(operation_key)
            with self._lock:
                local_result = self._local_operation_results.get(cache_key)
            if (
                existing is not None
                and existing.status is ReplayOperationStatus.CLAIMED
                and existing.generation == replay.generation
                and existing.owner_token == replay.owner_token
                and local_result is not None
            ):
                store.complete(
                    operation_key,
                    replay.owner_token,
                    replay.generation,
                    self._durable_result_envelope(local_result),
                )
                with self._lock:
                    if not any(item is local_result for item in self._history):
                        self._history.append(local_result)
                return local_result
            execution = store.begin(
                operation_key,
                replay.owner_token,
                replay.generation,
            )
        except DurableOperationPersistenceError:
            raise
        except Exception as exc:
            raise DurableOperationPersistenceError(
                f"could not claim optimizer Rollback {result.action}"
            ) from exc
        cache_key = (operation_key.tenant_scope, operation_key.idempotency_key)
        with self._lock:
            local_result = self._local_operation_results.get(cache_key)
        if execution.status is ReplayOperationStatus.COMPLETED:
            if local_result is not None:
                return local_result
            if execution.result is None:
                raise DurableOperationPersistenceError(
                    "completed optimizer Rollback has no persisted outcome"
                )
            try:
                restored = self._restore_durable_result(
                    execution.result,
                    idempotency_key=result.idempotency_key,
                    parent_idempotency_key=result.parent_idempotency_key,
                    rollback_idempotency_key=rollback_key,
                    ordinal=result.ordinal,
                )
            except Exception as exc:
                raise DurableOperationPersistenceError(
                    "could not restore the completed optimizer Rollback outcome"
                ) from exc
            if restored.action != result.action or restored.ordinal != result.ordinal:
                raise DurableOperationPersistenceError(
                    "completed optimizer Rollback outcome does not match its ledger identity"
                )
            with self._lock:
                self._history.append(restored)
            return restored

        if local_result is not None:
            try:
                store.complete(
                    operation_key,
                    replay.owner_token,
                    replay.generation,
                    self._durable_result_envelope(local_result),
                )
            except Exception as exc:
                raise DurableOperationPersistenceError(
                    f"could not finalize cached optimizer Rollback {result.action}"
                ) from exc
            with self._lock:
                if not any(item is local_result for item in self._history):
                    self._history.append(local_result)
            return local_result

        if (
            execution.attempts > 1
            and action.replay_policy
            is OptimizationActionReplayPolicy.REQUIRE_LOCAL_STATE
        ):
            state_uncertain = (
                not isinstance(result.result, Mapping)
                or result.result.get("changed") is not False
            )
            outcome = OptimizationActionResult(
                action=result.action,
                success=False,
                result=result.result,
                error=(
                    "an earlier Rollback attempt was interrupted and its Runtime-local "
                    "state cannot be proven after ownership takeover"
                ),
                idempotency_key=result.idempotency_key,
                parent_idempotency_key=result.parent_idempotency_key,
                rollback_idempotency_key=rollback_key,
                state_uncertain=state_uncertain,
                ordinal=result.ordinal,
            )
            with self._lock:
                self._local_operation_results[cache_key] = outcome
            try:
                store.complete(
                    operation_key,
                    replay.owner_token,
                    replay.generation,
                    self._durable_result_envelope(outcome),
                )
            except Exception as exc:
                raise DurableOperationPersistenceError(
                    f"could not persist uncertain optimizer Rollback {result.action}"
                ) from exc
            with self._lock:
                self._history.append(outcome)
            return outcome

        try:
            if not _accepts_keyword_argument(action.rollback, "idempotency_key"):
                raise TypeError(
                    "keyed optimization rollback callback must accept the idempotency_key keyword argument"
                )
            action.rollback(result.result, idempotency_key=rollback_key)
            outcome = OptimizationActionResult(
                action=result.action,
                success=True,
                result=result.result,
                rolled_back=True,
                idempotency_key=result.idempotency_key,
                parent_idempotency_key=result.parent_idempotency_key,
                rollback_idempotency_key=rollback_key,
                ordinal=result.ordinal,
            )
        except Exception as exc:
            state_uncertain = (
                not isinstance(result.result, Mapping)
                or result.result.get("changed") is not False
            )
            outcome = OptimizationActionResult(
                action=result.action,
                success=False,
                result=result.result,
                error=str(exc),
                idempotency_key=result.idempotency_key,
                parent_idempotency_key=result.parent_idempotency_key,
                rollback_idempotency_key=rollback_key,
                state_uncertain=state_uncertain,
                ordinal=result.ordinal,
            )
        with self._lock:
            self._local_operation_results[cache_key] = outcome
        try:
            store.complete(
                operation_key,
                replay.owner_token,
                replay.generation,
                self._durable_result_envelope(outcome),
            )
        except Exception as exc:
            raise DurableOperationPersistenceError(
                f"could not persist optimizer Rollback outcome {result.action}"
            ) from exc
        with self._lock:
            self._history.append(outcome)
        if not outcome.success:
            self._publish(
                "OptimizationFailed",
                EventType.FAILURE,
                {
                    "optimization_id": self.optimizer_id,
                    "action": result.action,
                    "error": outcome.error or "optimizer Rollback failed",
                    "rollback": True,
                    "state_uncertain": outcome.state_uncertain,
                    **dict(rollback_key_fields),
                },
            )
        return outcome

    def rollback_action(self, result: OptimizationActionResult) -> OptimizationActionResult:
        if not isinstance(result, OptimizationActionResult):
            raise TypeError("result must be OptimizationActionResult")
        if not result.success or result.rolled_back:
            return result
        action = self.get_action(result.action)
        if action is None:
            raise KeyError(f"unknown optimization action: {result.action}")

        rollback_key = None
        rollback_key_fields: dict[str, Any] = {}
        if result.idempotency_key is not None:
            rollback_key = _rollback_idempotency_key(
                result.idempotency_key,
                result.action,
            )
            rollback_key_fields = {
                "idempotency_key": result.idempotency_key,
                "parent_idempotency_key": result.parent_idempotency_key,
                "rollback_idempotency_key": rollback_key,
            }

        if rollback_key is not None and self._replay_operation_store is not None:
            return self._rollback_durable_action(
                result,
                action,
                rollback_key,
                rollback_key_fields,
            )

        try:
            if rollback_key is None:
                action.rollback(result.result)
            else:
                if not _accepts_keyword_argument(action.rollback, "idempotency_key"):
                    raise TypeError(
                        "keyed optimization rollback callback must accept the "
                        "idempotency_key keyword argument"
                    )
                action.rollback(result.result, idempotency_key=rollback_key)
        except Exception as exc:
            state_uncertain = (
                not isinstance(result.result, Mapping)
                or result.result.get("changed") is not False
            )
            failure = OptimizationActionResult(
                action=result.action,
                success=False,
                result=result.result,
                error=str(exc),
                idempotency_key=result.idempotency_key,
                parent_idempotency_key=result.parent_idempotency_key,
                rollback_idempotency_key=rollback_key,
                state_uncertain=state_uncertain,
            )
            self._publish(
                "OptimizationFailed",
                EventType.FAILURE,
                {
                    "optimization_id": self.optimizer_id,
                    "action": result.action,
                    "error": str(exc),
                    "rollback": True,
                    "state_uncertain": state_uncertain,
                    **rollback_key_fields,
                },
            )
            with self._lock:
                self._history.append(failure)
            return failure

        rolled_back = OptimizationActionResult(
            action=result.action,
            success=True,
            result=result.result,
            rolled_back=True,
            idempotency_key=result.idempotency_key,
            parent_idempotency_key=result.parent_idempotency_key,
            rollback_idempotency_key=rollback_key,
        )
        with self._lock:
            self._history.append(rolled_back)
        return rolled_back

    def execute_actions(
        self,
        actions: list[str] | tuple[str, ...],
        context: Mapping[str, Any] | None = None,
        *,
        rollback_on_failure: bool = True,
    ) -> tuple[OptimizationActionResult, ...]:
        results: list[OptimizationActionResult] = []
        base_context = dict(context or {})
        parent_idempotency_key = base_context.get("idempotency_key")
        if parent_idempotency_key is not None and (
            not isinstance(parent_idempotency_key, str)
            or not parent_idempotency_key.strip()
        ):
            raise ValueError("idempotency_key must not be empty")
        if (
            self._replay_operation_store is not None
            and self.replay_execution_context is not None
            and parent_idempotency_key is None
        ):
            raise DurableOperationPersistenceError(
                "persistent replay Action sequence requires the parent Stage idempotency key"
            )
        if parent_idempotency_key is not None and self._replay_operation_store is not None:
            actions = self._persisted_action_plan(tuple(actions))
        if self._replay_operation_store is not None:
            missing_actions = tuple(
                name for name in actions if self.get_action(name) is None
            )
            if missing_actions:
                raise DurableOperationPersistenceError(
                    "persisted optimizer Action plan contains unregistered Actions: "
                    + ", ".join(missing_actions)
                )

        for ordinal, name in enumerate(actions):
            if parent_idempotency_key is None:
                result = self.execute_action(name, base_context)
            else:
                result = self._execute_action(
                    name,
                    base_context,
                    idempotency_key=_action_idempotency_key(
                        parent_idempotency_key,
                        name,
                        ordinal,
                    ),
                    parent_idempotency_key=parent_idempotency_key,
                    ordinal=ordinal,
                )
            results.append(result)
            if not result.success:
                if rollback_on_failure:
                    for index in range(len(results) - 2, -1, -1):
                        previous = results[index]
                        if previous.success and not previous.rolled_back:
                            results[index] = self.rollback_action(previous)
                break
        return tuple(results)
    def _publish(
        self,
        event_name: str,
        event_type: EventType,
        payload: dict[str, Any],
    ) -> None:
        publisher = self._event_publisher
        if publisher is None:
            return
        try:
            correlation_id = self._propagation_context.correlation_id if self._propagation_context is not None else self.optimizer_id
            causation_id = self._propagation_context.causation_id if self._propagation_context is not None else self._last_event_id
            trace_id = self._propagation_context.trace_id if self._propagation_context is not None else None
            tenant_id = self._propagation_context.tenant_id if self._propagation_context is not None else None
            event = Event.create(
                event_name=event_name,
                producer="optimizer",
                payload=payload,
                category=Category.ACTION,
                event_type=event_type,
                correlation_id=correlation_id,
                causation_id=causation_id,
                trace_id=trace_id,
                tenant_id=tenant_id,
            )
            publisher.publish(event)
            self._last_event_id = event.metadata.event_id
            self._propagation_context = EventPropagationContext(
                correlation_id=correlation_id,
                causation_id=event.metadata.event_id,
                trace_id=trace_id,
                tenant_id=tenant_id,
            )
        except Exception as exc:
            error(
                "SystemOptimizer event publication failed",
                {"event_name": event_name, "error": str(exc)},
            )

    def snapshot(self) -> dict[str, Any]:
        snap = {
            "context_depth": self.kernel.context_manager.snapshot()["depth"],
            "memory_size": len(self.kernel.history(limit=100)),
            "policy_count": len(self.kernel.policy.rules),
        }

        info("System snapshot created", snap)
        return snap

    def detect_bottlenecks(
        self,
        snapshot: dict[str, Any],
    ) -> dict[str, float]:
        bottlenecks = {
            "context_pressure": snapshot["context_depth"] * 0.15,
            "memory_pressure": snapshot["memory_size"] / 100,
            "policy_complexity": snapshot["policy_count"] / 10,
        }

        info("Bottlenecks detected", bottlenecks)
        return bottlenecks

    def score_modules(self) -> dict[str, float]:
        scores = {
            "runtime": 0.8,
            "cognition": 0.9,
            "policy": 0.7,
            "memory": 0.85,
            "kernel": 0.95,
        }

        info("Module scores computed", scores)
        return scores

    def rebalance(
        self,
        bottlenecks: dict[str, float],
    ) -> dict[str, Any]:
        actions: list[str] = []

        if bottlenecks["context_pressure"] > 1.0:
            actions.append("reduce_context_depth")

        if bottlenecks["memory_pressure"] > 0.8:
            actions.append("compress_memory")

        if bottlenecks["policy_complexity"] > 0.9:
            actions.append("simplify_policy")

        info("Rebalance actions determined", {"actions": actions})

        return {
            "actions": actions,
            "optimizer_id": self.optimizer_id,
        }

    def prune(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        pruned: list[str] = []

        if snapshot["memory_size"] > 80:
            pruned.append("memory:old_experiences")

        if snapshot["policy_count"] > 8:
            pruned.append("policy:weak_rules")

        info("Pruning completed", {"pruned": pruned})

        return {
            "pruned": pruned,
            "optimizer_id": self.optimizer_id,
        }

    def optimize(
        self,
        *,
        context: EventPropagationContext | None = None,
        execute: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if idempotency_key is not None and (
            not isinstance(idempotency_key, str) or not idempotency_key.strip()
        ):
            raise ValueError("idempotency_key must not be empty")
        if (
            self._replay_operation_store is not None
            and self.replay_execution_context is not None
            and idempotency_key is None
        ):
            raise DurableOperationPersistenceError(
                "persistent replay optimization requires the parent Stage idempotency key"
            )
        if context is not None:
            self.set_propagation_context(context)

        self._publish(
            "OptimizationStarted",
            EventType.START,
            {"optimizer_id": self.optimizer_id},
        )

        snapshot = self.snapshot()
        bottlenecks = self.detect_bottlenecks(snapshot)
        modules = self.score_modules()
        rebalance_actions = self.rebalance(bottlenecks)
        prune_actions = self.prune(snapshot)

        proposed_actions = tuple(rebalance_actions["actions"])
        if self._replay_operation_store is not None and self.replay_execution_context is not None:
            persisted_actions = self._persisted_action_plan(proposed_actions)
            rebalance_actions = dict(rebalance_actions)
            rebalance_actions["actions"] = list(persisted_actions)
            proposed_actions = persisted_actions
        execution: tuple[OptimizationActionResult, ...] = ()
        if execute:
            action_context = (
                {"idempotency_key": idempotency_key}
                if idempotency_key is not None
                else None
            )
            execution = self.execute_actions(proposed_actions, action_context)
        result = {
            "optimizer_id": self.optimizer_id,
            "snapshot": snapshot,
            "bottlenecks": bottlenecks,
            "module_scores": modules,
            "rebalance": rebalance_actions,
            "prune": prune_actions,
            "execution": tuple(item.to_dict() for item in execution),
        }

        success = all(item.success for item in execution) if execution else True
        if execute:
            self._publish(
                "OptimizationEvaluated",
                EventType.COMPLETE,
                {
                    "optimization_id": self.optimizer_id,
                    "success": success,
                    "actions": len(execution),
                },
            )
        self._publish(
            "OptimizationCompleted" if success else "OptimizationFailed",
            EventType.COMPLETE if success else EventType.FAILURE,
            {
                "optimizer_id": self.optimizer_id,
                "success": success,
                "changes": tuple(item.to_dict() for item in execution),
            },
        )

        info("System optimization completed", result)
        return result
