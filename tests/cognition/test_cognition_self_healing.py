from __future__ import annotations

from foundation.utils.exceptions import SH3Exception
from self_healing.core import SelfHealingCore


def test_execute_safe_returns_the_function_result() -> None:
    healer = SelfHealingCore()

    assert healer.execute_safe(lambda value: value + 1, 2) == 3


def test_execute_safe_recovers_from_sh3_exception() -> None:
    healer = SelfHealingCore()

    def fail() -> None:
        raise SH3Exception("temporary failure")

    result = healer.execute_safe(fail, context={"operation": "test"})

    assert result["status"] == "retried"
    assert result["trace_id"]
