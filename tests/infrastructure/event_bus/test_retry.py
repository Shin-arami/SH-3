from __future__ import annotations

import pytest

from infrastructure.event_bus.retry import RetryManager, RetryPolicy


def test_attempt_count_and_failure_count() -> None:
    manager = RetryManager(RetryPolicy(max_attempts=3))
    assert manager.attempts("key") == 0
    assert manager.failures("key") == 0
    first = manager.record_failure("key", RuntimeError("one"))
    second = manager.record_failure("key", RuntimeError("two"))
    assert first.retry and first.attempt == 1
    assert second.retry and second.attempt == 2
    assert manager.attempts("key") == 2
    assert manager.failures("key") == 2


def test_backoff() -> None:
    policy = RetryPolicy(max_attempts=5, initial_delay=2.0, backoff=3.0, max_delay=10.0)
    assert policy.delay(1) == 2.0
    assert policy.delay(2) == 6.0
    assert policy.delay(3) == 10.0
    assert policy.delay(4) == 10.0


def test_exhaustion() -> None:
    manager = RetryManager(RetryPolicy(max_attempts=3))
    assert manager.record_failure("key", RuntimeError("one")).retry
    assert manager.record_failure("key", RuntimeError("two")).retry
    decision = manager.record_failure("key", RuntimeError("three"))
    assert not decision.retry
    assert decision.exhausted
    assert decision.attempt == 3
    assert manager.exhausted("key")
    assert not manager.should_retry("key")


def test_success_reset() -> None:
    manager = RetryManager(RetryPolicy(max_attempts=3))
    manager.record_failure("key", RuntimeError("failure"))
    state = manager.record_success("key")
    assert state.attempts == 1
    assert state.failures == 1
    assert state.last_error is None
    assert not state.exhausted
    assert manager.attempts("key") == 0
    assert manager.failures("key") == 0
    assert manager.next_retry_at("key") is None


def test_deterministic_clock() -> None:
    now = [100.0]
    manager = RetryManager(
        RetryPolicy(max_attempts=3, initial_delay=5.0, backoff=2.0), clock=lambda: now[0]
    )
    decision = manager.record_failure("key", RuntimeError("failure"))
    assert decision.delay == 5.0
    assert decision.next_retry_at == 105.0
    assert not manager.should_retry("key")
    now[0] = 105.0
    assert manager.should_retry("key")


def test_invalid_policy() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=-1)
    with pytest.raises(ValueError):
        RetryPolicy(initial_delay=-1)
    with pytest.raises(ValueError):
        RetryPolicy(backoff=0.5)
