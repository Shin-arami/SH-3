from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.monitoring import (
    StatusCollector,
)
from sh3dev.protocols import CommandMetadata


class StatusCommand(BaseCommand):
    """
    Show SH-3 project status.
    """

    metadata = CommandMetadata(
        name="status",
        description="Show SH-3 project status",
        category="system",
    )

    def __init__(
        self,
    ) -> None:

        self._collector = StatusCollector()

    def execute(
        self,
        args: list[str],
    ) -> object:

        root = args[0] if args else "."

        return self._collector.collect(
            root,
        )
