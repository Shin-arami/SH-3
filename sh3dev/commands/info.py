from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.protocols import CommandMetadata


class InfoCommand(BaseCommand):
    """
    Display SH-3 DevKit information.
    """

    metadata = CommandMetadata(
        name="info",
        description="Show SH-3 DevKit information",
        category="system",
    )

    def execute(
        self,
        args: list[str],
    ) -> object:
        del args

        return {
            "name": "SH-3 DevKit",
            "version": "1.0.0",
            "status": "development",
        }
