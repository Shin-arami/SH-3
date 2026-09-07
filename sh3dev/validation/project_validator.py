from __future__ import annotations

from pathlib import Path


class ProjectValidator:
    """
    Validate SH-3 project structure.
    """

    REQUIRED_DIRECTORIES = (
        "foundation",
        "infrastructure",
        "runtime",
        "services",
        "kernel",
        "persistence",
        "self_healing",
        "docs",
        "tests",
    )

    REQUIRED_FILES = (
        "README.md",
        "pyproject.toml",
    )

    def validate(
        self,
        root: str = ".",
    ) -> dict[str, object]:
        base = Path(root)

        missing_directories = [
            directory for directory in self.REQUIRED_DIRECTORIES if not (base / directory).exists()
        ]

        missing_files = [file for file in self.REQUIRED_FILES if not (base / file).exists()]

        return {
            "valid": (not missing_directories and not missing_files),
            "missing_directories": (missing_directories),
            "missing_files": (missing_files),
        }
