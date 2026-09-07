from __future__ import annotations

from abc import ABC, abstractmethod

from sh3dev.protocols import CommandMetadata


class BaseCommand(ABC):
    """
    Base implementation for SH-3 commands.
    """

    metadata: CommandMetadata

    @abstractmethod
    def execute(
        self,
        args: list[str],
    ) -> object:
        """
        Execute command.
        """
        raise NotImplementedError
