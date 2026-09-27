from __future__ import annotations

from dataclasses import dataclass

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.exceptions import RuntimeException
from infrastructure.event_bus import PublishResult
from infrastructure.events.model import Event
from runtime.context_manager import RuntimeContext
from runtime.core import RuntimeCore


@dataclass
class RecordingPublisher:
    events: list[Event]

    def __init__(self) -> None:
        self.events = []

    def publish(self, event: Event) -> PublishResult:
        self.events.append(event)
        return PublishResult(
            event_id=event.id,
            accepted=True,
            queued=True,
            delivered=False,
        )


def test_run_publishes_started_and_completed() -> None:
    publisher = RecordingPublisher()
    runtime = RuntimeCore(event_publisher=publisher)

    assert runtime.run(lambda: 42) == 42

    assert [event.metadata.event_name for event in publisher.events] == [
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
    ]
    assert publisher.events[0].event_type == EventType.START
    assert publisher.events[1].event_type == EventType.COMPLETE
    assert publisher.events[0].category == Category.EXECUTION
    assert publisher.events[1].category == Category.EXECUTION
    assert publisher.events[0].payload["execution_id"]
    assert publisher.events[1].payload["execution_id"] == (
        publisher.events[0].payload["execution_id"]
    )


def test_run_publishes_failed() -> None:
    publisher = RecordingPublisher()
    runtime = RuntimeCore(event_publisher=publisher)

    with pytest.raises(RuntimeException):
        runtime.run(lambda: (_ for _ in ()).throw(ValueError("failure")))

    assert [event.metadata.event_name for event in publisher.events] == [
        "RuntimeExecutionStarted",
        "RuntimeExecutionFailed",
    ]
    assert publisher.events[1].payload["error"] == "failure"
    assert publisher.events[1].payload["success"] is False


def test_sh3_exception_publishes_failed_and_preserves_exception() -> None:
    from foundation.utils.exceptions import SH3Exception

    publisher = RecordingPublisher()
    runtime = RuntimeCore(event_publisher=publisher)

    class TestException(SH3Exception):
        pass

    with pytest.raises(TestException):
        runtime.run(lambda: (_ for _ in ()).throw(TestException("failure")))

    assert publisher.events[-1].metadata.event_name == "RuntimeExecutionFailed"


def test_pipe_publishes_started_and_completed() -> None:
    publisher = RecordingPublisher()
    runtime = RuntimeCore(event_publisher=publisher)

    assert runtime.pipe(1, lambda value: value + 1) == 2

    assert [event.metadata.event_name for event in publisher.events] == [
        "RuntimePipelineStarted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
        "RuntimePipelineCompleted",
    ]
    assert publisher.events[0].category == Category.PIPELINE
    assert publisher.events[-1].category == Category.PIPELINE
    assert publisher.events[0].payload["pipeline_id"]
    assert publisher.events[-1].payload["pipeline_id"] == (
        publisher.events[0].payload["pipeline_id"]
    )


def test_pipe_publishes_failed() -> None:
    publisher = RecordingPublisher()
    runtime = RuntimeCore(event_publisher=publisher)

    with pytest.raises(RuntimeException):
        runtime.pipe(
            1,
            lambda value: value + 1,
            lambda _: (_ for _ in ()).throw(ValueError("pipeline failure")),
        )

    names = [event.metadata.event_name for event in publisher.events]
    assert names == [
        "RuntimePipelineStarted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionCompleted",
        "RuntimeExecutionStarted",
        "RuntimeExecutionFailed",
        "RuntimePipelineFailed",
    ]
    assert publisher.events[-1].payload["error"] == "pipeline failure"


def test_custom_context_trace_id_is_published() -> None:
    publisher = RecordingPublisher()
    runtime = RuntimeCore(event_publisher=publisher)
    context = RuntimeContext("custom")

    assert runtime.run(lambda: 7, context=context) == 7

    assert publisher.events[0].payload["trace_id"] == context.trace_id
    assert publisher.events[1].payload["trace_id"] == context.trace_id


def test_publisher_failure_does_not_change_runtime_result() -> None:
    class FailingPublisher:
        def publish(self, event: Event) -> PublishResult:
            raise RuntimeError("publisher failure")

    runtime = RuntimeCore(event_publisher=FailingPublisher())

    assert runtime.run(lambda: 42) == 42


def test_publisher_can_be_updated() -> None:
    publisher = RecordingPublisher()
    runtime = RuntimeCore()

    runtime.set_event_publisher(publisher)
    assert runtime.event_publisher is publisher

    assert runtime.run(lambda: "ok") == "ok"
    assert len(publisher.events) == 2


def test_existing_runtime_api_remains_usable() -> None:
    runtime = RuntimeCore()

    assert runtime.run(lambda: 42) == 42
    assert runtime.pipe(1, lambda value: value + 1) == 2
