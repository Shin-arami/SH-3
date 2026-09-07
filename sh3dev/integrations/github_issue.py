from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubIssue:
    """
    GitHub Issue metadata.
    """

    title: str
    body: str
    labels: tuple[str, ...]
