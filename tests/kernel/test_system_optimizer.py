from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel import SH3Kernel
from kernel.system_optimizer import OptimizationAction, SystemOptimizer


def test_optimize_returns_a_snapshot_and_no_actions_for_default_kernel() -> None:
    kernel = SH3Kernel()

    result = SystemOptimizer(kernel).optimize()

    assert result["snapshot"] == {
        "context_depth": 0,
        "memory_size": 0,
        "policy_count": 0,
    }
    assert result["rebalance"]["actions"] == []
    assert result["prune"]["pruned"] == []


def test_rebalance_and_prune_flag_overloaded_resources() -> None:
    optimizer = SystemOptimizer(SH3Kernel())
    snapshot = {
        "context_depth": 7,
        "memory_size": 81,
        "policy_count": 10,
    }

    bottlenecks = optimizer.detect_bottlenecks(snapshot)

    assert optimizer.rebalance(bottlenecks)["actions"] == [
        "reduce_context_depth",
        "compress_memory",
        "simplify_policy",
    ]
    assert optimizer.prune(snapshot)["pruned"] == [
        "memory:old_experiences",
        "policy:weak_rules",
    ]


def test_execute_actions_derives_stable_unique_child_idempotency_keys() -> None:
    optimizer = SystemOptimizer(SH3Kernel())
    observed: list[dict[str, object]] = []

    def record(context: Mapping[str, Any]) -> dict[str, bool]:
        observed.append(dict(context))
        return {"changed": False}

    optimizer.register_action(OptimizationAction("first", record, lambda _: None))
    optimizer.register_action(OptimizationAction("second", record, lambda _: None))

    first_run = optimizer.execute_actions(
        ("first", "second"),
        {"idempotency_key": "optimizer-parent:test"},
    )
    first_contexts = observed[:]
    second_run = optimizer.execute_actions(
        ("first", "second"),
        {"idempotency_key": "optimizer-parent:test"},
    )

    first_keys = tuple(item.idempotency_key for item in first_run)
    second_keys = tuple(item.idempotency_key for item in second_run)
    assert first_keys == second_keys
    assert len(set(first_keys)) == 2
    assert all(key is not None and key.startswith("optimizer-action:") for key in first_keys)
    assert all(item.parent_idempotency_key == "optimizer-parent:test" for item in first_run)
    assert tuple(item["idempotency_key"] for item in first_contexts) == first_keys
    assert all(item["parent_idempotency_key"] == "optimizer-parent:test" for item in first_contexts)


def test_execute_action_derives_a_child_key_from_a_parent_key() -> None:
    optimizer = SystemOptimizer(SH3Kernel())
    observed: list[dict[str, object]] = []
    optimizer.register_action(
        OptimizationAction(
            "single",
            lambda context: observed.append(dict(context)) or {"changed": False},
            lambda _: None,
        )
    )

    result = optimizer.execute_action("single", {"idempotency_key": "optimizer-parent:single"})

    assert result.idempotency_key == observed[0]["idempotency_key"]
    assert result.parent_idempotency_key == "optimizer-parent:single"
    assert result.idempotency_key != result.parent_idempotency_key
