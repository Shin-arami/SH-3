from __future__ import annotations

from sh3dev.commands.base import BaseCommand
from sh3dev.diagnostics import Doctor
from sh3dev.protocols import CommandMetadata


class DoctorCommand(BaseCommand):
    """
    Diagnose SH-3 environment.
    """

    metadata = CommandMetadata(
        name="doctor",
        description="Diagnose SH-3 environment",
        category="system",
    )

    def __init__(
        self,
    ) -> None:

        self._doctor = Doctor()

    def execute(
        self,
        args: list[str],
    ) -> object:

        root = args[0] if args else "."

        return self._doctor.run(
            root,
        )
