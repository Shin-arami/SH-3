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


def test_install_copies_artifact_and_persists_release_metadata(tmp_path: Path) -> None:
    source = tmp_path / "package"
    source.mkdir()
    (source / "main.py").write_text("print('v1')", encoding="utf-8")
    controller = DeploymentController(
        FilePackageManager(tmp_path / "packages"),
        FileEnvironmentManager(tmp_path / "environments"),
        FileInstaller(),
        FileUpgradeManager(),
        FileRollbackManager(),
        Verifier(),
    )
    manifest = DeploymentManifest(
        name="sh3", version="2.1.0", source=str(source),
        environment=DeploymentEnvironment.STAGING,
        build_id="build-1", commit="abc123", compatibility="backward-compatible",
        dependencies=("python>=3.12",),
    )
    result = controller.deploy(manifest)
    target = Path(result.details["target"])
    assert (target / "app" / "main.py").read_text(encoding="utf-8") == "print('v1')"
    assert '"build_id": "build-1"' in (target / "installed.json").read_text(encoding="utf-8")


def test_upgrade_creates_backup_and_rollback_restores_previous_artifact(tmp_path: Path) -> None:
    source1 = tmp_path / "package1"
    source2 = tmp_path / "package2"
    source1.mkdir()
    source2.mkdir()
    (source1 / "main.py").write_text("v1", encoding="utf-8")
    (source2 / "main.py").write_text("v2", encoding="utf-8")
    controller = DeploymentController(
        FilePackageManager(tmp_path / "packages"),
        FileEnvironmentManager(tmp_path / "environments"),
        FileInstaller(),
        FileUpgradeManager(),
        FileRollbackManager(),
        Verifier(),
    )
    first = DeploymentManifest("sh3", "1.0.0", str(source1), DeploymentEnvironment.TESTING)
    second = DeploymentManifest("sh3", "2.0.0", str(source2), DeploymentEnvironment.TESTING)
    first_result = controller.deploy(first)
    target = Path(first_result.details["target"])
    assert controller.deploy(second, previous=first).success
    assert (target / "app" / "main.py").read_text(encoding="utf-8") == "v2"
    assert (target / ".rollback" / "1.0.0" / "main.py").read_text(encoding="utf-8") == "v1"
    assert controller.rollback().state == DeploymentState.ROLLED_BACK
    assert (target / "app" / "main.py").read_text(encoding="utf-8") == "v1"
