from __future__ import annotations

import hashlib
import json
from pathlib import Path

from foundation.utils.exceptions import ValidationException

from .models import DeploymentManifest

__all__ = ["FilePackageManager"]


class FilePackageManager:
    __slots__ = ("root",)

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def validate(self, manifest: DeploymentManifest) -> None:
        source = Path(manifest.source).expanduser()
        if not source.exists():
            raise ValidationException(
                f"Deployment package does not exist: {source}"
            )
        if not source.is_file() and not source.is_dir():
            raise ValidationException(
                f"Deployment package is not deployable: {source}"
            )

        expected_hash = manifest.metadata.get("sha256")
        if expected_hash is not None:
            if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                raise ValidationException("metadata.sha256 must be a SHA-256 digest")
            actual = self._sha256(source)
            if actual != expected_hash.lower():
                raise ValidationException("Deployment package checksum mismatch")

    def prepare(self, manifest: DeploymentManifest) -> str:
        self.validate(manifest)
        target = self.root / f"{manifest.name}-{manifest.version}"
        target.mkdir(parents=True, exist_ok=True)
        metadata = target / "deployment.json"
        metadata.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(target)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        if path.is_file():
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            relative = child.relative_to(path).as_posix().encode("utf-8")
            digest.update(relative)
            digest.update(b"\0")
            with child.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        return digest.hexdigest()
