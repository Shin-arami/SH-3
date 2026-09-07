"""
SH-3 Complete Edition v1.0
Foundation Layer
Configuration Subsystem

reserved.py

Kernel reserved names and metadata keys.
These keys are reserved by the kernel and must not be
redefined by user code.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "KEY_ATTRIBUTES",
    "KEY_CATEGORY",
    # AI
    "KEY_CONFIDENCE",
    # Runtime
    "KEY_CONTEXT",
    # Time
    "KEY_CREATED_AT",
    "KEY_EDGES",
    "KEY_ENCODING",
    # Packet
    "KEY_HEADER",
    # Common Keys
    "KEY_ID",
    "KEY_METADATA",
    "KEY_NAME",
    # Graph
    "KEY_NODES",
    # Ownership
    "KEY_OWNER",
    "KEY_PARENT_ID",
    "KEY_PAYLOAD",
    # Runtime
    "KEY_PRIORITY",
    "KEY_RETRY",
    "KEY_ROOT_ID",
    # Serialization
    "KEY_SCHEMA",
    "KEY_SCORE",
    "KEY_SOURCE",
    "KEY_STATE",
    "KEY_STATUS",
    # Metadata
    "KEY_TAGS",
    "KEY_TARGET",
    "KEY_TIMEOUT",
    "KEY_TIMESTAMP",
    "KEY_TRACE",
    "KEY_TTL",
    "KEY_TYPE",
    "KEY_UPDATED_AT",
    "KEY_UUID",
    "KEY_VERSION",
    "KEY_WEIGHT",
    # Reserved Collections
    "RESERVED_KEYS",
]

# ==========================================================
# Common
# ==========================================================

KEY_ID: Final[str] = "id"
KEY_PARENT_ID: Final[str] = "parent_id"
KEY_ROOT_ID: Final[str] = "root_id"
KEY_UUID: Final[str] = "uuid"

KEY_NAME: Final[str] = "name"
KEY_TYPE: Final[str] = "type"
KEY_CATEGORY: Final[str] = "category"

KEY_VERSION: Final[str] = "version"

KEY_STATUS: Final[str] = "status"
KEY_STATE: Final[str] = "state"

# ==========================================================
# Time
# ==========================================================

KEY_CREATED_AT: Final[str] = "created_at"
KEY_UPDATED_AT: Final[str] = "updated_at"
KEY_TIMESTAMP: Final[str] = "timestamp"

# ==========================================================
# Runtime
# ==========================================================

KEY_PRIORITY: Final[str] = "priority"
KEY_TIMEOUT: Final[str] = "timeout"
KEY_TTL: Final[str] = "ttl"
KEY_RETRY: Final[str] = "retry"

# ==========================================================
# Ownership
# ==========================================================

KEY_OWNER: Final[str] = "owner"
KEY_SOURCE: Final[str] = "source"
KEY_TARGET: Final[str] = "target"

# ==========================================================
# Packet
# ==========================================================

KEY_HEADER: Final[str] = "header"
KEY_PAYLOAD: Final[str] = "payload"

# ==========================================================
# Graph
# ==========================================================

KEY_NODES: Final[str] = "nodes"
KEY_EDGES: Final[str] = "edges"

# ==========================================================
# Metadata
# ==========================================================

KEY_TAGS: Final[str] = "tags"
KEY_ATTRIBUTES: Final[str] = "attributes"
KEY_METADATA: Final[str] = "metadata"

# ==========================================================
# AI
# ==========================================================

KEY_CONFIDENCE: Final[str] = "confidence"
KEY_SCORE: Final[str] = "score"
KEY_WEIGHT: Final[str] = "weight"

# ==========================================================
# Serialization
# ==========================================================

KEY_SCHEMA: Final[str] = "schema"
KEY_ENCODING: Final[str] = "encoding"

# ==========================================================
# Runtime
# ==========================================================

KEY_CONTEXT: Final[str] = "context"
KEY_TRACE: Final[str] = "trace"

# ==========================================================
# Reserved Collection
# ==========================================================

_RESERVED = {
    KEY_ID,
    KEY_PARENT_ID,
    KEY_ROOT_ID,
    KEY_UUID,
    KEY_NAME,
    KEY_TYPE,
    KEY_CATEGORY,
    KEY_VERSION,
    KEY_STATUS,
    KEY_STATE,
    KEY_CREATED_AT,
    KEY_UPDATED_AT,
    KEY_TIMESTAMP,
    KEY_PRIORITY,
    KEY_TIMEOUT,
    KEY_TTL,
    KEY_RETRY,
    KEY_OWNER,
    KEY_SOURCE,
    KEY_TARGET,
    KEY_HEADER,
    KEY_PAYLOAD,
    KEY_NODES,
    KEY_EDGES,
    KEY_TAGS,
    KEY_ATTRIBUTES,
    KEY_METADATA,
    KEY_CONFIDENCE,
    KEY_SCORE,
    KEY_WEIGHT,
    KEY_SCHEMA,
    KEY_ENCODING,
    KEY_CONTEXT,
    KEY_TRACE,
}

RESERVED_KEYS: Final[frozenset[str]] = frozenset(_RESERVED)

del _RESERVED
