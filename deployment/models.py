from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

__all__ = [
    "DeploymentEnvironment",
    "DeploymentManifest",
    "DeploymentResult",
    "DeploymentState",
]


class DeploymentEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentState(StrEnum):
    CREATED = "created"
    VALIDATING = "validating"
    PREPARING = "preparing"
    INSTALLING = "installing"
    VERIFYING = "verifying"
    ACTIVE = "active"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True, slots=True)
class DeploymentManifest:
    name: str
    version: str
    source: str
    environment: DeploymentEnvironment = DeploymentEnvironment.DEVELOPMENT
    build_id: str = ""
    commit: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    release_date: datetime | None = None
    compatibility: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.version.strip():
            raise ValueError("version must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not isinstance(self.environment, DeploymentEnvironment):
            raise TypeError("environment must be a DeploymentEnvironment")
        if not all(isinstance(item, str) and item.strip() for item in self.dependencies):
            raise TypeError("dependencies must contain non-empty strings")
        if self.release_date is not None and (
            not isinstance(self.release_date, datetime) or self.release_date.tzinfo is None
        ):
            raise ValueError("release_date must be timezone-aware")
        if not isinstance(self.compatibility, str):
            raise TypeError("compatibility must be a string")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "environment": self.environment.value,
            "build_id": self.build_id,
            "commit": self.commit,
            "metadata": dict(self.metadata),
            "dependencies": list(self.dependencies),
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "compatibility": self.compatibility,
        }


@dataclass(frozen=True, slots=True)
class DeploymentResult:
    deployment_id: str
    state: DeploymentState
    manifest: DeploymentManifest
    started_at: datetime
    completed_at: datetime
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.started_at, datetime) or self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        if not isinstance(self.completed_at, datetime) or self.completed_at.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware")
        object.__setattr__(
            self,
            "details",
            MappingProxyType(dict(self.details)),
        )

    @property
    def success(self) -> bool:
        return self.state == DeploymentState.ACTIVE

    @property
    def duration_seconds(self) -> float:
        return max(
            0.0,
            (self.completed_at - self.started_at).total_seconds(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "state": self.state.value,
            "manifest": self.manifest.to_dict(),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "message": self.message,
            "details": dict(self.details),
            "success": self.success,
            "duration_seconds": self.duration_seconds,
        }


def now_utc() -> datetime:
    return datetime.now(UTC)
