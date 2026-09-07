from __future__ import annotations

from sh3dev.builders import ProjectBuilder
from sh3dev.commands.base import BaseCommand
from sh3dev.protocols import CommandMetadata


class BuildCommand(BaseCommand):
    """
    Build SH-3 project.
    """

    metadata = CommandMetadata(
        name="build",
        description="Build SH-3 project artifacts",
        category="build",
    )

    def __init__(
        self,
        builder: ProjectBuilder | None = None,
    ) -> None:

        self._builder = builder if builder is not None else ProjectBuilder()

    def execute(
        self,
        args: list[str],
    ) -> object:

        root = args[0] if args else "."

        return self._builder.build(
            root,
        )
