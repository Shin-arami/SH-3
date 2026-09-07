from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.generators import (
    ReleaseNotesGenerator,
)
from sh3dev.protocols import CommandMetadata
from sh3dev.release import (
    ReleaseManager,
)


class ReleaseCommand(BaseCommand):
    """
    Generate SH-3 release report.
    """

    metadata = CommandMetadata(
        name="release",
        description="Prepare SH-3 release",
        category="release",
    )

    def __init__(
        self,
    ) -> None:

        self._manager = ReleaseManager()

        self._generator = ReleaseNotesGenerator()

    def execute(
        self,
        args: list[str],
    ) -> object:

        report = self._manager.prepare()

        self._generator.generate(
            report,
        )

        return report
