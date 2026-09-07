"""
SH-3 Complete Edition v1.0
Foundation Layer
Configuration Subsystem

limits.py

Kernel safety limits.

These limits define the maximum capability supported by the
kernel. Runtime settings may only reduce these values, never
exceed them.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "MAX_ATTRIBUTES",
    # Memory
    "MAX_CACHE_SIZE",
    # Entity
    "MAX_COMPONENTS",
    "MAX_DICT_SIZE",
    "MAX_ENTITY_RELATIONS",
    "MAX_GRAPH_EDGES",
    # Graph
    "MAX_GRAPH_NODES",
    "MAX_HISTORY_SIZE",
    # Identity
    "MAX_ID_LENGTH",
    # Serialization
    "MAX_JSON_DEPTH",
    # Collections
    "MAX_LIST_SIZE",
    "MAX_METADATA_SIZE",
    "MAX_NAME_LENGTH",
    "MAX_PACKET_CHILDREN",
    "MAX_PACKET_DEPTH",
    # Packet
    "MAX_PACKET_SIZE",
    # Queue
    "MAX_QUEUE_SIZE",
    # Runtime
    "MAX_RETRY",
    "MAX_SET_SIZE",
    # Metadata
    "MAX_TAGS",
    # String
    "MAX_TEXT_LENGTH",
    "MAX_TIMEOUT",
    "MAX_TTL",
    "MAX_VERSION_LENGTH",
]

# ==========================================================
# Identity
# ==========================================================

MAX_ID_LENGTH: Final[int] = 128
MAX_NAME_LENGTH: Final[int] = 256
MAX_VERSION_LENGTH: Final[int] = 32

# ==========================================================
# Packet
# ==========================================================

MAX_PACKET_SIZE: Final[int] = 16 * 1024 * 1024  # 16 MiB
MAX_PACKET_DEPTH: Final[int] = 128
MAX_PACKET_CHILDREN: Final[int] = 4096

# ==========================================================
# Entity
# ==========================================================

MAX_COMPONENTS: Final[int] = 256
MAX_ENTITY_RELATIONS: Final[int] = 100000

# ==========================================================
# Metadata
# ==========================================================

MAX_TAGS: Final[int] = 1024
MAX_ATTRIBUTES: Final[int] = 4096
MAX_METADATA_SIZE: Final[int] = 2 * 1024 * 1024

# ==========================================================
# Collections
# ==========================================================

MAX_LIST_SIZE: Final[int] = 100000
MAX_DICT_SIZE: Final[int] = 100000
MAX_SET_SIZE: Final[int] = 100000

# ==========================================================
# Runtime
# ==========================================================

MAX_RETRY: Final[int] = 32
MAX_TIMEOUT: Final[float] = 3600.0
MAX_TTL: Final[int] = 86400

# ==========================================================
# Memory
# ==========================================================

MAX_CACHE_SIZE: Final[int] = 100000
MAX_HISTORY_SIZE: Final[int] = 100000

# ==========================================================
# Graph
# ==========================================================

MAX_GRAPH_NODES: Final[int] = 1_000_000
MAX_GRAPH_EDGES: Final[int] = 10_000_000

# ==========================================================
# Queue
# ==========================================================

MAX_QUEUE_SIZE: Final[int] = 100000

# ==========================================================
# String
# ==========================================================

MAX_TEXT_LENGTH: Final[int] = 16 * 1024 * 1024

# ==========================================================
# Serialization
# ==========================================================

MAX_JSON_DEPTH: Final[int] = 256
