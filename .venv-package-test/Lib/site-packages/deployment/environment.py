from __future__ import annotations

import os
from pathlib import Path

from foundation.utils.exceptions import ValidationException

from .models import DeploymentEnvironment

__all__ = ["FileEnvironmentManager"]


class FileEnvironmentManager:
    __slots__ = ("root",)

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def prepare(self, environment: DeploymentEnvironment) -> str:
        if not isinstance(environment, DeploymentEnvironment):
            raise TypeError("environment must be a DeploymentEnvironment")
        target = self.root / environment.value
        for name in ("config", "logs", "cache", "storage"):
            (target / name).mkdir(parents=True, exist_ok=True)
        return str(target)

    def validate(self, environment: DeploymentEnvironment) -> None:
        target = self.root / environment.value
        if not target.is_dir():
            raise ValidationException(
                f"Deployment environment is not prepared: {environment.value}"
            )
        required = ("config", "logs", "cache", "storage")
        missing = [name for name in required if not (target / name).is_dir()]
        if missing:
            raise ValidationException(
                f"Deployment environment is incomplete: {', '.join(missing)}"
            )

        if environment == DeploymentEnvironment.PRODUCTION:
            self._validate_production()

    @staticmethod
    def _validate_production() -> None:
        if os.environ.get("SH3_ALLOW_PRODUCTION") != "1":
            raise ValidationException(
                "Production deployment requires SH3_ALLOW_PRODUCTION=1"
            )
