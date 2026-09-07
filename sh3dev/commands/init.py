from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.initialization import (
    ProjectInitializer,
)
from sh3dev.protocols import CommandMetadata


class InitCommand(BaseCommand):
    """
    Initialize SH-3 project.
    """

    metadata = CommandMetadata(
        name="init",
        description="Initialize SH-3 project",
        category="project",
    )

    def __init__(
        self,
    ) -> None:

        self._initializer = ProjectInitializer()

    def execute(
        self,
        args: list[str],
    ) -> object:

        root = args[0] if args else "SH-3"

        return self._initializer.initialize(
            root,
        )
