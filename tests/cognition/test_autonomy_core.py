from __future__ import annotations

from autonomy.core import AutonomyCore
from kernel import SH3Kernel


def test_generate_goal_uses_memory_snapshot() -> None:
    autonomy = AutonomyCore(SH3Kernel())

    assert autonomy.generate_goal() == "stabilize system memory"


def test_cycle_runs_the_integrated_autonomy_components() -> None:
    kernel = SH3Kernel()
    autonomy = AutonomyCore(kernel)

    result = autonomy.cycle()

    assert result["cycle"] == 1
    assert result["goal"] == "stabilize system memory"
    assert result["snapshot"]["memory"]["timeline_length"] == 0
    assert result["execution"]["goal"] == result["goal"]
    assert kernel.context_manager.snapshot()["depth"] == 0
