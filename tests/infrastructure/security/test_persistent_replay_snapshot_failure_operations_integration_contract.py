from __future__ import annotations

from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_OPERATIONS = _REPOSITORY_ROOT / "docs" / "operations"


def test_failure_matrix_integrates_connection_and_cleanup_contracts() -> None:
    matrix = (_OPERATIONS / "part11-21-persistent-replay-failure-matrix.md").read_text(
        encoding="utf-8"
    )
    integration = (
        _OPERATIONS
        / "part11-141-persistent-replay-snapshot-failure-operations-integration.md"
    ).read_text(encoding="utf-8")
    lowered_matrix = matrix.casefold()
    for required in (
        "snapshot connection configuration or close failure",
        "source identity change before publication",
        "temporary cleanup and source-close failures",
        "part 11-132",
        "part 11-140",
    ):
        assert required in lowered_matrix
    for part in range(132, 141):
        assert f"Part 11-{part}" in integration


def test_runbook_distinguishes_published_and_unpublished_failures() -> None:
    runbook = (_OPERATIONS / "part11-22-persistent-replay-operations.md").read_text(
        encoding="utf-8"
    )
    integration = (
        _OPERATIONS
        / "part11-141-persistent-replay-snapshot-failure-operations-integration.md"
    ).read_text(encoding="utf-8")
    lowered = (runbook + "\n" + integration).casefold()
    for required in (
        "snapshot and connection lifecycle failure recovery",
        "snapshot was published, but temporary cleanup was incomplete",
        "fileexistserror",
        ".partial",
        "-wal",
        "-shm",
        "-journal",
        "do not overwrite",
        "retry",
    ):
        assert required in lowered
