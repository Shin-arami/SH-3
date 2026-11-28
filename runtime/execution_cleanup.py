from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any

__all__ = ["CleanupFailure", "CleanupResult", "RuntimeExecutionCleanupManager"]

CleanupAction = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class CleanupFailure:
    execution_id: str
    name: str
    error_type: str
    error_message: str


@dataclass(frozen=True, slots=True)
class CleanupResult:
    execution_id: str
    attempted: bool
    completed: bool
    failures: tuple[CleanupFailure, ...] = ()

    @property
    def failed(self) -> bool:
        return bool(self.failures)


@dataclass(frozen=True, slots=True)
class _CleanupEntry:
    sequence: int
    name: str
    action: CleanupAction


class RuntimeExecutionCleanupManager:
    __slots__ = ("_completed", "_failures", "_items", "_lock", "_next_sequence")

    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, list[_CleanupEntry]] = {}
        self._next_sequence = 0
        self._completed: set[str] = set()
        self._failures: dict[str, tuple[CleanupFailure, ...]] = {}

    def register(self, execution_id: str, action: CleanupAction, *, name: str = "cleanup") -> None:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        if not callable(action):
            raise TypeError("action must be callable")
        if not name:
            raise ValueError("name must not be empty")
        with self._lock:
            if execution_id in self._completed:
                raise RuntimeError(f"cleanup already completed: {execution_id}")
            entry = _CleanupEntry(self._next_sequence, name, action)
            self._next_sequence += 1
            self._items.setdefault(execution_id, []).append(entry)

    def cleanup(self, execution_id: str) -> CleanupResult:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            if execution_id in self._completed:
                return CleanupResult(
                    execution_id=execution_id,
                    attempted=False,
                    completed=True,
                    failures=self._failures.get(execution_id, ()),
                )
            entries = tuple(sorted(self._items.pop(execution_id, ()), key=lambda item: item.sequence))
            self._completed.add(execution_id)

        failures: list[CleanupFailure] = []
        for entry in entries:
            try:
                entry.action()
            except Exception as exc:
                failures.append(
                    CleanupFailure(
                        execution_id=execution_id,
                        name=entry.name,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )

        result = CleanupResult(
            execution_id=execution_id,
            attempted=bool(entries),
            completed=not failures,
            failures=tuple(failures),
        )
        with self._lock:
            self._failures[execution_id] = result.failures
        return result

    def is_completed(self, execution_id: str) -> bool:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            return execution_id in self._completed

    def failures(self, execution_id: str) -> tuple[CleanupFailure, ...]:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            return self._failures.get(execution_id, ())

    def registered(self, execution_id: str) -> int:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            return len(self._items.get(execution_id, ()))

    def pending(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._items))
