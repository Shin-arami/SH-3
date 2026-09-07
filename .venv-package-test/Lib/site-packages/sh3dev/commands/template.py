from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.protocols import CommandMetadata
from sh3dev.templates import (
    TemplateRegistry,
)


class TemplateCommand(BaseCommand):
    """
    Manage templates.
    """

    metadata = CommandMetadata(
        name="template",
        description="Manage templates",
        category="development",
    )

    def __init__(
        self,
    ) -> None:

        self._registry = TemplateRegistry()

    def execute(
        self,
        args: list[str],
    ) -> object:

        if not args:
            return "Usage: template list"

        if args[0] == "list":
            templates = self._registry.list()

            return "\n".join((f"{item.category}/{item.name}") for item in templates)

        return f"Unknown action: {args[0]}"
