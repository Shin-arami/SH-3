from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class ProjectConfig:
    name: str
    version: str
    python: str
    architecture: str
    root: Path
