from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(
    frozen=True,
    slots=True,
)
class TemplateEntry:
    """
    Template metadata.
    """

    name: str
    path: str
    category: str


class TemplateRegistry:
    """
    Manage SH-3 templates.
    """

    def __init__(
        self,
        root: str = "sh3dev/templates",
    ) -> None:

        self._root = Path(root)

    def list(
        self,
    ) -> list[TemplateEntry]:

        if not self._root.exists():
            return []

        result: list[TemplateEntry] = []

        for file in self._root.rglob(
            "*.md",
        ):
            relative = file.relative_to(
                self._root,
            )

            category = str(relative.parent) if str(relative.parent) != "." else "core"

            result.append(
                TemplateEntry(
                    name=file.stem,
                    path=str(file),
                    category=category,
                )
            )

        return result
