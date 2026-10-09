from __future__ import annotations

import re
from typing import Final

__all__ = [
    "COGNITION_CONTRACT_VERSION",
    "EVENT_SCHEMA_VERSION",
    "EVIDENCE_SCHEMA_VERSION",
    "PACKAGE_NAME",
    "PACKAGE_VERSION",
    "PRODUCT_EDITION",
    "is_semantic_version",
    "validate_semantic_version",
]

PACKAGE_NAME: Final[str] = "sh3"
PACKAGE_VERSION: Final[str] = "2.1.0"
PRODUCT_EDITION: Final[str] = "2.0"
COGNITION_CONTRACT_VERSION: Final[str] = "1.0.0"
EVENT_SCHEMA_VERSION: Final[str] = "1.0.0"
EVIDENCE_SCHEMA_VERSION: Final[str] = "1.0.0"
_SEMVER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")

def is_semantic_version(value: str) -> bool:
    return isinstance(value, str) and _SEMVER_PATTERN.fullmatch(value) is not None

def validate_semantic_version(value: str, *, field: str = "version") -> str:
    if not is_semantic_version(value):
        raise ValueError(f"{field} must be a semantic version: {value!r}")
    return value
