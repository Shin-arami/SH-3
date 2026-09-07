from __future__ import annotations

from pathlib import Path

from sh3dev.integrations import (
    GitHubIssue,
)


class GitHubIssueGenerator:
    """
    Generate GitHub Issue documents.
    """

    def generate(
        self,
        issue: GitHubIssue,
        output: str,
    ) -> Path:

        target = Path(output)

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        content = f"# {issue.title}\n\n{issue.body}\n\n## Labels\n\n" + "\n".join(
            f"- {label}" for label in issue.labels
        )

        target.write_text(
            content,
            encoding="utf-8",
        )

        return target
