from __future__ import annotations

from pathlib import Path
from typing import Any

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
from foundation.utils.exceptions import ValidationException


class Verifier:
    def verify(self, manifest: DeploymentManifest, target: str) -> bool:
        return (
            Path(target).is_dir()
            and manifest.version != ""
        )


def test_deployment_controller_installs_package(tmp_path: Path) -> None:
    source = tmp_path / "package"
    source.mkdir()

    package_root = tmp_path / "packages"
    environment_root = tmp_path / "environments"

    controller = DeploymentController(
        FilePackageManager(package_root),
        FileEnvironmentManager(environment_root),
        FileInstaller(),
        FileUpgradeManager(),
        FileRollbackManager(),
        Verifier(),
    )

    manifest = DeploymentManifest(
        name="sh3",
        version="2.0.0",
        source=str(source),
        environment=DeploymentEnvironment.TESTING,
    )

    result = controller.deploy(manifest)

    assert result.success
    assert result.state == DeploymentState.ACTIVE
    assert controller.state == DeploymentState.ACTIVE
    assert Path(result.details["target"]).is_dir()


def test_deployment_controller_upgrade_and_rollback(tmp_path: Path) -> None:
    source = tmp_path / "package"
    source.mkdir()

    package_root = tmp_path / "packages"
    environment_root = tmp_path / "environments"

    controller = DeploymentController(
        FilePackageManager(package_root),
        FileEnvironmentManager(environment_root),
        FileInstaller(),
        FileUpgradeManager(),
        FileRollbackManager(),
        Verifier(),
    )

    first = DeploymentManifest(
        name="sh3",
        version="2.0.0",
        source=str(source),
        environment=DeploymentEnvironment.TESTING,
    )
    second = DeploymentManifest(
        name="sh3",
        version="2.1.0",
        source=str(source),
        environment=DeploymentEnvironment.TESTING,
    )

    assert controller.deploy(first).success
    assert controller.deploy(second, previous=first).success

    rollback = controller.rollback()

    assert rollback.state == DeploymentState.ROLLED_BACK
    assert rollback.manifest.version == first.version
    assert (Path(rollback.details["target"]) / "rollback.json").exists()


def test_production_requires_explicit_enable(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    source = tmp_path / "package"
    source.mkdir()

    environment_root = tmp_path / "environments"
    manager = FileEnvironmentManager(environment_root)
    manager.prepare(DeploymentEnvironment.PRODUCTION)

    monkeypatch.delenv("SH3_ALLOW_PRODUCTION", raising=False)

    import pytest

    with pytest.raises(ValidationException):
        manager.validate(DeploymentEnvironment.PRODUCTION)
