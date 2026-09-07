from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Final

from sh3dev import __title__, __version__
from sh3dev.dispatcher import CommandDispatcher
from sh3dev.exceptions import (
    ExitCode,
    SH3DevKitError,
)
from sh3dev.registry.command_registry import CommandRegistry
from sh3dev.registry.loader import load_builtin_commands

APP_DESCRIPTION: Final[str] = "SH-3 AI Operating System Development Toolkit"


def create_registry() -> CommandRegistry:
    """
    Create command registry.
    """

    registry = CommandRegistry()

    load_builtin_commands(
        registry,
    )

    return registry


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sh3dev",
        description=APP_DESCRIPTION,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"{__title__} {__version__}",
    )

    parser.add_argument(
        "command",
        nargs="?",
        help="Command name",
    )

    parser.add_argument(
        "args",
        nargs="*",
        help="Command arguments",
    )

    return parser


def run(
    args: Sequence[str] | None = None,
) -> int:

    parser = create_parser()

    namespace = parser.parse_args(args)

    if namespace.command is None:
        parser.print_help()

        return int(ExitCode.SUCCESS)

    registry = create_registry()

    dispatcher = CommandDispatcher(
        registry,
    )

    try:
        result = dispatcher.dispatch(
            namespace.command,
            list(namespace.args),
        )

        if result is not None:
            print(result)

        return int(ExitCode.SUCCESS)

    except SH3DevKitError as error:
        print(f"Error: {error}")

        return int(error.exit_code)


def main() -> int:
    return run()


__all__: Final[list[str]] = [
    "create_parser",
    "create_registry",
    "main",
    "run",
]
