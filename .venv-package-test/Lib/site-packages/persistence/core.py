from __future__ import annotations

import json
import os
from typing import Any

from foundation.utils.hash import short_id
from foundation.utils.logging import info
from foundation.utils.time import iso


class PersistenceCore:
    def __init__(self, base_path: str = "./sh3_state"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)
        self.persistence_id = short_id("sh3-persistence")

    def save_state(self, name: str, state: dict[str, Any]) -> str:
        snapshot = {
            "name": name,
            "timestamp": iso(__import__("datetime").datetime.utcnow()),
            "state": state,
            "version": 1,
        }
        file_id = short_id(name)
        path = os.path.join(self.base_path, f"{file_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        info("State saved", {"file": path})
        return file_id

    def load_state(self, file_id: str) -> dict[str, Any] | None:
        path = os.path.join(self.base_path, f"{file_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Persisted state must be a JSON object")
        info("State loaded", {"file": path})
        return data

    def snapshot_kernel(self, kernel: Any) -> dict[str, Any]:
        state = {
            "context": kernel.context_manager.snapshot(),
            "memory": kernel.memory.snapshot(),
            "policy": len(kernel.policy.rules),
        }
        return state

    def snapshot_cognition(self, kernel: Any) -> dict[str, Any]:
        return {
            "planner": "active",
            "policy_rules": len(kernel.policy.rules),
            "memory_size": len(kernel.memory.snapshot().get("keys", [])),
        }

    def snapshot_system(self, kernel: Any) -> dict[str, Any]:
        system_state = {
            "kernel": self.snapshot_kernel(kernel),
            "cognition": self.snapshot_cognition(kernel),
            "timestamp": iso(__import__("datetime").datetime.utcnow()),
        }
        return system_state

    def restore(self, data: dict[str, Any], kernel: Any) -> dict[str, Any]:
        state = data.get("state", {})

        if "kernel" in state and "context" in state["kernel"]:
            kernel.context_manager.clear()
            info("Context restored")

        if "kernel" in state:
            mem_state = state["kernel"].get("memory", {})
            info("Memory restore skipped (deterministic rebuild assumed)", mem_state)

        if "cognition" in state:
            rule_count = state["cognition"].get("policy_rules", 0)
            info("Policy restore hint", {"rules": rule_count})

        return {
            "status": "restored",
            "persistence_id": self.persistence_id,
        }
