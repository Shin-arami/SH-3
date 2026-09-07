from __future__ import annotations

from sh3dev.commands.architecture import ArchitectureCommand
from sh3dev.commands.build import BuildCommand
from sh3dev.commands.create import CreateCommand
from sh3dev.commands.doctor import DoctorCommand
from sh3dev.commands.github import GitHubCommand
from sh3dev.commands.info import InfoCommand
from sh3dev.commands.init import InitCommand
from sh3dev.commands.list import ListCommand
from sh3dev.commands.release import ReleaseCommand
from sh3dev.commands.rfc import RFCCommand
from sh3dev.commands.status import StatusCommand
from sh3dev.commands.template import TemplateCommand
from sh3dev.commands.validate import ValidateCommand
from sh3dev.commands.version import VersionCommand
from sh3dev.registry.command_registry import CommandRegistry


def load_builtin_commands(
    registry: CommandRegistry,
) -> None:
    """
    Load built-in SH-3 commands.
    """

    commands = (
        InfoCommand(),
        VersionCommand(),
        ListCommand(registry),
        CreateCommand(),
        RFCCommand(),
        ValidateCommand(),
        BuildCommand(),
        TemplateCommand(),
        ArchitectureCommand(),
        DoctorCommand(),
        StatusCommand(),
        GitHubCommand(),
        ReleaseCommand(),
        InitCommand(),
    )

    for command in commands:
        registry.register(
            command,
        )
