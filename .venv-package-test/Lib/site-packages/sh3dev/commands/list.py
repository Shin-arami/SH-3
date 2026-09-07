from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.protocols import CommandMetadata
from sh3dev.registry.command_registry import CommandRegistry


class ListCommand(BaseCommand):
    """
    List registered commands.
    """

    metadata = CommandMetadata(
        name="list",
        description="List available commands",
        category="system",
    )

    def __init__(
        self,
        registry: CommandRegistry,
    ) -> None:
        self._registry = registry

    def execute(
        self,
        args: list[str],
    ) -> object:
        del args

        commands = []

        for command in self._registry.all():
            commands.append(f"{command.metadata.name:<12}{command.metadata.description}")

        return "\n".join(commands)
