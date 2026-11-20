from __future__ import annotations

from dataclasses import dataclass


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class ReplayExecutionContext:
    """Private owner context for one optimizer replay-stage execution.

    This value is passed in-process and is deliberately not serialized into
    events. The parent claim and stage stores remain the authorities for its
    owner token and generation.
    """

    cycle_id: str
    cycle_fingerprint: str
    parent_stage_key: str
    owner_token: str
    generation: int
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("cycle_id", self.cycle_id),
            ("cycle_fingerprint", self.cycle_fingerprint),
            ("parent_stage_key", self.parent_stage_key),
            ("owner_token", self.owner_token),
        ):
            _text(name, value)
        if self.tenant_id is not None:
            _text("tenant_id", self.tenant_id)
        if (
            isinstance(self.generation, bool)
            or not isinstance(self.generation, int)
            or self.generation < 1
        ):
            raise ValueError("generation must be a positive integer")


class DurableOperationPersistenceError(RuntimeError):
    """Raised when a durable optimizer ledger operation cannot be committed.

    This exception must cross optimizer boundaries unchanged. Converting it to
    an ordinary optimization failure could complete the parent Replay Stage
    while one or more Action rows are still claimed.
    """
