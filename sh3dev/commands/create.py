from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.generators import FileGenerator
from sh3dev.protocols import CommandMetadata


class CreateCommand(BaseCommand):
    """
    Create SH-3 project files.
    """

    metadata = CommandMetadata(
        name="create",
        description="Create SH-3 files",
        category="generator",
    )

    def __init__(
        self,
        generator: FileGenerator | None = None,
    ) -> None:
        self._generator = generator if generator is not None else FileGenerator()

    def execute(
        self,
        args: list[str],
    ) -> object:

        if len(args) < 2:
            return "Usage: create <path> <content>"

        path = args[0]

        content = args[1]

        result = self._generator.create_file(
            path,
            content,
        )

        return f"Created: {result}"
