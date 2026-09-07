"""
SH-3 Complete Edition v1.0
Foundation Layer
Configuration Subsystem

prefixes.py

Kernel identifier prefixes.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "PREFIX_BELIEF",
    # Storage
    "PREFIX_CACHE",
    "PREFIX_COMPONENT",
    "PREFIX_EDGE",
    "PREFIX_ENTITY",
    # Runtime
    "PREFIX_EVENT",
    "PREFIX_EXPERIENCE",
    # Knowledge
    "PREFIX_FACT",
    "PREFIX_GOAL",
    # Graph
    "PREFIX_GRAPH",
    # Kernel
    "PREFIX_KERNEL",
    "PREFIX_LEARNING",
    # Cognition
    "PREFIX_MEMORY",
    # Base
    "PREFIX_NODE",
    "PREFIX_PACKET",
    "PREFIX_PIPELINE",
    "PREFIX_PLAN",
    "PREFIX_REASONING",
    "PREFIX_REFLECTION",
    "PREFIX_SESSION",
    "PREFIX_SYSTEM",
    "PREFIX_TASK",
    # Misc
    "PREFIX_USER",
    "PREFIX_VECTOR",
    "PREFIX_VERTEX",
    "PREFIX_WORLD_MODEL",
]

# ==========================================================
# Kernel
# ==========================================================

PREFIX_KERNEL: Final[str] = "krn"

# ==========================================================
# Base
# ==========================================================

PREFIX_NODE: Final[str] = "nd"

PREFIX_COMPONENT: Final[str] = "cmp"

PREFIX_ENTITY: Final[str] = "ent"

PREFIX_PACKET: Final[str] = "pkt"

# ==========================================================
# Runtime
# ==========================================================

PREFIX_EVENT: Final[str] = "evt"

PREFIX_TASK: Final[str] = "tsk"

PREFIX_PIPELINE: Final[str] = "pln"

PREFIX_SESSION: Final[str] = "ses"

# ==========================================================
# Cognition
# ==========================================================

PREFIX_MEMORY: Final[str] = "mem"

PREFIX_PLAN: Final[str] = "plan"

PREFIX_GOAL: Final[str] = "goal"

PREFIX_REASONING: Final[str] = "rsn"

PREFIX_WORLD_MODEL: Final[str] = "wm"

PREFIX_LEARNING: Final[str] = "lrn"

PREFIX_REFLECTION: Final[str] = "rfl"

# ==========================================================
# Knowledge
# ==========================================================

PREFIX_FACT: Final[str] = "fact"

PREFIX_BELIEF: Final[str] = "blf"

PREFIX_EXPERIENCE: Final[str] = "exp"

# ==========================================================
# Graph
# ==========================================================

PREFIX_GRAPH: Final[str] = "grp"

PREFIX_EDGE: Final[str] = "edg"

PREFIX_VERTEX: Final[str] = "vtx"

# ==========================================================
# Storage
# ==========================================================

PREFIX_CACHE: Final[str] = "cac"

PREFIX_VECTOR: Final[str] = "vec"

# ==========================================================
# Misc
# ==========================================================

PREFIX_USER: Final[str] = "usr"

PREFIX_SYSTEM: Final[str] = "sys"
