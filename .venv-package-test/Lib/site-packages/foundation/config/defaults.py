"""
SH-3 Complete Edition v1.0
Foundation Layer
Configuration Subsystem

defaults.py

Runtime default values.
These values may be overridden by KernelSettings.
"""

from __future__ import annotations

from typing import Any, Final

__all__ = [
    "DEFAULT_ATTRIBUTES",
    # Cache
    "DEFAULT_CACHE",
    "DEFAULT_COMPONENT_ENABLED",
    # Component
    "DEFAULT_COMPONENT_TYPE",
    # Confidence
    "DEFAULT_CONFIDENCE",
    "DEFAULT_CONTENT",
    "DEFAULT_DESCRIPTION",
    "DEFAULT_ENCODING",
    "DEFAULT_ENTITY_STATE",
    # Entity
    "DEFAULT_ENTITY_TYPE",
    # Identity
    "DEFAULT_ID",
    "DEFAULT_LANGUAGE",
    # Logging
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_METADATA",
    # Generic
    "DEFAULT_NAME",
    "DEFAULT_NODE_STATUS",
    # Node
    "DEFAULT_NODE_TYPE",
    "DEFAULT_PACKET_PRIORITY",
    "DEFAULT_PACKET_RETRY",
    "DEFAULT_PACKET_TTL",
    # Packet
    "DEFAULT_PACKET_TYPE",
    "DEFAULT_PARENT_ID",
    # Message
    "DEFAULT_ROLE",
    "DEFAULT_ROOT_ID",
    "DEFAULT_SCORE",
    # Serialization
    "DEFAULT_SERIALIZER",
    # Metadata
    "DEFAULT_TAGS",
    # Runtime
    "DEFAULT_TIMEOUT",
    # Validation
    "DEFAULT_VALIDATION",
    "DEFAULT_VERSION",
    "DEFAULT_WEIGHT",
]

# ==========================================================
# Generic
# ==========================================================
DEFAULT_NAME: Final[str] = ""
DEFAULT_DESCRIPTION: Final[str] = ""
DEFAULT_VERSION: Final[str] = "1.0.0"
DEFAULT_LANGUAGE: Final[str] = "en"
DEFAULT_ENCODING: Final[str] = "utf-8"

# ==========================================================
# Identity
# ==========================================================
DEFAULT_ID: Final[str] = ""
DEFAULT_PARENT_ID: Final[str] = ""
DEFAULT_ROOT_ID: Final[str] = ""

# ==========================================================
# Node
# ==========================================================
DEFAULT_NODE_TYPE: Final[str] = "node"
DEFAULT_NODE_STATUS: Final[str] = "active"

# ==========================================================
# Entity
# ==========================================================
DEFAULT_ENTITY_TYPE: Final[str] = "entity"
DEFAULT_ENTITY_STATE: Final[str] = "ready"

# ==========================================================
# Component
# ==========================================================
DEFAULT_COMPONENT_TYPE: Final[str] = "component"
DEFAULT_COMPONENT_ENABLED: Final[bool] = True

# ==========================================================
# Packet
# ==========================================================
DEFAULT_PACKET_TYPE: Final[str] = "packet"
DEFAULT_PACKET_PRIORITY: Final[int] = 50
DEFAULT_PACKET_TTL: Final[int] = 3600
DEFAULT_PACKET_RETRY: Final[int] = 3

# ==========================================================
# Runtime
# ==========================================================
DEFAULT_TIMEOUT: Final[float] = 30.0
DEFAULT_MAX_DEPTH: Final[int] = 128

# ==========================================================
# Confidence
# ==========================================================
DEFAULT_CONFIDENCE: Final[float] = 1.0
DEFAULT_SCORE: Final[float] = 0.0
DEFAULT_WEIGHT: Final[float] = 1.0

# ==========================================================
# Metadata
# ==========================================================
DEFAULT_TAGS: Final[tuple[str, ...]] = ()
DEFAULT_ATTRIBUTES: Final[dict[str, Any]] = {}
DEFAULT_METADATA: Final[dict[str, Any]] = {}

# ==========================================================
# Message
# ==========================================================
DEFAULT_ROLE: Final[str] = "assistant"
DEFAULT_CONTENT: Final[str] = ""

# ==========================================================
# Serialization
# ==========================================================
DEFAULT_SERIALIZER: Final[str] = "json"

# ==========================================================
# Validation
# ==========================================================
DEFAULT_VALIDATION: Final[bool] = True

# ==========================================================
# Cache
# ==========================================================
DEFAULT_CACHE: Final[bool] = True

# ==========================================================
# Logging
# ==========================================================
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
