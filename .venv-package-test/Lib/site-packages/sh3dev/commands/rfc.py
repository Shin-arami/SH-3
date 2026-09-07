from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.generators import (
    RFCGenerator,
    RFCIndexGenerator,
)
from sh3dev.protocols import CommandMetadata
from sh3dev.registry.rfc_registry import (
    RFCEntry,
    RFCRegistry,
)


class RFCCommand(BaseCommand):
    """
    Manage SH-3 RFC documents.
    """

    metadata = CommandMetadata(
        name="rfc",
        description="Manage SH-3 RFC documents",
        category="documentation",
    )

    def __init__(
        self,
    ) -> None:

        self._generator = RFCGenerator()

        self._registry = RFCRegistry()

        self._index = RFCIndexGenerator()

    def execute(
        self,
        args: list[str],
    ) -> object:

        if not args:
            return "Usage: rfc create|list|index"

        action = args[0]

        if action == "create":
            if len(args) < 4:
                return "Usage: rfc create <number> <title> <output>"

            entry = RFCEntry(
                number=args[1],
                title=args[2],
                path=args[3],
            )

            self._generator.generate(
                args[1],
                args[2],
                args[3],
            )

            self._registry.add(
                entry,
            )

            return f"Created RFC-{args[1]}"

        if action == "list":
            return "\n".join((f"RFC-{item.number} {item.title}") for item in self._registry.load())

        if action == "index":
            result = self._index.generate(
                self._registry.load(),
            )

            return f"Generated: {result}"

        return f"Unknown RFC action: {action}"
