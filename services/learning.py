from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from foundation.enums import Severity
from foundation.utils.exceptions import SH3Exception

from .base import Service
from .health import HealthState, HealthStatus

__all__ = ["LearningException", "LearningRecord", "LearningService"]


class LearningException(SH3Exception):
    """Learning operation failure."""


@dataclass(frozen=True, slots=True)
class LearningRecord:
    key: str
    value: float
    success: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not self.key or not self.key.strip():
            raise ValueError("key must not be empty")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "details": dict(self.details),
        }


class LearningService(Service):
    __slots__ = ("_records", "_started")

    def __init__(self, name: str = "learning") -> None:
        super().__init__(name)
        self._records: dict[str, list[LearningRecord]] = {}
        self._started = False

    def _on_start(self) -> None:
        with self._lock:
            self._started = True

    def _on_suspend(self) -> None:
        with self._lock:
            self._started = False

    def _on_resume(self) -> None:
        with self._lock:
            self._started = True

    def _on_terminate(self) -> None:
        with self._lock:
            self._started = False
            self._records.clear()

    def record(
        self,
        key: str,
        value: float,
        success: bool = True,
        details: Mapping[str, Any] | None = None,
    ) -> LearningRecord:
        if not key or not key.strip():
            raise ValueError("key must not be empty")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("value must be numeric") from exc
        record = LearningRecord(
            key=key,
            value=numeric_value,
            success=bool(success),
            details=details or {},
        )
        with self._lock:
            self._records.setdefault(key, []).append(record)
        return record

    def add(self, record: LearningRecord) -> None:
        if not isinstance(record, LearningRecord):
            raise TypeError("record must be a LearningRecord")
        with self._lock:
            self._records.setdefault(record.key, []).append(record)

    def records(self, key: str | None = None) -> tuple[LearningRecord, ...]:
        with self._lock:
            if key is not None:
                return tuple(self._records.get(key, ()))
            return tuple(record for records in self._records.values() for record in records)

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._records))

    def count(self, key: str | None = None) -> int:
        with self._lock:
            if key is not None:
                return len(self._records.get(key, ()))
            return sum(len(records) for records in self._records.values())

    def latest(self, key: str) -> LearningRecord | None:
        with self._lock:
            records = self._records.get(key)
            return records[-1] if records else None

    def average(self, key: str) -> float | None:
        with self._lock:
            records = self._records.get(key, ())
            if not records:
                return None
            return sum(record.value for record in records) / len(records)

    def success_rate(self, key: str | None = None) -> float | None:
        with self._lock:
            records = (
                self._records.get(key, ())
                if key is not None
                else tuple(record for values in self._records.values() for record in values)
            )
            if not records:
                return None
            return sum(record.success for record in records) / len(records)

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._records.clear()
            else:
                self._records.pop(key, None)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            records = {
                key: [record.to_dict() for record in values]
                for key, values in sorted(self._records.items())
            }
            total = sum(len(values) for values in self._records.values())
            return {
                "name": self.name,
                "state": self.state.value,
                "started": self._started,
                "keys": tuple(sorted(self._records)),
                "record_count": total,
                "records": records,
            }

    def health(self) -> HealthStatus:
        with self._lock:
            key_count = len(self._records)
            record_count = sum(len(records) for records in self._records.values())
            started = self._started
        if self.terminated:
            return HealthStatus.create(
                HealthState.UNHEALTHY,
                "Learning service is terminated",
                {"keys": key_count, "records": record_count},
                self.name,
                Severity.HIGH,
            )
        if self.suspended:
            return HealthStatus.create(
                HealthState.DEGRADED,
                "Learning service is suspended",
                {"keys": key_count, "records": record_count},
                self.name,
                Severity.MEDIUM,
            )
        if started:
            return HealthStatus.create(
                HealthState.HEALTHY,
                "Learning service is active",
                {"keys": key_count, "records": record_count},
                self.name,
                Severity.INFO,
            )
        return HealthStatus.create(
            HealthState.UNKNOWN,
            "Learning service is not active",
            {"keys": key_count, "records": record_count},
            self.name,
            Severity.LOW,
        )
