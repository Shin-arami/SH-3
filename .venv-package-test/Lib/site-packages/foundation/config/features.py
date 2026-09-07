"""
SH-3 Complete Edition v1.0
Foundation Layer
Configuration Subsystem

features.py

Kernel feature flags.

Feature flags describe capabilities supported by the kernel.
Runtime may enable/disable features through KernelSettings,
but feature names remain stable as part of the public API.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

__all__ = [
    # Collections
    "DEFAULT_FEATURES",
    "FEATURE_ASYNC",
    "FEATURE_BINARY",
    "FEATURE_CACHE",
    "FEATURE_COMPONENT",
    # Foundation
    "FEATURE_CONFIG",
    "FEATURE_DISTRIBUTED",
    "FEATURE_ENTITY",
    "FEATURE_ENUMS",
    "FEATURE_EVENTBUS",
    "FEATURE_EXECUTION",
    "FEATURE_FACTORY",
    # Serialization
    "FEATURE_JSON",
    "FEATURE_LEARNING",
    "FEATURE_LIFECYCLE",
    "FEATURE_LOGGING",
    # Cognition
    "FEATURE_MEMORY",
    "FEATURE_MIGRATION",
    "FEATURE_MULTIPROCESS",
    # Base
    "FEATURE_NODE",
    "FEATURE_PACKET",
    "FEATURE_PIPELINE",
    "FEATURE_PLANNING",
    # Extension
    "FEATURE_PLUGIN",
    "FEATURE_REASONING",
    "FEATURE_REFLECTION",
    # Runtime
    "FEATURE_RUNTIME",
    "FEATURE_SCHEDULER",
    "FEATURE_SCHEMA",
    # Services
    "FEATURE_SERIALIZER",
    "FEATURE_STREAMING",
    "FEATURE_TRANSPORT",
    "FEATURE_TYPES",
    "FEATURE_UTILS",
    # Security
    "FEATURE_VALIDATION",
    "FEATURE_VALIDATOR",
    "FEATURE_WORLD_MODEL",
]

# ==========================================================
# Foundation
# ==========================================================

FEATURE_CONFIG: Final[str] = "config"
FEATURE_TYPES: Final[str] = "types"
FEATURE_ENUMS: Final[str] = "enums"
FEATURE_UTILS: Final[str] = "utils"
FEATURE_LOGGING: Final[str] = "logging"

# ==========================================================
# Base
# ==========================================================

FEATURE_NODE: Final[str] = "node"
FEATURE_COMPONENT: Final[str] = "component"
FEATURE_ENTITY: Final[str] = "entity"
FEATURE_PACKET: Final[str] = "packet"
FEATURE_TRANSPORT: Final[str] = "transport"

# ==========================================================
# Services
# ==========================================================

FEATURE_SERIALIZER: Final[str] = "serializer"
FEATURE_VALIDATOR: Final[str] = "validator"
FEATURE_FACTORY: Final[str] = "factory"
FEATURE_MIGRATION: Final[str] = "migration"
FEATURE_CACHE: Final[str] = "cache"
FEATURE_EVENTBUS: Final[str] = "eventbus"

# ==========================================================
# Runtime
# ==========================================================

FEATURE_RUNTIME: Final[str] = "runtime"
FEATURE_SCHEDULER: Final[str] = "scheduler"
FEATURE_PIPELINE: Final[str] = "pipeline"
FEATURE_EXECUTION: Final[str] = "execution"
FEATURE_LIFECYCLE: Final[str] = "lifecycle"

# ==========================================================
# Cognition
# ==========================================================

FEATURE_MEMORY: Final[str] = "memory"
FEATURE_PLANNING: Final[str] = "planning"
FEATURE_REASONING: Final[str] = "reasoning"
FEATURE_WORLD_MODEL: Final[str] = "world_model"
FEATURE_LEARNING: Final[str] = "learning"
FEATURE_REFLECTION: Final[str] = "reflection"

# ==========================================================
# Extension
# ==========================================================

FEATURE_PLUGIN: Final[str] = "plugin"
FEATURE_DISTRIBUTED: Final[str] = "distributed"
FEATURE_MULTIPROCESS: Final[str] = "multiprocess"
FEATURE_ASYNC: Final[str] = "async"
FEATURE_STREAMING: Final[str] = "streaming"

# ==========================================================
# Serialization
# ==========================================================

FEATURE_JSON: Final[str] = "json"
FEATURE_BINARY: Final[str] = "binary"

# ==========================================================
# Security
# ==========================================================

FEATURE_VALIDATION: Final[str] = "validation"
FEATURE_SCHEMA: Final[str] = "schema"

# ==========================================================
# Default Feature Set
# ==========================================================

_DEFAULT_FEATURES = {
    FEATURE_CONFIG: True,
    FEATURE_TYPES: True,
    FEATURE_ENUMS: True,
    FEATURE_UTILS: True,
    FEATURE_LOGGING: True,
    FEATURE_NODE: True,
    FEATURE_COMPONENT: True,
    FEATURE_ENTITY: True,
    FEATURE_PACKET: True,
    FEATURE_TRANSPORT: True,
    FEATURE_SERIALIZER: True,
    FEATURE_VALIDATOR: True,
    FEATURE_FACTORY: True,
    FEATURE_MIGRATION: True,
    FEATURE_CACHE: True,
    FEATURE_EVENTBUS: True,
    FEATURE_RUNTIME: True,
    FEATURE_SCHEDULER: True,
    FEATURE_PIPELINE: True,
    FEATURE_EXECUTION: True,
    FEATURE_LIFECYCLE: True,
    FEATURE_MEMORY: True,
    FEATURE_PLANNING: True,
    FEATURE_REASONING: True,
    FEATURE_WORLD_MODEL: True,
    FEATURE_LEARNING: True,
    FEATURE_REFLECTION: True,
    FEATURE_PLUGIN: True,
    FEATURE_DISTRIBUTED: False,
    FEATURE_MULTIPROCESS: False,
    FEATURE_ASYNC: True,
    FEATURE_STREAMING: True,
    FEATURE_JSON: True,
    FEATURE_BINARY: False,
    FEATURE_VALIDATION: True,
    FEATURE_SCHEMA: True,
}

DEFAULT_FEATURES: Final[MappingProxyType[str, bool]] = MappingProxyType(_DEFAULT_FEATURES)

del _DEFAULT_FEATURES
