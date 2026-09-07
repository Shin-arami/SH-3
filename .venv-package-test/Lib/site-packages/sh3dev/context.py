from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

DEFAULT_METADATA_KEY: Final[str] = "sh3dev"


@dataclass(slots=True)
class ExecutionContext:
    """Runtime context for SH-3 DevKit execution."""

    project_root: Path
    working_directory: Path
    verbose: bool = False
    environment: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    def get_metadata(
        self,
        key: str,
        default: str | None = None,
    ) -> str | None:
        return self.metadata.get(key, default)

    def set_metadata(
        self,
        key: str,
        value: str,
    ) -> None:
        self.metadata[key] = value

    @property
    def is_verbose(self) -> bool:
        return self.verbose


def create_default_context(
    project_root: Path | None = None,
) -> ExecutionContext:
    """Create default execution context."""

    root = project_root.resolve() if project_root is not None else Path.cwd().resolve()

    return ExecutionContext(
        project_root=root,
        working_directory=Path.cwd().resolve(),
        metadata={
            DEFAULT_METADATA_KEY: "SH-3 DevKit",
        },
    )


__all__: list[str] = [
    "ExecutionContext",
    "create_default_context",
]
