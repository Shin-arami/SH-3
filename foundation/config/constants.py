"""
SH-3 Complete Edition v1.0
Foundation Layer
Configuration Subsystem

constants.py

Kernel immutable constants.
These values are part of the public API and must never
change during runtime.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "COMPATIBILITY_VERSION",
    "DEFAULT_ENCODING",
    "DEFAULT_TIMEZONE",
    "EMPTY_BYTES",
    "EMPTY_FROZENSET",
    "EMPTY_STRING",
    "EMPTY_TUPLE",
    "FALSE",
    "JSON_INDENT",
    "JSON_SORT_KEYS",
    "KERNEL_API_VERSION",
    "KERNEL_CODENAME",
    "KERNEL_NAME",
    "KERNEL_VERSION",
    "PATH_SEPARATOR",
    "PYTHON_MIN_VERSION",
    "SCHEMA_VERSION",
    "TRACE_SEPARATOR",
    "TRUE",
    "UUID_NAMESPACE",
]

# ==========================================================
# Kernel Identity
# ==========================================================

KERNEL_NAME: str = "SH-3 Kernel"
KERNEL_CODENAME: str = "Complete Edition"
KERNEL_VERSION: str = "1.0.0"

# ==========================================================
# API / Schema
# ==========================================================

KERNEL_API_VERSION: int = 1
SCHEMA_VERSION: str = "1.0"
COMPATIBILITY_VERSION: int = 1

# ==========================================================
# Runtime Requirements
# ==========================================================

PYTHON_MIN_VERSION: tuple[int, int] = (3, 12)

# ==========================================================
# Environment
# ==========================================================

DEFAULT_ENCODING: str = "utf-8"
DEFAULT_TIMEZONE: str = "UTC"

# ==========================================================
# Serialization
# ==========================================================

JSON_INDENT: int = 2
JSON_SORT_KEYS: bool = True

# ==========================================================
# Internal Identifiers
# ==========================================================

UUID_NAMESPACE: str = "sh3"

TRACE_SEPARATOR: str = "/"
PATH_SEPARATOR: str = "."

# ==========================================================
# Immutable Objects
# ==========================================================

TRUE: bool = True
FALSE: bool = False

EMPTY_STRING: str = ""
EMPTY_BYTES: bytes = b""

EMPTY_TUPLE: tuple[()] = ()
EMPTY_FROZENSET: frozenset[Any] = frozenset()
