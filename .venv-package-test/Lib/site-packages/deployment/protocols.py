from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .models import DeploymentEnvironment, DeploymentManifest

__all__ = [
    "DeploymentEventSink",
    "DeploymentVerifier",
    "EnvironmentManagerProtocol",
    "InstallerProtocol",
    "PackageManagerProtocol",
    "RollbackManagerProtocol",
    "UpgradeManagerProtocol",
]


@runtime_checkable
class DeploymentEventSink(Protocol):
    def __call__(self, name: str, payload: dict[str, Any]) -> None: ...


@runtime_checkable
class PackageManagerProtocol(Protocol):
    def validate(self, manifest: DeploymentManifest) -> None: ...

    def prepare(self, manifest: DeploymentManifest) -> str: ...


@runtime_checkable
class EnvironmentManagerProtocol(Protocol):
    def prepare(self, environment: DeploymentEnvironment) -> str: ...

    def validate(self, environment: DeploymentEnvironment) -> None: ...


@runtime_checkable
class InstallerProtocol(Protocol):
    def install(self, manifest: DeploymentManifest, target: str) -> None: ...


@runtime_checkable
class UpgradeManagerProtocol(Protocol):
    def upgrade(
        self,
        manifest: DeploymentManifest,
        target: str,
        previous: DeploymentManifest | None,
    ) -> None: ...


@runtime_checkable
class RollbackManagerProtocol(Protocol):
    def rollback(
        self,
        target: str,
        previous: DeploymentManifest,
    ) -> None: ...


@runtime_checkable
class DeploymentVerifier(Protocol):
    def verify(
        self,
        manifest: DeploymentManifest,
        target: str,
    ) -> bool: ...
