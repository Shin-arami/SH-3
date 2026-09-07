from __future__ import annotations

from sh3dev.commands.info import InfoCommand
from sh3dev.commands.version import VersionCommand
from sh3dev.registry.command_registry import CommandRegistry


class CommandFactory:
    """
    Creates command plugin instances.
    """

    def __init__(
        self,
        registry: CommandRegistry,
    ) -> None:
        self._registry = registry

    def create(self) -> list[object]:
        return [
            InfoCommand(),
            VersionCommand(),
        ]
