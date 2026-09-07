from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from foundation.utils.hash import short_id
from foundation.utils.logging import info
from foundation.utils.time import iso

__all__ = ["Planner", "StrategyNode"]


class StrategyNode:
    """Deterministic planning tree node."""

    __slots__ = ("children", "depth", "name", "trace_id")

    def __init__(self, name: str, depth: int = 0) -> None:
        if not isinstance(name, str):
            raise TypeError("name must be str")
        if isinstance(depth, bool) or not isinstance(depth, int):
            raise TypeError("depth must be int")
        if depth < 0:
            raise ValueError("depth must be >= 0")
        self.name = name
        self.depth = depth
        self.children: list[StrategyNode] = []
        self.trace_id = short_id(name)

    def add_child(self, node: StrategyNode) -> None:
        if not isinstance(node, StrategyNode):
            raise TypeError("node must be StrategyNode")
        self.children.append(node)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "depth": self.depth,
            "trace_id": self.trace_id,
            "children": [child.to_dict() for child in self.children],
        }


class Planner:
    """SH-3 deterministic planning engine."""

    __slots__ = ("_chunk_size", "_lock")

    def __init__(self, chunk_size: int = 2) -> None:
        self._lock = RLock()
        self._chunk_size = 2
        self.set_chunk_size(chunk_size)

    @property
    def chunk_size(self) -> int:
        with self._lock:
            return self._chunk_size

    def set_chunk_size(self, chunk_size: int) -> None:
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
            raise TypeError("chunk_size must be int")
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        with self._lock:
            self._chunk_size = chunk_size
        info("Planner chunk size updated", {"chunk_size": chunk_size})

    @staticmethod
    def _validate_goal(goal: str) -> str:
        if not isinstance(goal, str):
            raise TypeError("goal must be str")
        if not goal.strip():
            raise ValueError("goal must not be empty")
        return goal

    @staticmethod
    def _validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(plan, dict):
            raise TypeError("plan must be dict")
        tree = plan.get("tree")
        if not isinstance(tree, dict):
            raise ValueError("plan must contain a tree dictionary")
        if not isinstance(tree.get("name"), str):
            raise ValueError("plan tree must contain a name")
        children = tree.get("children", [])
        if not isinstance(children, list):
            raise ValueError("plan tree children must be list")
        return plan

    def build_plan(self, goal: str) -> dict[str, Any]:
        goal = self._validate_goal(goal)

        with self._lock:
            root = StrategyNode(goal, depth=0)
            steps = self._decompose(goal, self._chunk_size)

        for step in steps:
            node = StrategyNode(step, depth=1)
            substeps = self._decompose(step, self._chunk_size)
            for substep in substeps:
                node.add_child(StrategyNode(substep, depth=2))
            root.add_child(node)

        plan = {
            "goal": goal,
            "tree": root.to_dict(),
            "created_at": iso(__import__("datetime").datetime.utcnow()),
            "trace_id": root.trace_id,
        }

        info(
            "Plan built",
            {
                "goal": goal,
                "trace_id": root.trace_id,
                "steps": len(steps),
            },
        )
        return plan

    @staticmethod
    def _decompose(text: str, chunk_size: int) -> list[str]:
        words = text.split()
        if not words:
            return []

        chunks: list[str] = []
        buffer: list[str] = []

        for word in words:
            buffer.append(word)
            if len(buffer) >= chunk_size:
                chunks.append(" ".join(buffer))
                buffer = []

        if buffer:
            chunks.append(" ".join(buffer))

        return chunks

    def score(self, node: StrategyNode) -> float:
        if not isinstance(node, StrategyNode):
            raise TypeError("node must be StrategyNode")

        base = len(node.name) % 7
        depth_penalty = node.depth * 0.1
        score = max(0.0, (base / 10.0) - depth_penalty)
        return round(score, 3)

    def flatten(self, node: StrategyNode) -> list[str]:
        if not isinstance(node, StrategyNode):
            raise TypeError("node must be StrategyNode")

        result = [node.name]
        for child in node.children:
            result.extend(self.flatten(child))
        return result

    @staticmethod
    def _prune_tree(tree: dict[str, Any]) -> dict[str, Any]:
        name = tree.get("name")
        depth = tree.get("depth", 0)
        trace_id = tree.get("trace_id", short_id(str(name)))

        children = tree.get("children", [])
        if not isinstance(children, list):
            raise ValueError("tree children must be list")

        retained: list[dict[str, Any]] = []

        for child in children:
            if not isinstance(child, dict):
                raise ValueError("tree child must be dict")

            child_name = child.get("name")
            if not isinstance(child_name, str):
                raise ValueError("tree child name must be str")

            if not child_name.strip():
                continue

            retained.append(Planner._prune_tree(child))

        return {
            "name": name,
            "depth": depth,
            "trace_id": trace_id,
            "children": retained,
        }

    def optimize(self, plan: dict[str, Any]) -> dict[str, Any]:
        self._validate_plan(plan)

        optimized = deepcopy(plan)
        original_tree = optimized["tree"]
        optimized["tree"] = self._prune_tree(original_tree)
        optimized["optimized"] = True

        original_children = len(original_tree.get("children", []))
        optimized_children = len(optimized["tree"].get("children", []))

        info(
            "Plan optimized",
            {
                "trace_id": optimized.get("trace_id"),
                "original_children": original_children,
                "optimized_children": optimized_children,
            },
        )
        return optimized
