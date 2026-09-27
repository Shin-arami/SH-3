from __future__ import annotations

import tomllib

import pytest

from foundation.version import (
    EVENT_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    PRODUCT_EDITION,
    is_semantic_version,
    validate_semantic_version,
)
from infrastructure.events.model import Event
from infrastructure.events.registry import EventSchemaRegistry
from infrastructure.security import EvidenceRecord
from sh3dev import __version__


def test_package_version_is_canonical_and_semver() -> None:
    assert PACKAGE_NAME == "sh3"
    assert PACKAGE_VERSION == "2.1.0"
    assert __version__ == PACKAGE_VERSION
    assert is_semantic_version(PACKAGE_VERSION)


def test_pyproject_derives_package_version_from_canonical_source() -> None:
    with open("pyproject.toml", "rb") as handle:
        project = tomllib.load(handle)
    assert project["project"]["dynamic"] == ["version"]
    assert project["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "foundation.version.PACKAGE_VERSION"


def test_product_edition_is_distinct_from_package_version() -> None:
    assert PRODUCT_EDITION == "2.0"
    assert PRODUCT_EDITION != PACKAGE_VERSION


def test_contract_versions_are_canonical() -> None:
    event = Event.create(event_name="VersionGovernance", producer="test")
    assert event.version == EVENT_SCHEMA_VERSION
    registry = EventSchemaRegistry()
    assert registry._DEFAULT_VERSION == EVENT_SCHEMA_VERSION
    record = EvidenceRecord.create(evidence_id="ev-version", kind="test", source="test", subject_id="subject")
    assert record.version == EVIDENCE_SCHEMA_VERSION


def test_semver_validation_rejects_invalid_versions() -> None:
    for value in ("1", "1.0", "01.0.0", "v1.0.0", "1.0.0.0"):
        assert not is_semantic_version(value)
        with pytest.raises(ValueError):
            validate_semantic_version(value)
    assert validate_semantic_version("2.1.0") == "2.1.0"


def test_release_workflow_contains_version_gate() -> None:
    with open(".github/workflows/release.yml", encoding="utf-8") as handle:
        workflow = handle.read()
    assert "Validate release version" in workflow
    assert "PACKAGE_VERSION" in workflow
