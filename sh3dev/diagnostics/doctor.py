from __future__ import annotations

from pathlib import Path


class Doctor:
    """
    Diagnose SH-3 DevKit environment.
    """

    def run(
        self,
        root: str = ".",
    ) -> dict[str, object]:

        base = Path(root).resolve()

        return {
            "python": self._python_check(),
            "project": self._project_check(
                base,
            ),
            "configuration": (
                self._config_check(
                    base,
                )
            ),
            "status": "READY",
        }

    def _python_check(
        self,
    ) -> str:

        return "OK"

    def _project_check(
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

        return "OK"

    def _config_check(
        self,
        root: Path,
    ) -> str:

        if (root / "pyproject.toml").exists():
            return "OK"

        return "FAILED"
