from __future__ import annotations

from enum import IntEnum
from typing import Final


class ExitCode(IntEnum):
    SUCCESS = 0
    GENERAL_ERROR = 1
    INVALID_ARGUMENT = 2
    CONFIGURATION_ERROR = 3
    EXECUTION_ERROR = 4


class SH3DevKitError(Exception):
    """Base exception for SH-3 DevKit."""

    exit_code: ExitCode = ExitCode.GENERAL_ERROR

    def __init__(
        self,
        message: str,
        *,
        exit_code: ExitCode | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if exit_code is not None:
            self.exit_code = exit_code

    def __str__(self) -> str:
        return self.message


class ConfigurationError(SH3DevKitError):
    """Configuration related error."""

    exit_code = ExitCode.CONFIGURATION_ERROR


class InvalidArgumentError(SH3DevKitError):
    """Invalid command argument error."""

    exit_code = ExitCode.INVALID_ARGUMENT


class CommandExecutionError(SH3DevKitError):
    """Command execution failure."""

    exit_code = ExitCode.EXECUTION_ERROR


class CommandNotFoundError(Exception):
    """Raised when requested command does not exist."""

    def __init__(self, command_name: str) -> None:
        super().__init__(f"Command not found: {command_name}")


__all__: Final[list[str]] = [
    "CommandExecutionError",
    "CommandNotFoundError",
    "ConfigurationError",
    "ExitCode",
    "InvalidArgumentError",
    "SH3DevKitError",
]
