from __future__ import annotations

import json
import shutil
from pathlib import Path
from threading import RLock

from foundation.utils.exceptions import ValidationException

from .models import DeploymentManifest

__all__ = ["FileInstaller", "FileRollbackManager", "FileUpgradeManager"]


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
            app = destination / "app"
            staged = destination / ".staging"
            if staged.exists():
                shutil.rmtree(staged)
            staged.mkdir(parents=True)
            try:
                if source.is_dir():
                    shutil.copytree(source, staged / "app")
                else:
                    (staged / "app").mkdir()
                    shutil.copy2(source, staged / "app" / source.name)
                if app.exists():
                    shutil.rmtree(app)
                staged.joinpath("app").replace(app)
                (destination / "installed.json").write_text(
                    _manifest_json(manifest), encoding="utf-8"
                )
            finally:
                if staged.exists():
                    shutil.rmtree(staged)


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
            if previous is None:
                raise ValidationException("Previous deployment is required for upgrade")
            destination = Path(target).resolve()
            app = destination / "app"
            if not app.is_dir():
                raise ValidationException("Existing deployment is not installed")
            backup_root = destination / ".rollback"
            backup = backup_root / previous.version
            if backup.exists():
                shutil.rmtree(backup)
            backup_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(app, backup)
            (backup_root / f"{previous.version}.json").write_text(
                _manifest_json(previous), encoding="utf-8"
            )
            try:
                self._installer.install(manifest, str(destination))
            except Exception:
                if app.exists():
                    shutil.rmtree(app)
                shutil.copytree(backup, app)
                raise
            (destination / "previous-version.txt").write_text(
                previous.version, encoding="utf-8"
            )


class FileRollbackManager:
    __slots__ = ("_lock",)

    def __init__(self) -> None:
        self._lock = RLock()

    def rollback(self, target: str, previous: DeploymentManifest) -> None:
        with self._lock:
            destination = Path(target).resolve()
            if not destination.is_dir():
                raise ValidationException(f"Deployment target does not exist: {destination}")
            backup = destination / ".rollback" / previous.version
            if not backup.is_dir():
                raise ValidationException(
                    f"Rollback backup does not exist: {previous.version}"
                )
            app = destination / "app"
            restored = destination / ".restore"
            if restored.exists():
                shutil.rmtree(restored)
            shutil.copytree(backup, restored)
            try:
                if app.exists():
                    shutil.rmtree(app)
                restored.replace(app)
                (destination / "rollback.json").write_text(
                    _manifest_json(previous), encoding="utf-8"
                )
                (destination / "installed.json").write_text(
                    _manifest_json(previous), encoding="utf-8"
                )
            finally:
                if restored.exists():
                    shutil.rmtree(restored)


def _manifest_json(manifest: DeploymentManifest) -> str:
    return json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2)
