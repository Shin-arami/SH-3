from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from types import MappingProxyType
from typing import Any

from foundation.version import EVIDENCE_SCHEMA_VERSION

__all__ = ["EvidenceRecord", "EvidenceStore"]


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, set):
        return sorted((_normalize(item) for item in value), key=repr)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_normalize(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    kind: str
    source: str
    subject_id: str
    version: str
    collected_at: str
    payload: Mapping[str, Any]
    trace_id: str | None
    integrity: str

    @classmethod
    def create(cls, *, evidence_id: str, kind: str, source: str, subject_id: str, version: str = EVIDENCE_SCHEMA_VERSION, payload: Mapping[str, Any] | None = None, trace_id: str | None = None, collected_at: str | None = None) -> EvidenceRecord:
        for name, value in (("evidence_id", evidence_id), ("kind", kind), ("source", source), ("subject_id", subject_id), ("version", version)):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must not be empty")
        if trace_id is not None and not trace_id:
            raise ValueError("trace_id must not be empty")
        timestamp = collected_at or datetime.now(UTC).isoformat()
        if not isinstance(timestamp, str) or not timestamp:
            raise ValueError("collected_at must not be empty")
        copied = MappingProxyType(dict(_normalize(payload or {})))
        integrity = _digest({"evidence_id": evidence_id, "kind": kind, "source": source, "subject_id": subject_id, "version": version, "collected_at": timestamp, "payload": copied, "trace_id": trace_id})
        return cls(evidence_id, kind, source, subject_id, version, timestamp, copied, trace_id, f"sha256:{integrity}")

    def to_dict(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, "kind": self.kind, "source": self.source, "subject_id": self.subject_id, "version": self.version, "collected_at": self.collected_at, "payload": dict(self.payload), "trace_id": self.trace_id, "integrity": self.integrity}

    def verify(self) -> bool:
        expected = _digest({"evidence_id": self.evidence_id, "kind": self.kind, "source": self.source, "subject_id": self.subject_id, "version": self.version, "collected_at": self.collected_at, "payload": self.payload, "trace_id": self.trace_id})
        return self.integrity == f"sha256:{expected}"


class EvidenceStore:
    __slots__ = ("_lock", "_records")

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, EvidenceRecord] = {}

    def register(self, record: EvidenceRecord) -> EvidenceRecord:
        if not isinstance(record, EvidenceRecord):
            raise TypeError("record must be EvidenceRecord")
        if not record.verify():
            raise ValueError("evidence integrity verification failed")
        with self._lock:
            existing = self._records.get(record.evidence_id)
            if existing is not None:
                if existing != record:
                    raise ValueError(f"evidence_id already registered: {record.evidence_id}")
                return existing
            self._records[record.evidence_id] = record
            return record

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        with self._lock:
            return self._records.get(evidence_id)

    def verify(self, evidence_id: str) -> bool:
        record = self.get(evidence_id)
        return record is not None and record.verify()

    def records(self) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(self._records.values())
