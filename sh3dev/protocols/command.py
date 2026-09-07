from __future__ import annotations

from typing import Protocol

from sh3dev.protocols.metadata import CommandMetadata


class CommandProtocol(Protocol):
    """
    SH-3 command plugin protocol.
    """

    metadata: CommandMetadata

    def execute(
        self,
        args: list[str],
    ) -> object:
        """
        Execute command.
        """
        ...
