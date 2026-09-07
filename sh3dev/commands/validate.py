from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.protocols import CommandMetadata
from sh3dev.validation import ProjectValidator


class ValidateCommand(BaseCommand):
    """
    Validate SH-3 project.
    """

    metadata = CommandMetadata(
        name="validate",
        description="Validate SH-3 project structure",
        category="quality",
    )

    def __init__(
        self,
        validator: ProjectValidator | None = None,
    ) -> None:
        self._validator = validator if validator is not None else ProjectValidator()

    def execute(
        self,
        args: list[str],
    ) -> object:

        root = args[0] if args else "."

        return self._validator.validate(
            root,
        )
