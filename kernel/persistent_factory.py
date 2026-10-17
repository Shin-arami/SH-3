from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from infrastructure.event_bus import EventPublisher
from infrastructure.security.persistent_replay_runtime import (
    PersistentReplayStores,
    create_persistent_replay_stores,
)
from kernel.core import SH3Kernel

__all__ = [
    "PersistentKernelRuntime",
    "create_persistent_sh3_kernel",
]

_DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class PersistentKernelRuntime:
    """A kernel and the persistent stores configured for its closed loop."""

    kernel: SH3Kernel
    stores: PersistentReplayStores

    def __post_init__(self) -> None:
        if not isinstance(self.kernel, SH3Kernel):
            raise TypeError("kernel must be SH3Kernel")
        if not isinstance(self.stores, PersistentReplayStores):
            raise TypeError("stores must be PersistentReplayStores")

    @property
    def database_path(self) -> Path:
        """Return the canonical SQLite database path used by both stores."""
        return self.stores.database_path


def create_persistent_sh3_kernel(
    database_path: str | PathLike[str] | None = None,
    *,
    event_publisher: EventPublisher | None = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    create_if_missing: bool = False,
    environ: Mapping[str, str] | None = None,
) -> PersistentKernelRuntime:
    """Create a kernel whose evidence and replay claims share one SQLite DB.

    Existing databases are validated by the persistent store factory before the
    kernel is constructed. Missing databases fail closed unless
    ``create_if_missing=True`` is supplied explicitly for first-time provisioning.
    The function does not change the default behavior of ``SH3Kernel()`` and does
    not attach persistent storage to unrelated kernel instances.
    """
    stores = create_persistent_replay_stores(
        database_path,
        timeout_seconds=timeout_seconds,
        create_if_missing=create_if_missing,
        environ=environ,
    )
    kernel = SH3Kernel(
        event_publisher=event_publisher,
        evidence_store=stores.evidence_store,
        replay_claim_store=stores.replay_claim_store,
    )
    return PersistentKernelRuntime(kernel=kernel, stores=stores)
