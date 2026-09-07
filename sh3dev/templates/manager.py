from __future__ import annotations

from pathlib import Path

from sh3dev.templates.template_registry import (
    TemplateRegistry,
)


class TemplateManager:
    """
    Load and render templates.
    """

    def __init__(
        self,
        registry: TemplateRegistry | None = None,
    ) -> None:

        self._registry = registry if registry is not None else TemplateRegistry()

    def render(
        self,
        name: str,
        variables: dict[str, str],
    ) -> str:

        templates = self._registry.list()

        for template in templates:
            if template.name == name:
                content = Path(template.path).read_text(
                    encoding="utf-8",
                )

                return content.format(
                    **variables,
                )

        raise FileNotFoundError(f"Template not found: {name}")
