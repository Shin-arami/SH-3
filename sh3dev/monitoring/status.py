from __future__ import annotations

from pathlib import Path

from sh3dev.registry.rfc_registry import (
    RFCRegistry,
)


class StatusCollector:
    """
    Collect SH-3 project status.
    """

    def __init__(
        self,
    ) -> None:

        self._rfc_registry = RFCRegistry()

    def collect(
        self,
        root: str = ".",
    ) -> dict[str, object]:

        base = Path(root).resolve()

        return {
            "project": (
                self._project_name(
                    base,
                )
            ),
            "version": (
                self._version(
                    base,
                )
            ),
            "architecture": (
                self._architecture(
                    base,
                )
            ),
            "rfc": (self._rfc_count()),
            "modules": (
                self._modules(
                    base,
                )
            ),
            "validation": (
                self._validation(
                    base,
                )
            ),
        }

    def _project_name(
        self,
        root: Path,
    ) -> str:

        return root.name if root.name else "SH-3"

    def _version(
        self,
        root: Path,
    ) -> str:

        pyproject = root / "pyproject.toml"

        if not pyproject.exists():
            return "unknown"

        text = pyproject.read_text(
            encoding="utf-8",
        )

        for line in text.splitlines():
            if line.startswith("version"):
                return (
                    line.split(
                        "=",
                    )[1]
                    .strip()
                    .replace(
                        '"',
                        "",
                    )
                )

        return "unknown"

    def _architecture(
        self,
        root: Path,
    ) -> str:

        if (root / "docs" / "architecture").exists():
            return "Layered Kernel System"

        return "unknown"

    def _rfc_count(
        self,
    ) -> int:

        return len(self._rfc_registry.load())

    def _modules(
        self,
        root: Path,
    ) -> list[str]:

        modules = (
            "foundation",
            "infrastructure",
            "runtime",
            "services",
            "kernel",
            "persistence",
            "self_healing",
        )

        return [item for item in modules if (root / item).exists()]

    def _validation(
        self,
        root: Path,
    ) -> str:

        required = (
            "foundation",
            "runtime",
            "kernel",
        )

        for item in required:
            if not (root / item).exists():
                return "FAILED"

        return "PASS"
