from __future__ import annotations

from pathlib import Path
from typing import ClassVar


class Bootstrap:
    """
    Generate SH-3 bootstrap files.
    """

    FILES: ClassVar[dict[str, str]] = {
        ".github/workflows/ci.yml": """name: SH-3 CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python -m pytest
""",
        ".github/ISSUE_TEMPLATE/feature.md": """# Feature Request

## Description

Describe the feature.

## Specification

-

## Validation

-
""",
        "docs/rfc/rfc-0001-foundation.md": """# RFC-0001 Foundation

Category:

Core RFC


## Purpose

Define SH-3 Foundation layer.


## Status

Draft
""",
    "tests/test_import.py": """def test_import() -> None:
        import sh3dev
""",
    }

    def generate(
        self,
        root: str,
    ) -> list[str]:

        base = Path(root)

        created: list[str] = []

        for path, content in self.FILES.items():
            target = base / path

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            if not target.exists():
                target.write_text(
                    content,
                    encoding="utf-8",
                )

            created.append(str(target))

        return created

BootstrapGenerator = Bootstrap

__all__ = [
    "Bootstrap",
    "BootstrapGenerator",
]
