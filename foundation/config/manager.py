"""
SH-3 Complete Edition v1.0
Foundation Layer
Configuration Subsystem

manager.py

Kernel configuration manager.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .limits import MAX_PACKET_DEPTH, MAX_RETRY, MAX_TIMEOUT
from .settings import KernelSettings

__all__ = [
    "SettingsManager",
    "settings_manager",
]


class SettingsManager:
    """
    Kernel runtime configuration manager.

    Responsible for:
        - Loading
        - Saving
        - Validation
        - Runtime Updates
        - Reset
    """

    def __init__(
        self,
        settings: KernelSettings | None = None,
    ) -> None:
        self._settings = settings or KernelSettings()

    @property
    def settings(self) -> KernelSettings:
        return self._settings

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        return getattr(self._settings, key, default)

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:
        if not hasattr(self._settings, key):
            raise AttributeError(f"Unknown setting: {key}")
        setattr(self._settings, key, value)

    def update(
        self,
        **kwargs: Any,
    ) -> None:
        for key, value in kwargs.items():
            self.set(key, value)

    def validate(self) -> None:
        s = self._settings
        if s.timeout < 0:
            raise ValueError("timeout must be >= 0")
        if s.timeout > MAX_TIMEOUT:
            raise ValueError("timeout exceeds MAX_TIMEOUT")
        if s.retry < 0:
            raise ValueError("retry must be >= 0")
        if s.retry > MAX_RETRY:
            raise ValueError("retry exceeds MAX_RETRY")
        if s.max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        if s.max_depth > MAX_PACKET_DEPTH:
            raise ValueError("max_depth exceeds limit")

    def to_dict(self) -> dict[str, Any]:
        return self._settings.to_dict()

    def from_dict(
        self,
        data: dict[str, Any],
    ) -> KernelSettings:
        self._settings = KernelSettings.from_dict(data)
        self.validate()
        return self._settings

    def load_json(
        self,
        path: str | Path,
    ) -> KernelSettings:
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return self.from_dict(data)

    def save_json(
        self,
        path: str | Path,
    ) -> None:
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                self.to_dict(),
                f,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )

    def copy(self) -> KernelSettings:
        return deepcopy(self._settings)

    def reset(self) -> KernelSettings:
        self._settings = KernelSettings()
        return self._settings

    def enable_feature(
        self,
        name: str,
    ) -> None:
        self._settings.enable(name)

    def disable_feature(
        self,
        name: str,
    ) -> None:
        self._settings.disable(name)

    def feature_enabled(
        self,
        name: str,
    ) -> bool:
        return self._settings.get_feature(name)

settings_manager = SettingsManager()
