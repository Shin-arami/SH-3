from __future__ import annotations

from typing import Any

import pytest

from cognition.policy import PolicyRule
from infrastructure.event_bus import PublishResult
from infrastructure.events.model import Event
from kernel import SH3Kernel
from kernel.learning_loop import LearningLoop


def test_run_collects_scores_and_stores_experience() -> None:
    kernel = SH3Kernel()
    kernel.add_policy(PolicyRule("always", score_fn=lambda _: 1.0))

    result = LearningLoop(kernel).run(kernel.execute("prepare release notes"))

    assert result["experience"] == {
        "goal": "prepare release notes",
        "decision": "always",
        "plan_size": 2,
        "success": True,
    }
    assert result["score"] == 0.7
    assert kernel.recall(result["memory_key"]) == {
        "experience": result["experience"],
        "score": 0.7,
    }


def test_low_score_weakens_policy_weights() -> None:
    kernel = SH3Kernel()
    rule = PolicyRule("always")
    kernel.add_policy(rule)

    result = LearningLoop(kernel).run({"goal": "", "plan": {"tree": {}}})

    assert result["score"] == 0.0
    assert rule.weight == pytest.approx(0.95)
    assert kernel.planner.chunk_size == 1


def test_high_score_uses_coarser_planner_decomposition() -> None:
    kernel = SH3Kernel()
    loop = LearningLoop(kernel)

    loop.tune_planner({}, 0.9)

    assert kernel.planner.chunk_size == 3


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def publish(self, event: Event) -> PublishResult:
        self.events.append(event)
        return PublishResult(
            event_id=event.metadata.event_id,
            accepted=True,
            queued=False,
            delivered=False,
            retry=None,
            dead_lettered=False,
            error=None,
        )


def test_run_publishes_learning_lifecycle_events() -> None:
    kernel = SH3Kernel()
    kernel.add_policy(PolicyRule("always", score_fn=lambda _: 1.0))
    publisher = RecordingPublisher()
    loop = LearningLoop(kernel, event_publisher=publisher)

    result = loop.run(kernel.execute("prepare release notes"))

    assert result["score"] == 0.7
    assert [
        event.metadata.event_name
        for event in publisher.events
    ] == [
        "LearningStarted",
        "LearningRecordCreated",
        "LearningResultRecorded",
        "LearningCompleted",
    ]
    assert all(
        event.metadata.producer == loop.loop_id
        for event in publisher.events
    )


def test_run_publishes_learning_failed_event(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = SH3Kernel()
    publisher = RecordingPublisher()
    loop = LearningLoop(kernel, event_publisher=publisher)

    def fail_store(
        self: LearningLoop,
        experience: dict[str, Any],
        score: float,
        *,
        idempotency_key: str | None = None,
    ) -> str:
        del idempotency_key
        raise TypeError("store failed")

    monkeypatch.setattr(LearningLoop, "store_experience", fail_store)

    with pytest.raises(TypeError, match="store failed"):
        loop.run({"goal": "test", "plan": {"tree": {"children": []}}})

    names = [event.metadata.event_name for event in publisher.events]
    assert "LearningStarted" in names
    assert "LearningFailed" in names


def test_run_without_event_publisher_preserves_behavior() -> None:
    kernel = SH3Kernel()
    kernel.add_policy(PolicyRule("always", score_fn=lambda _: 1.0))

    result = LearningLoop(kernel).run(
        kernel.execute("prepare release notes")
    )

    assert result["score"] == 0.7
