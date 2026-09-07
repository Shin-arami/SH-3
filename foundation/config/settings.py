"""
SH-3 Complete Edition v1.0
Foundation Layer
Configuration Subsystem

settings.py

Kernel runtime settings.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .defaults import (
    DEFAULT_CACHE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_DEPTH,
    DEFAULT_PACKET_RETRY,
    DEFAULT_SERIALIZER,
    DEFAULT_TIMEOUT,
    DEFAULT_VALIDATION,
)
from .features import DEFAULT_FEATURES

__all__ = [
    "KernelSettings",
]

_EMPTY: Mapping[str, Any] = MappingProxyType({})


@dataclass(slots=True)
class KernelSettings:
    """
    Mutable runtime configuration.

    This class stores all runtime-configurable options.
    Hard limits are enforced by config.limits.
    """

    debug: bool = False
    development: bool = False
    testing: bool = False

    enabled: bool = True
    timeout: float = DEFAULT_TIMEOUT
    retry: int = DEFAULT_PACKET_RETRY
    max_depth: int = DEFAULT_MAX_DEPTH

    serializer: str = DEFAULT_SERIALIZER

    validation: bool = DEFAULT_VALIDATION

    cache: bool = DEFAULT_CACHE

    log_level: str = DEFAULT_LOG_LEVEL

    features: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_FEATURES))

    metadata: dict[str, Any] = field(default_factory=dict)

    def get_feature(self, name: str) -> bool:
        return self.features.get(name, False)

    def enable(self, name: str) -> None:
        self.features[name] = True

    def disable(self, name: str) -> None:
        self.features[name] = False

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def copy(self) -> KernelSettings:
        return KernelSettings(
            debug=self.debug,
            development=self.development,
            testing=self.testing,
            enabled=self.enabled,
            timeout=self.timeout,
            retry=self.retry,
            max_depth=self.max_depth,
            serializer=self.serializer,
            validation=self.validation,
            cache=self.cache,
            log_level=self.log_level,
            features=self.features.copy(),
            metadata=self.metadata.copy(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "debug": self.debug,
            "development": self.development,
            "testing": self.testing,
            "enabled": self.enabled,
            "timeout": self.timeout,
            "retry": self.retry,
            "max_depth": self.max_depth,
            "serializer": self.serializer,
            "validation": self.validation,
            "cache": self.cache,
            "log_level": self.log_level,
            "features": self.features.copy(),
            "metadata": self.metadata.copy(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KernelSettings:
        settings = cls()
        settings.update(**data)
        return settings
