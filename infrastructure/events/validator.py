"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

validator.py

Canonical event schema validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.Enums.priority import Priority

from .model import Event, EventContext, EventMetadata

__all__ = [
    "EventValidationError",
    "EventValidator",
    "ValidationIssue",
]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    message: str
    value: Any = None

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


class EventValidationError(ValueError):
    def __init__(
        self,
        issues: tuple[ValidationIssue, ...],
    ) -> None:
        self.issues = issues
        message = "; ".join(str(issue) for issue in issues)
        super().__init__(message)


class EventValidator:
    """Validate SH-3 events before publication."""

    REQUIRED_METADATA = (
        "event_id",
        "event_name",
        "event_version",
        "timestamp",
        "producer",
        "correlation_id",
    )

    OPTIONAL_METADATA = (
        "causation_id",
        "priority",
        "tags",
        "trace_id",
        "tenant_id",
    )

    REQUIRED_TOP_LEVEL = (
        "metadata",
        "payload",
        "context",
    )

    @classmethod
    def validate(
        cls,
        event: Event,
    ) -> None:
        issues = cls.collect(event)
        if issues:
            raise EventValidationError(tuple(issues))

    @classmethod
    def is_valid(
        cls,
        event: Event,
    ) -> bool:
        return not cls.collect(event)

    @classmethod
    def collect(
        cls,
        event: Event,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if not isinstance(event, Event):
            return [
                ValidationIssue(
                    "event",
                    "must be an Event instance",
                    event,
                )
            ]

        cls._validate_metadata(event.metadata, issues)
        cls._validate_payload(event.payload, issues)
        cls._validate_context(event.context, issues)
        cls._validate_category(event.category, issues)
        cls._validate_event_type(event.event_type, issues)

        return issues

    @classmethod
    def validate_dict(
        cls,
        data: Mapping[str, Any],
    ) -> None:
        issues = cls.collect_dict(data)
        if issues:
            raise EventValidationError(tuple(issues))

    @classmethod
    def is_valid_dict(
        cls,
        data: Mapping[str, Any],
    ) -> bool:
        return not cls.collect_dict(data)

    @classmethod
    def collect_dict(
        cls,
        data: Mapping[str, Any],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if not isinstance(data, Mapping):
            return [
                ValidationIssue(
                    "event",
                    "must be a mapping",
                    data,
                )
            ]

        for field in cls.REQUIRED_TOP_LEVEL:
            if field not in data:
                issues.append(
                    ValidationIssue(
                        field,
                        "required field is missing",
                    )
                )

        metadata = data.get("metadata")
        if isinstance(metadata, Mapping):
            cls._validate_metadata_dict(metadata, issues)
        elif metadata is not None:
            issues.append(
                ValidationIssue(
                    "metadata",
                    "must be a mapping",
                    metadata,
                )
            )

        payload = data.get("payload")
        if not isinstance(payload, Mapping):
            issues.append(
                ValidationIssue(
                    "payload",
                    "must be a mapping",
                    payload,
                )
            )

        context = data.get("context")
        if isinstance(context, Mapping):
            cls._validate_context_dict(context, issues)
        elif context is not None:
            issues.append(
                ValidationIssue(
                    "context",
                    "must be a mapping",
                    context,
                )
            )

        category = data.get("category")
        if category is not None:
            try:
                Category(str(category))
            except (TypeError, ValueError):
                issues.append(
                    ValidationIssue(
                        "category",
                        "invalid category",
                        category,
                    )
                )
        elif "category" in data:
            issues.append(
                ValidationIssue(
                    "category",
                    "invalid category",
                    category,
                )
            )

        event_type = data.get("event_type")
        if event_type is not None:
            try:
                EventType(str(event_type))
            except (TypeError, ValueError):
                issues.append(
                    ValidationIssue(
                        "event_type",
                        "invalid event type",
                        event_type,
                    )
                )
        elif "event_type" in data:
            issues.append(
                ValidationIssue(
                    "event_type",
                    "invalid event type",
                    event_type,
                )
            )

        return issues

    @classmethod
    def _validate_metadata(
        cls,
        metadata: EventMetadata,
        issues: list[ValidationIssue],
    ) -> None:
        if not isinstance(metadata, EventMetadata):
            issues.append(
                ValidationIssue(
                    "metadata",
                    "must be EventMetadata",
                    metadata,
                )
            )
            return

        cls._validate_metadata_values(
            metadata.to_dict(),
            issues,
        )

    @classmethod
    def _validate_metadata_dict(
        cls,
        metadata: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        for field in cls.REQUIRED_METADATA:
            if field not in metadata:
                issues.append(
                    ValidationIssue(
                        f"metadata.{field}",
                        "required field is missing",
                    )
                )

        cls._validate_metadata_values(metadata, issues)

    @classmethod
    def _validate_metadata_values(
        cls,
        metadata: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        cls._require_string(
            metadata,
            "event_id",
            issues,
        )
        cls._require_string(
            metadata,
            "event_name",
            issues,
        )
        cls._require_string(
            metadata,
            "event_version",
            issues,
        )
        cls._require_string(
            metadata,
            "producer",
            issues,
        )
        cls._require_string(
            metadata,
            "correlation_id",
            issues,
        )

        timestamp = metadata.get("timestamp")
        if timestamp is not None and not isinstance(timestamp, (datetime, str)):
            issues.append(
                ValidationIssue(
                        "metadata.timestamp",
                        "must be datetime or ISO timestamp",
                        timestamp,
                    )
                )

        priority = metadata.get("priority")
        if priority is not None:
            if isinstance(priority, Priority):
                pass
            elif isinstance(priority, str):
                try:
                    Priority[priority]
                except KeyError:
                    issues.append(
                        ValidationIssue(
                            "metadata.priority",
                            "invalid priority",
                            priority,
                        )
                    )
            else:
                issues.append(
                    ValidationIssue(
                        "metadata.priority",
                        "must be Priority or priority name",
                        priority,
                    )
                )

        tags = metadata.get("tags")
        if tags is not None:
            cls._validate_tags(
                tags,
                "metadata.tags",
                issues,
            )

        for field in (
            "causation_id",
            "trace_id",
            "tenant_id",
        ):
            value = metadata.get(field)
            if value is not None and not isinstance(value, str):
                issues.append(
                    ValidationIssue(
                        f"metadata.{field}",
                        "must be a string",
                        value,
                    )
                )

    @staticmethod
    def _validate_payload(
        payload: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        if not isinstance(payload, Mapping):
            issues.append(
                ValidationIssue(
                    "payload",
                    "must be a mapping",
                    payload,
                )
            )

    @classmethod
    def _validate_context(
        cls,
        context: EventContext,
        issues: list[ValidationIssue],
    ) -> None:
        if not isinstance(context, EventContext):
            issues.append(
                ValidationIssue(
                    "context",
                    "must be EventContext",
                    context,
                )
            )
            return

        cls._validate_context_dict(
            context.to_dict(),
            issues,
        )

    @staticmethod
    def _validate_context_dict(
        context: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        fields = (
            "runtime",
            "execution",
            "mission",
            "security",
            "tracing",
        )

        for field in fields:
            if field not in context:
                continue

            if not isinstance(context[field], Mapping):
                issues.append(
                    ValidationIssue(
                        f"context.{field}",
                        "must be a mapping",
                        context[field],
                    )
                )

    @staticmethod
    def _validate_category(
        category: Category,
        issues: list[ValidationIssue],
    ) -> None:
        if not isinstance(category, Category):
            issues.append(
                ValidationIssue(
                    "category",
                    "must be Category",
                    category,
                )
            )

    @staticmethod
    def _validate_event_type(
        event_type: EventType,
        issues: list[ValidationIssue],
    ) -> None:
        if not isinstance(event_type, EventType):
            issues.append(
                ValidationIssue(
                    "event_type",
                    "must be EventType",
                    event_type,
                )
            )

    @staticmethod
    def _require_string(
        data: Mapping[str, Any],
        field: str,
        issues: list[ValidationIssue],
    ) -> None:
        value = data.get(field)

        if not isinstance(value, str):
            issues.append(
                ValidationIssue(
                    f"metadata.{field}",
                    "must be a string",
                    value,
                )
            )
            return

        if not value:
            issues.append(
                ValidationIssue(
                    f"metadata.{field}",
                    "must not be empty",
                    value,
                )
            )

    @staticmethod
    def _validate_tags(
        tags: Any,
        field: str,
        issues: list[ValidationIssue],
    ) -> None:
        if not isinstance(tags, Mapping):
            issues.append(
                ValidationIssue(
                    field,
                    "must be a mapping",
                    tags,
                )
            )
            return

        for key, value in tags.items():
            if not isinstance(key, str) or not key:
                issues.append(
                    ValidationIssue(
                        field,
                        "tag keys must be non-empty strings",
                        key,
                    )
                )
            if not isinstance(value, str):
                issues.append(
                    ValidationIssue(
                        field,
                        "tag values must be strings",
                        value,
                    )
                )
