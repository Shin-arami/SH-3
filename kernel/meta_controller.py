# kernel/meta_controller.py

from __future__ import annotations

from typing import Any

from cognition.policy import PolicyEngine, default_policy
from foundation.utils.hash import short_id
from foundation.utils.logging import info
from kernel.core import SH3Kernel
from self_healing.core import SelfHealingCore

# ----------------------------
# Meta Controller
# ----------------------------


class MetaController:
    def __init__(self, kernel: SH3Kernel):
        self.kernel = kernel
        self.healer = SelfHealingCore()
        self.policy_engine: PolicyEngine = kernel.policy

        self.meta_id = short_id("meta-controller")

    # ----------------------------
    # System Observation
    # ----------------------------

    def observe(self) -> dict[str, Any]:
        snapshot = {
            "kernel": self.kernel.context_manager.snapshot(),
            "memory": self.kernel.memory.snapshot(),
            "policy_rules": len(self.policy_engine.rules),
        }
        info("Meta observation completed", snapshot)
        return snapshot

    # ----------------------------
    # Health Evaluation
    # ----------------------------

    def evaluate_health(self, snapshot: dict[str, Any]) -> dict[str, float]:

        context_depth = snapshot["kernel"]["depth"]
        memory_size = snapshot["memory"]["timeline_length"]
        policy_count = snapshot["policy_rules"]

        score = {
            "context_health": max(0.0, 1.0 - context_depth * 0.1),
            "memory_health": min(1.0, memory_size / 50),
            "policy_health": min(1.0, policy_count / 10),
        }

        info("System health evaluated", score)
        return score

    # ----------------------------
    # Decision Logic
    # ----------------------------

    def decide_action(self, health: dict[str, float]) -> str:

        avg = sum(health.values()) / len(health)

        if avg < 0.3:
            return "rebuild"
        elif avg < 0.6:
            return "heal"
        elif avg < 0.8:
            return "optimize"
        else:
            return "stable"

    # ----------------------------
    # Policy Tuning
    # ----------------------------

    def tune_policy(self, snapshot: dict[str, Any]) -> None:

        if len(self.policy_engine.rules) < 3:
            new_policy = default_policy()
            self.policy_engine.rules = new_policy.rules

            info("Policy auto-tuned", {"rules": len(new_policy.rules)})

    # ----------------------------
    # Trigger Engine
    # ----------------------------

    def trigger(self, action: str, snapshot: dict[str, Any]) -> Any:

        if action == "heal":
            return self.healer.execute_safe(lambda: "heal_triggered")

        if action == "rebuild":
            self.kernel.context_manager.clear()
            return {"status": "kernel_rebuilt"}

        if action == "optimize":
            self.tune_policy(snapshot)
            return {"status": "optimized"}

        return {"status": "stable"}

    # ----------------------------
    # Full Meta Cycle
    # ----------------------------

    def run_cycle(self) -> dict[str, Any]:

        snapshot = self.observe()
        health = self.evaluate_health(snapshot)
        action = self.decide_action(health)
        result = self.trigger(action, snapshot)

        return {
            "meta_id": self.meta_id,
            "snapshot": snapshot,
            "health": health,
            "action": action,
            "result": result,
        }
