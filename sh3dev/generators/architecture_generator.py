from __future__ import annotations

from pathlib import Path


class ArchitectureGenerator:
    """
    Generate SH-3 architecture documents.
    """

    FILES = (
        "index.md",
        "layers.md",
        "dependency.md",
        "event-flow.md",
    )

    def __init__(
        self,
        template_root: str = ("sh3dev/templates/architecture"),
    ) -> None:

        self._template_root = Path(
            template_root,
        )

    def generate(
        self,
        output: str = ("docs/architecture"),
    ) -> list[Path]:

        target_root = Path(
            output,
        )

        target_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        created: list[Path] = []

        for filename in self.FILES:
            source = self._template_root / filename

            target = target_root / filename

            target.write_text(
                source.read_text(
                    encoding="utf-8",
                ),
                encoding="utf-8",
            )

            created.append(
                target,
            )

        return created
