from __future__ import annotations

from kernel import SH3Kernel
from kernel.system_optimizer import SystemOptimizer


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
