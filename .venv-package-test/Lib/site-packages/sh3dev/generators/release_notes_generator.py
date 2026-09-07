from __future__ import annotations

from pathlib import Path


class ReleaseNotesGenerator:
    """
    Generate release notes.
    """

    def generate(
        self,
        report: dict[str, object],
        output: str = ("docs/release/release-notes.md"),
    ) -> Path:

        target = Path(output)

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        content = (
            "# SH-3 Release Notes\n\n"
            f"Project: {report['project']}\n\n"
            f"Version: {report['version']}\n\n"
            f"Build: {report['build']}\n\n"
            f"Validation: {report['validation']}\n\n"
            f"Status: {report['status']}\n"
        )

        target.write_text(
            content,
            encoding="utf-8",
        )

        return target
