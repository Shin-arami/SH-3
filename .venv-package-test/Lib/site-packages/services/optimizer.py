from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from foundation.enums import Severity
from foundation.utils.exceptions import SH3Exception

from .base import Service
from .health import HealthState, HealthStatus

__all__ = ["OptimizationResult", "OptimizerException", "OptimizerService"]


class OptimizerException(SH3Exception):
    """Optimizer operation failure."""


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    selected: Any
    score: float
    candidates: int
    index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected,
            "score": self.score,
            "candidates": self.candidates,
            "index": self.index,
        }


class OptimizerService(Service):
    __slots__ = ("_last_result", "_runs", "_started")

    def __init__(self, name: str = "optimizer") -> None:
        super().__init__(name)
        self._runs = 0
        self._last_result: OptimizationResult | None = None
        self._started = False

    def _on_start(self) -> None:
        with self._lock:
            self._started = True

    def _on_suspend(self) -> None:
        with self._lock:
            self._started = False

    def _on_resume(self) -> None:
        with self._lock:
            self._started = True

    def _on_terminate(self) -> None:
        with self._lock:
            self._started = False
            self._last_result = None

    def optimize(
        self,
        candidates: Iterable[Any],
        scorer: Callable[[Any], float],
    ) -> OptimizationResult:
        if not callable(scorer):
            raise TypeError("scorer must be callable")
        values = tuple(candidates)
        if not values:
            raise ValueError("candidates must not be empty")
        scored: list[tuple[int, Any, float]] = []
        for index, candidate in enumerate(values):
            try:
                score = float(scorer(candidate))
            except (TypeError, ValueError) as exc:
                raise OptimizerException(
                    f"Invalid optimization score for candidate {index}"
                ) from exc
            except Exception as exc:
                raise OptimizerException(f"Scorer failed for candidate {index}") from exc
            scored.append((index, candidate, score))
        index, selected, score = max(
            scored,
            key=lambda item: (item[2], -item[0]),
        )
        result = OptimizationResult(
            selected=selected,
            score=score,
            candidates=len(values),
            index=index,
        )
        with self._lock:
            self._runs += 1
            self._last_result = result
        return result

    def select(
        self,
        candidates: Iterable[Any],
        scorer: Callable[[Any], float],
    ) -> Any:
        return self.optimize(candidates, scorer).selected

    def best_score(self) -> float | None:
        with self._lock:
            return None if self._last_result is None else self._last_result.score

    @property
    def runs(self) -> int:
        with self._lock:
            return self._runs

    @property
    def last_result(self) -> OptimizationResult | None:
        with self._lock:
            return self._last_result

    def reset(self) -> None:
        with self._lock:
            self._runs = 0
            self._last_result = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            result = self._last_result
            return {
                "name": self.name,
                "state": self._state.value,
                "started": self._started,
                "runs": self._runs,
                "last_result": None if result is None else result.to_dict(),
            }

    def health(self) -> HealthStatus:
        with self._lock:
            runs = self._runs
            started = self._started
        if self.terminated:
            return HealthStatus.create(
                HealthState.UNHEALTHY,
                "Optimizer service is terminated",
                {"runs": runs},
                self.name,
                Severity.HIGH,
            )
        if self.suspended:
            return HealthStatus.create(
                HealthState.DEGRADED,
                "Optimizer service is suspended",
                {"runs": runs},
                self.name,
                Severity.MEDIUM,
            )
        if started:
            return HealthStatus.create(
                HealthState.HEALTHY,
                "Optimizer service is active",
                {"runs": runs},
                self.name,
                Severity.INFO,
            )
        return HealthStatus.create(
            HealthState.UNKNOWN,
            "Optimizer service is not active",
            {"runs": runs},
            self.name,
            Severity.LOW,
        )
