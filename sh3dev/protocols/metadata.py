from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DEFAULT_COMMAND_VERSION: Final[str] = "1.0.0"


@dataclass(
    frozen=True,
    slots=True,
)
class CommandMetadata:
    """
    Metadata definition for SH-3 commands.
    """

    name: str
    description: str
    category: str
    version: str = DEFAULT_COMMAND_VERSION
