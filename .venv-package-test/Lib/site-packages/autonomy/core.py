# autonomy/core.py

from __future__ import annotations

from typing import Any

from foundation.utils.hash import short_id
from foundation.utils.logging import info
from kernel.core import SH3Kernel
from kernel.learning_loop import LearningLoop
from kernel.meta_controller import MetaController
from kernel.system_optimizer import SystemOptimizer

# ----------------------------
# Autonomy Core
# ----------------------------


class AutonomyCore:
    def __init__(self, kernel: SH3Kernel):
        self.kernel = kernel

        self.meta = MetaController(kernel)
        self.optimizer = SystemOptimizer(kernel)
        self.learning = LearningLoop(kernel)

        self.autonomy_id = short_id("sh3-autonomy")

        self.active = False
        self.cycle_count = 0

    # ----------------------------
    # Goal Generation (deterministic)
    # ----------------------------

    def generate_goal(self) -> str:
        """
        Deterministic pseudo-goal generation
        based on system state.
        """

        snapshot = self.meta.observe()

        if snapshot["memory"]["timeline_length"] < 5:
            return "stabilize system memory"

        if snapshot["kernel"]["depth"] > 3:
            return "reduce context complexity"

        if snapshot["policy_rules"] < 3:
            return "strengthen decision policy"

        return "optimize system balance"

    # ----------------------------
    # Execution Cycle
    # ----------------------------

    def cycle(self) -> dict[str, Any]:

        goal = self.generate_goal()

        info("Autonomy cycle started", {"cycle": self.cycle_count, "goal": goal})

        # 1. Meta observation
        snapshot = self.meta.observe()

        # 2. Optimization pass
        optimization = self.optimizer.optimize()

        # 3. Kernel execution
        execution = self.kernel.execute(goal)

        # 4. Learning feedback
        learning = self.learning.run(execution)

        self.cycle_count += 1

        result = {
            "autonomy_id": self.autonomy_id,
            "cycle": self.cycle_count,
            "goal": goal,
            "snapshot": snapshot,
            "optimization": optimization,
            "execution": execution,
            "learning": learning,
        }

        info("Autonomy cycle completed", result)

        return result

    # ----------------------------
    # Continuous Loop Controller
    # ----------------------------

    def run(self, max_cycles: int = 10) -> list[dict[str, Any]]:

        self.active = True
        results = []

        info("Autonomy system activated", {"max_cycles": max_cycles})

        while self.active and self.cycle_count < max_cycles:
            result = self.cycle()
            results.append(result)

            # Stop condition (deterministic stability check)
            if result["learning"]["score"] > 0.95:
                info("Autonomy reached stable state")
                break

        self.active = False

        return results

    # ----------------------------
    # Stop Control
    # ----------------------------

    def stop(self) -> None:
        self.active = False
        info("Autonomy system stopped", {"cycle": self.cycle_count})
