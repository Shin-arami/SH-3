"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

Public Events API.
"""

from __future__ import annotations

from .model import (
    Event,
    EventContext,
    EventMetadata,
)
from .registry import (
    EventSchema,
    EventSchemaRegistry,
    SchemaKey,
)
from .validator import (
    EventValidationError,
    EventValidator,
    ValidationIssue,
)

__all__ = [
    "Event",
    "EventContext",
    "EventMetadata",
    "EventSchema",
    "EventSchemaRegistry",
    "EventValidationError",
    "EventValidator",
    "SchemaKey",
    "ValidationIssue",
]
