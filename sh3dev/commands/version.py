from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.protocols import CommandMetadata


class VersionCommand(BaseCommand):
    """
    Display SH-3 DevKit version.
    """

    metadata = CommandMetadata(
        name="version",
        description="Show SH-3 DevKit version",
        category="system",
    )

    def execute(
        self,
        args: list[str],
    ) -> object:
        del args

        return "SH-3 DevKit 1.0.0"
