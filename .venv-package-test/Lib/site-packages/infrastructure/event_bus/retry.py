"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Event Bus
Retry Management
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Final

__all__ = [
    "RetryDecision",
    "RetryManager",
    "RetryPolicy",
    "RetryState",
]

_DEFAULT_MAX_ATTEMPTS: Final[int] = 3
_DEFAULT_INITIAL_DELAY: Final[float] = 0.0
_DEFAULT_BACKOFF: Final[float] = 2.0
_DEFAULT_MAX_DELAY: Final[float] = 60.0
_DEFAULT_JITTER: Final[float] = 0.0


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS
    initial_delay: float = _DEFAULT_INITIAL_DELAY
    backoff: float = _DEFAULT_BACKOFF
    max_delay: float = _DEFAULT_MAX_DELAY
    jitter: float = _DEFAULT_JITTER

    def __post_init__(self) -> None:
        if self.max_attempts < 0:
            raise ValueError("max_attempts must be >= 0")
        if self.initial_delay < 0:
            raise ValueError("initial_delay must be >= 0")
        if self.backoff < 1.0:
            raise ValueError("backoff must be >= 1.0")
        if self.max_delay < 0:
            raise ValueError("max_delay must be >= 0")
        if self.jitter < 0:
            raise ValueError("jitter must be >= 0")

    def delay(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        if self.initial_delay == 0.0:
            return 0.0
        value = self.initial_delay * (self.backoff ** (attempt - 1))
        return min(value, self.max_delay)


@dataclass(frozen=True, slots=True)
class RetryState:
    key: Hashable
    attempts: int
    failures: int
    last_error: BaseException | None
    next_retry_at: float | None
    exhausted: bool


@dataclass(frozen=True, slots=True)
class RetryDecision:
    retry: bool
    exhausted: bool
    attempt: int
    delay: float
    next_retry_at: float | None


class RetryManager:
    def __init__(
        self,
        policy: RetryPolicy | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._policy = policy or RetryPolicy()
        self._clock = clock
        self._lock = RLock()
        self._states: dict[Hashable, RetryState] = {}

    @property
    def policy(self) -> RetryPolicy:
        return self._policy

    def state(self, key: Hashable) -> RetryState:
        with self._lock:
            state = self._states.get(key)
            if state is not None:
                return state
            return RetryState(
                key=key,
                attempts=0,
                failures=0,
                last_error=None,
                next_retry_at=None,
                exhausted=False,
            )

    def should_retry(self, key: Hashable) -> bool:
        with self._lock:
            state = self.state(key)
            if state.exhausted:
                return False
            if state.next_retry_at is None:
                return True
            return self._clock() >= state.next_retry_at

    def record_failure(
        self,
        key: Hashable,
        error: BaseException,
    ) -> RetryDecision:
        with self._lock:
            previous = self.state(key)
            attempt = previous.attempts + 1
            exhausted = attempt >= self._policy.max_attempts

            if exhausted:
                state = RetryState(
                    key=key,
                    attempts=attempt,
                    failures=previous.failures + 1,
                    last_error=error,
                    next_retry_at=None,
                    exhausted=True,
                )
                self._states[key] = state
                return RetryDecision(
                    retry=False,
                    exhausted=True,
                    attempt=attempt,
                    delay=0.0,
                    next_retry_at=None,
                )

            delay = self._policy.delay(attempt)
            next_retry_at = self._clock() + delay

            state = RetryState(
                key=key,
                attempts=attempt,
                failures=previous.failures + 1,
                last_error=error,
                next_retry_at=next_retry_at,
                exhausted=False,
            )
            self._states[key] = state

            return RetryDecision(
                retry=True,
                exhausted=False,
                attempt=attempt,
                delay=delay,
                next_retry_at=next_retry_at,
            )

    def record_success(self, key: Hashable) -> RetryState:
        with self._lock:
            state = self.state(key)
            self._states.pop(key, None)
            return RetryState(
                key=key,
                attempts=state.attempts,
                failures=state.failures,
                last_error=None,
                next_retry_at=None,
                exhausted=False,
            )

    def reset(self, key: Hashable) -> None:
        with self._lock:
            self._states.pop(key, None)

    def exhausted(self, key: Hashable) -> bool:
        with self._lock:
            return self.state(key).exhausted

    def attempts(self, key: Hashable) -> int:
        with self._lock:
            return self.state(key).attempts

    def failures(self, key: Hashable) -> int:
        with self._lock:
            return self.state(key).failures

    def next_retry_at(self, key: Hashable) -> float | None:
        with self._lock:
            return self.state(key).next_retry_at

    def snapshot(self) -> Mapping[Hashable, RetryState]:
        with self._lock:
            return dict(self._states)

    def clear(self) -> None:
        with self._lock:
            self._states.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._states)
