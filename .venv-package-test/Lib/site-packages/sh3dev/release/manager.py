from __future__ import annotations

from sh3dev.monitoring import (
    StatusCollector,
)


class ReleaseManager:
    """
    Manage SH-3 releases.
    """

    def __init__(
        self,
    ) -> None:

        self._status = StatusCollector()

    def prepare(
        self,
        root: str = ".",
    ) -> dict[str, object]:

        status = self._status.collect(
            root,
        )

        return {
            "project": (status["project"]),
            "version": (status["version"]),
            "build": "SUCCESS",
            "validation": (status["validation"]),
            "status": ("READY" if status["validation"] == "PASS" else "FAILED"),
        }
