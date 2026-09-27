from __future__ import annotations

from pathlib import Path

from deployment import (
    DeploymentController,
    DeploymentEnvironment,
    DeploymentManifest,
    DeploymentState,
    FileEnvironmentManager,
    FileInstaller,
    FilePackageManager,
    FileRollbackManager,
    FileUpgradeManager,
)
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, PublishResult
from infrastructure.event_bus.router import EventSubscription
from infrastructure.events.catalog import CanonicalEventCatalog
from infrastructure.events.model import Event


class Verifier:
    def verify(self, manifest: DeploymentManifest, target: str) -> bool:
        return Path(target).is_dir() and manifest.version != ""


class FailingVerifier:
    def verify(self, manifest: DeploymentManifest, target: str) -> bool:
        return False


class FailingPublisher:
    def publish(self, event: Event) -> PublishResult:
        raise RuntimeError("event publication failed")


def _controller(
    tmp_path: Path,
    publisher: EventBusPublisher | FailingPublisher | None = None,
    verifier: Verifier | FailingVerifier | None = None,
) -> DeploymentController:
    return DeploymentController(
        FilePackageManager(tmp_path / "packages"),
        FileEnvironmentManager(tmp_path / "environments"),
        FileInstaller(),
        FileUpgradeManager(),
        FileRollbackManager(),
        verifier or Verifier(),
        event_publisher=publisher,
    )


def _subscribe(bus: EventBus, events: list[Event]) -> None:
    bus.subscribe(
        EventSubscription(
            subscriber_id="deployment-test",
            handler=events.append,
        )
    )


def test_deployment_event_lifecycle(tmp_path: Path) -> None:
    source = tmp_path / "package"
    source.mkdir()

    bus = EventBus()
    events: list[Event] = []
    _subscribe(bus, events)
    controller = _controller(tmp_path, EventBusPublisher(bus))

    manifest = DeploymentManifest(
        name="sh3",
        version="2.0.0",
        source=str(source),
        environment=DeploymentEnvironment.TESTING,
    )

    result = controller.deploy(manifest)

    assert result.success
    assert result.state == DeploymentState.ACTIVE
    assert [item.metadata.event_name for item in events] == [
        "DeploymentStarted",
        "DeploymentCompleted",
    ]

    started, completed = events

    assert started.metadata.producer == "deployment"
    assert started.metadata.event_version == "1.0.0"
    assert started.category.value == "component"
    assert started.event_type is EventType.START
    assert started.payload == {
        "deployment_id": result.deployment_id,
        "version": manifest.version,
    }

    assert completed.metadata.producer == "deployment"
    assert completed.category.value == "component"
    assert completed.event_type is EventType.COMPLETE
    assert completed.payload == {
        "deployment_id": result.deployment_id,
        "version": manifest.version,
        "success": True,
        "target": result.details["target"],
    }
    assert completed.metadata.causation_id == started.metadata.event_id
    assert completed.metadata.correlation_id == started.metadata.correlation_id

    catalog = CanonicalEventCatalog()
    catalog.validate(started)
    catalog.validate(completed)

    bus.close()


def test_deployment_failure_event_lifecycle(tmp_path: Path) -> None:
    source = tmp_path / "package"
    source.mkdir()

    bus = EventBus()
    events: list[Event] = []
    _subscribe(bus, events)
    controller = _controller(
        tmp_path,
        EventBusPublisher(bus),
        FailingVerifier(),
    )

    manifest = DeploymentManifest(
        name="sh3",
        version="2.0.0",
        source=str(source),
        environment=DeploymentEnvironment.TESTING,
    )

    result = controller.deploy(manifest)

    assert not result.success
    assert result.state == DeploymentState.FAILED
    assert [item.metadata.event_name for item in events] == [
        "DeploymentStarted",
        "DeploymentFailed",
    ]

    started, failed = events

    assert started.event_type is EventType.START
    assert failed.event_type is EventType.FAILURE
    assert failed.metadata.producer == "deployment"
    assert failed.category.value == "component"
    assert failed.metadata.causation_id == started.metadata.event_id
    assert failed.metadata.correlation_id == started.metadata.correlation_id
    assert failed.payload == {
        "deployment_id": result.deployment_id,
        "version": manifest.version,
        "error": result.message,
    }

    catalog = CanonicalEventCatalog()
    catalog.validate(started)
    catalog.validate(failed)

    bus.close()


def test_rollback_event_lifecycle(tmp_path: Path) -> None:
    source1 = tmp_path / "package1"
    source2 = tmp_path / "package2"
    source1.mkdir()
    source2.mkdir()
    (source1 / "main.py").write_text("v1", encoding="utf-8")
    (source2 / "main.py").write_text("v2", encoding="utf-8")

    bus = EventBus()
    events: list[Event] = []
    _subscribe(bus, events)
    controller = _controller(tmp_path, EventBusPublisher(bus))

    first = DeploymentManifest(
        name="sh3",
        version="1.0.0",
        source=str(source1),
        environment=DeploymentEnvironment.TESTING,
    )
    second = DeploymentManifest(
        name="sh3",
        version="2.0.0",
        source=str(source2),
        environment=DeploymentEnvironment.TESTING,
    )

    assert controller.deploy(first).success
    events.clear()

    assert controller.deploy(second, previous=first).success
    events.clear()

    result = controller.rollback()

    assert result.state == DeploymentState.ROLLED_BACK
    assert [item.metadata.event_name for item in events] == [
        "RollbackStarted",
        "RollbackCompleted",
    ]

    started, completed = events

    assert started.metadata.producer == "deployment"
    assert started.category.value == "component"
    assert started.event_type is EventType.START
    assert started.payload == {
        "deployment_id": result.deployment_id,
        "version": first.version,
    }

    assert completed.metadata.producer == "deployment"
    assert completed.category.value == "component"
    assert completed.event_type is EventType.COMPLETE
    assert completed.payload == {
        "deployment_id": result.deployment_id,
        "version": first.version,
        "success": True,
        "target": result.details["target"],
    }
    assert completed.metadata.causation_id == started.metadata.event_id
    assert completed.metadata.correlation_id == started.metadata.correlation_id

    catalog = CanonicalEventCatalog()
    catalog.validate(started)
    catalog.validate(completed)

    bus.close()


def test_event_publisher_failure_does_not_break_deployment(
    tmp_path: Path,
) -> None:
    source = tmp_path / "package"
    source.mkdir()

    controller = _controller(tmp_path, FailingPublisher())

    manifest = DeploymentManifest(
        name="sh3",
        version="2.0.0",
        source=str(source),
        environment=DeploymentEnvironment.TESTING,
    )

    result = controller.deploy(manifest)

    assert result.success
    assert result.state == DeploymentState.ACTIVE


def test_event_publisher_is_optional(tmp_path: Path) -> None:
    source = tmp_path / "package"
    source.mkdir()

    controller = _controller(tmp_path)

    manifest = DeploymentManifest(
        name="sh3",
        version="2.0.0",
        source=str(source),
        environment=DeploymentEnvironment.TESTING,
    )

    result = controller.deploy(manifest)

    assert result.success
    assert result.state == DeploymentState.ACTIVE
    assert controller.event_publisher is None


def test_event_bus_receives_deployment_events(tmp_path: Path) -> None:
    source = tmp_path / "package"
    source.mkdir()

    bus = EventBus()
    events: list[Event] = []
    _subscribe(bus, events)
    controller = _controller(tmp_path, EventBusPublisher(bus))

    manifest = DeploymentManifest(
        name="sh3",
        version="2.0.0",
        source=str(source),
        environment=DeploymentEnvironment.TESTING,
    )

    controller.deploy(manifest)

    snapshot = bus.snapshot()

    assert snapshot.published == 2
    assert snapshot.accepted == 2
    assert snapshot.delivered == 2
    assert snapshot.failed == 0
    assert snapshot.queue_size == 0
    assert len(events) == 2
    assert all(item.metadata.producer == "deployment" for item in events)

    bus.close()


def test_event_chain_preserves_correlation_and_causation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "package"
    source.mkdir()

    bus = EventBus()
    events: list[Event] = []
    _subscribe(bus, events)
    controller = _controller(tmp_path, EventBusPublisher(bus))

    manifest = DeploymentManifest(
        name="sh3",
        version="2.0.0",
        source=str(source),
        environment=DeploymentEnvironment.TESTING,
    )

    controller.deploy(manifest)

    started, completed = events

    assert started.metadata.correlation_id == started.payload["deployment_id"]
    assert completed.metadata.correlation_id == started.metadata.correlation_id
    assert completed.metadata.causation_id == started.metadata.event_id

    bus.close()
