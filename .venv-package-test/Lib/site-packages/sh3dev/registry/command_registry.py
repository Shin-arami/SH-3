from __future__ import annotations

from sh3dev.protocols.command import CommandProtocol


class CommandRegistry:
    """
    Registry for SH-3 command plugins.
    """

    def __init__(self) -> None:
        self._commands: dict[
            str,
            CommandProtocol,
        ] = {}

    def register(
        self,
        command: CommandProtocol,
    ) -> None:
        """
        Register command plugin.
        """

        self._commands[command.metadata.name] = command

    def get(
        self,
        name: str,
    ) -> CommandProtocol | None:
        """
        Get command plugin.
        """

        return self._commands.get(name)

    def all(
        self,
    ) -> tuple[CommandProtocol, ...]:
        """
        Return all commands.
        """

        return tuple(self._commands.values())
