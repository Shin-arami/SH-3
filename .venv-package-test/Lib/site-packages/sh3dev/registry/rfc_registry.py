from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(
    frozen=True,
    slots=True,
)
class RFCEntry:
    """
    RFC metadata.
    """

    number: str
    title: str
    path: str
    status: str = "Draft"


class RFCRegistry:
    """
    Manage SH-3 RFC registry.
    """

    def __init__(
        self,
        path: str = "docs/rfc_registry.json",
    ) -> None:
        self._path = Path(path)

    def load(
        self,
    ) -> list[RFCEntry]:

        if not self._path.exists():
            return []

        data = json.loads(
            self._path.read_text(
                encoding="utf-8",
            )
        )

        return [RFCEntry(**item) for item in data]

    def save(
        self,
        entries: list[RFCEntry],
    ) -> None:

        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._path.write_text(
            json.dumps(
                [asdict(entry) for entry in entries],
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def add(
        self,
        entry: RFCEntry,
    ) -> None:

        entries = self.load()

        for current in entries:
            if current.number == entry.number:
                raise ValueError(f"RFC already exists: {entry.number}")

        entries.append(entry)

        self.save(
            entries,
        )
