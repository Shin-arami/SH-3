from __future__ import annotations

from collections.abc import Mapping
from threading import RLock
from typing import Any

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.exceptions import SH3Exception, ValidationException
from foundation.utils.hash import short_id
from foundation.utils.logging import error, event, info
from infrastructure.event_bus import EventPublisher
from infrastructure.events.model import Event

from .models import (
    DeploymentManifest,
    DeploymentResult,
    DeploymentState,
    now_utc,
)
from .protocols import (
    DeploymentEventSink,
    DeploymentVerifier,
    EnvironmentManagerProtocol,
    InstallerProtocol,
    PackageManagerProtocol,
    RollbackManagerProtocol,
    UpgradeManagerProtocol,
)

__all__ = ["DeploymentController"]


class DeploymentController:
    __slots__ = (
        "_correlation_id",
        "_environment",
        "_event_publisher",
        "_events",
        "_installer",
        "_last_event_id",
        "_lock",
        "_package",
        "_previous",
        "_rollback",
        "_state",
        "_target",
        "_upgrade",
        "_verifier",
    )

    def __init__(
        self,
        package_manager: PackageManagerProtocol,
        environment_manager: EnvironmentManagerProtocol,
        installer: InstallerProtocol,
        upgrade_manager: UpgradeManagerProtocol,
        rollback_manager: RollbackManagerProtocol,
        verifier: DeploymentVerifier,
        event_sink: DeploymentEventSink | None = None,
        *,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._package = package_manager
        self._environment = environment_manager
        self._installer = installer
        self._upgrade = upgrade_manager
        self._rollback = rollback_manager
        self._verifier = verifier
        self._events = event_sink or event
        self._event_publisher = event_publisher
        self._correlation_id: str | None = None
        self._last_event_id: str | None = None
        self._lock = RLock()
        self._state = DeploymentState.CREATED
        self._target = ""
        self._previous: DeploymentManifest | None = None

    @property
    def state(self) -> DeploymentState:
        with self._lock:
            return self._state

    @property
    def target(self) -> str:
        with self._lock:
            return self._target

    @property
    def previous(self) -> DeploymentManifest | None:
        with self._lock:
            return self._previous

    @property
    def event_publisher(self) -> EventPublisher | None:
        with self._lock:
            return self._event_publisher

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        with self._lock:
            self._event_publisher = publisher

    def deploy(
        self,
        manifest: DeploymentManifest,
        previous: DeploymentManifest | None = None,
    ) -> DeploymentResult:
        started = now_utc()

        self._correlation_id = None
        self._last_event_id = None
        deployment_id = short_id(
            f"{manifest.name}:{manifest.version}:{started.isoformat()}"
        )

        with self._lock:
            if self._state in {
                DeploymentState.VALIDATING,
                DeploymentState.PREPARING,
                DeploymentState.INSTALLING,
                DeploymentState.VERIFYING,
                DeploymentState.ROLLING_BACK,
            }:
                raise ValidationException("Deployment is already in progress")
            self._previous = previous
            self._last_event_id = None

            self._publish(
                "DeploymentStarted",
                {
                    "deployment_id": deployment_id,
                    "version": manifest.version,
                },
                EventType.START,
                correlation_id=deployment_id,
            )

        try:
            self._set_state(DeploymentState.VALIDATING)
            self._package.validate(manifest)

            self._set_state(DeploymentState.PREPARING)
            target = self._environment.prepare(manifest.environment)
            self._environment.validate(manifest.environment)
            prepared = self._package.prepare(manifest)

            self._set_state(DeploymentState.INSTALLING)
            if previous is None:
                self._installer.install(manifest, target)
            else:
                self._upgrade.upgrade(manifest, target, previous)

            self._set_state(DeploymentState.VERIFYING)
            if not self._verifier.verify(manifest, target):
                raise ValidationException("Deployment verification failed")

            with self._lock:
                self._target = target
                self._state = DeploymentState.ACTIVE

            completed = now_utc()
            result = DeploymentResult(
                deployment_id=deployment_id,
                state=DeploymentState.ACTIVE,
                manifest=manifest,
                started_at=started,
                completed_at=completed,
                message="Deployment completed",
                details={"target": target, "prepared": prepared},
            )
            self._publish(
                "DeploymentCompleted",
                {
                    "deployment_id": deployment_id,
                    "version": manifest.version,
                    "success": True,
                    "target": target,
                },
                EventType.COMPLETE,
                correlation_id=deployment_id,
            )
            info("Deployment completed", result.to_dict())
            return result
        except SH3Exception as exc:
            return self._fail(
                deployment_id,
                manifest,
                started,
                exc,
            )
        except Exception as exc:
            wrapped = ValidationException(str(exc))
            return self._fail(
                deployment_id,
                manifest,
                started,
                wrapped,
                original=exc,
            )

    def rollback(self) -> DeploymentResult:
        with self._lock:
            previous = self._previous
            target = self._target
            self._last_event_id = None

        if previous is None:
            raise ValidationException("No previous deployment is available")
        if not target:
            raise ValidationException("No deployment target is available")

        started = now_utc()
        deployment_id = short_id(
            f"rollback:{previous.name}:{previous.version}:{started.isoformat()}"
        )
        self._set_state(DeploymentState.ROLLING_BACK)
        self._publish(
            "RollbackStarted",
            {
                "deployment_id": deployment_id,
                "version": previous.version,
            },
            EventType.START,
            correlation_id=deployment_id,
        )

        try:
            self._rollback.rollback(target, previous)
            if not self._verifier.verify(previous, target):
                raise ValidationException("Rollback verification failed")

            self._set_state(DeploymentState.ROLLED_BACK)
            completed = now_utc()
            result = DeploymentResult(
                deployment_id=deployment_id,
                state=DeploymentState.ROLLED_BACK,
                manifest=previous,
                started_at=started,
                completed_at=completed,
                message="Rollback completed",
                details={"target": target},
            )
            self._publish(
                "RollbackCompleted",
                {
                    "deployment_id": deployment_id,
                    "version": previous.version,
                    "success": True,
                    "target": target,
                },
                EventType.COMPLETE,
                correlation_id=deployment_id,
            )
            return result
        except Exception as exc:
            self._set_state(DeploymentState.FAILED)
            self._publish(
                "DeploymentFailed",
                {
                    "deployment_id": deployment_id,
                    "version": previous.version,
                    "error": str(exc),
                },
                EventType.FAILURE,
                correlation_id=deployment_id,
            )
            raise

    def _fail(
        self,
        deployment_id: str,
        manifest: DeploymentManifest,
        started: Any,
        exc: SH3Exception,
        original: Exception | None = None,
    ) -> DeploymentResult:
        self._set_state(DeploymentState.FAILED)
        completed = now_utc()
        details: dict[str, Any] = {"error_type": type(exc).__name__}
        if original is not None:
            details["original_type"] = type(original).__name__

        result = DeploymentResult(
            deployment_id=deployment_id,
            state=DeploymentState.FAILED,
            manifest=manifest,
            started_at=started,
            completed_at=completed,
            message=str(exc),
            details=details,
        )
        self._publish(
            "DeploymentFailed",
            {
                "deployment_id": result.deployment_id,
                "version": manifest.version,
                "error": result.message,
            },
            EventType.FAILURE,
            correlation_id=result.deployment_id,
        )
        error("Deployment failed", result.to_dict())
        return result

    def _set_state(self, state: DeploymentState) -> None:
        with self._lock:
            self._state = state

    def _publish(
        self,
        name: str,
        payload: Mapping[str, Any],
        event_type: EventType,
        *,
        correlation_id: str,
    ) -> None:
        self._events(name, dict(payload))
        if self._event_publisher is None:
            return
        try:
            event_context = Event.create(
                event_name=name,
                producer="deployment",
                payload=payload,
                category=Category.COMPONENT,
                event_type=event_type,
                correlation_id=correlation_id,
                causation_id=self._last_event_id,
            )
            self._event_publisher.publish(event_context)
            self._last_event_id = event_context.metadata.event_id
        except Exception as exc:
            error(
                "Deployment event publication failed",
                data={"event_name": name, "error": str(exc)},
            )
