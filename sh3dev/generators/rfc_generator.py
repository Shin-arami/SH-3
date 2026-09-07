from __future__ import annotations

from pathlib import Path


class RFCGenerator:
    """
    Generate SH-3 RFC documents.
    """

    def __init__(
        self,
        template_path: str = ("sh3dev/templates/rfc_template.md"),
    ) -> None:
        self._template_path = Path(template_path)

    def generate(
        self,
        number: str,
        title: str,
        output: str,
    ) -> Path:
        template = self._template_path.read_text(
            encoding="utf-8",
        )

        content = template.format(
            number=number,
            title=title,
        )

        target = Path(output)

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        target.write_text(
            content,
            encoding="utf-8",
        )

        return target
