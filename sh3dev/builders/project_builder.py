from __future__ import annotations

from pathlib import Path


class ProjectBuilder:
    """Build SH-3 project artifacts."""

    def build(self, root: str = ".") -> dict[str, object]:
        base = Path(root).resolve()
        result: dict[str, object] = {
            "project": self._project_name(base),
            "structure": self._check_structure(base),
            "documents": self._check_documents(base),
            "status": "SUCCESS",
        }
        return result

    def _project_name(self, root: Path) -> str:
        """Resolve project name."""
        if root.name:
            return root.name
        return "SH-3"

    def _check_structure(self, root: Path) -> str:
        required = (
            "foundation",
            "runtime",
            "services",
            "kernel",
        )
        for item in required:
            if not (root / item).exists():
                return "FAILED"
        return "OK"

    def _check_documents(self, root: Path) -> str:
        if (root / "docs").exists():
            return "OK"
        return "FAILED"
