from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.generators import (
    ArchitectureGenerator,
)
from sh3dev.protocols import CommandMetadata


class ArchitectureCommand(BaseCommand):
    """
    Generate SH-3 architecture documents.
    """

    metadata = CommandMetadata(
        name="architecture",
        description="Generate architecture documents",
        category="documentation",
    )

    def __init__(
        self,
    ) -> None:

        self._generator = ArchitectureGenerator()

    def execute(
        self,
        args: list[str],
    ) -> object:

        if not args:
            return "Usage: architecture generate"

        if args[0] != "generate":
            return f"Unknown action: {args[0]}"

        files = self._generator.generate()

        return "\n".join(str(file) for file in files)
