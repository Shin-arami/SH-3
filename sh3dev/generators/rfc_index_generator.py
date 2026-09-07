from __future__ import annotations

from pathlib import Path

from sh3dev.registry.rfc_registry import RFCEntry


class RFCIndexGenerator:
    """
    Generate RFC index document.
    """

    def generate(
        self,
        entries: list[RFCEntry],
        output: str = "docs/rfc/index.md",
    ) -> Path:

        lines = [
            "# SH-3 RFC Index",
            "",
        ]

        for entry in entries:
            lines.append(f"- RFC-{entry.number} {entry.title} ({entry.status})")

        target = Path(output)

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        target.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

        return target
