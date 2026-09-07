from __future__ import annotations

from pathlib import Path
from threading import RLock

from foundation.utils.exceptions import ValidationException

from .models import DeploymentManifest

__all__ = [
    "FileInstaller",
    "FileRollbackManager",
    "FileUpgradeManager",
]


class FileInstaller:
    __slots__ = ("_lock",)

    def __init__(self) -> None:
        self._lock = RLock()

    def install(self, manifest: DeploymentManifest, target: str) -> None:
        with self._lock:
            source = Path(manifest.source).expanduser().resolve()
            destination = Path(target).resolve()
            if not source.exists():
                raise ValidationException(f"Source does not exist: {source}")
            destination.mkdir(parents=True, exist_ok=True)

            marker = destination / "installed.json"
            marker.write_text(
                _manifest_json(manifest),
                encoding="utf-8",
            )


class FileUpgradeManager:
    __slots__ = ("_installer", "_lock")

    def __init__(self, installer: FileInstaller | None = None) -> None:
        self._installer = installer or FileInstaller()
        self._lock = RLock()

    def upgrade(
        self,
        manifest: DeploymentManifest,
        target: str,
        previous: DeploymentManifest | None,
    ) -> None:
        with self._lock:
            self._installer.install(manifest, target)
            marker = Path(target) / "previous-version.txt"
            marker.write_text(
                previous.version if previous is not None else "",
                encoding="utf-8",
            )


class FileRollbackManager:
    __slots__ = ("_lock",)

    def __init__(self) -> None:
        self._lock = RLock()

    def rollback(
        self,
        target: str,
        previous: DeploymentManifest,
    ) -> None:
        with self._lock:
            destination = Path(target).resolve()
            if not destination.is_dir():
                raise ValidationException(
                    f"Deployment target does not exist: {destination}"
                )
            (destination / "rollback.json").write_text(
                _manifest_json(previous),
                encoding="utf-8",
            )


def _manifest_json(manifest: DeploymentManifest) -> str:
    import json

    return json.dumps(
        manifest.to_dict(),
        ensure_ascii=False,
        indent=2,
    )
