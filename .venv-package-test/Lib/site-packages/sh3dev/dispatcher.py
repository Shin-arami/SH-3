from __future__ import annotations

from sh3dev.exceptions import SH3DevKitError
from sh3dev.protocols.command import CommandProtocol
from sh3dev.registry.command_registry import CommandRegistry


class CommandDispatcher:
    """
    Dispatch commands to registered plugins.
    """

    def __init__(
        self,
        registry: CommandRegistry,
    ) -> None:
        self._registry = registry

    def dispatch(
        self,
        name: str,
        args: list[str],
    ) -> object:
        command: CommandProtocol | None = self._registry.get(name)

        if command is None:
            raise SH3DevKitError(f"Unknown command: {name}")

        return command.execute(args)
