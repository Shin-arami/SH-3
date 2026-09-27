"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

Public Events API.
"""

from __future__ import annotations

from .catalog import (
    CANONICAL_EVENT_VERSION,
    CanonicalEventCatalog,
    EventDefinition,
)
from .model import (
    Event,
    EventContext,
    EventMetadata,
)
from .propagation import EventPropagationContext
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
    "CANONICAL_EVENT_VERSION",
    "CanonicalEventCatalog",
    "Event",
    "EventContext",
    "EventDefinition",
    "EventMetadata",
    "EventPropagationContext",
    "EventSchema",
    "EventSchemaRegistry",
    "EventValidationError",
    "EventValidator",
    "SchemaKey",
    "ValidationIssue",
]
