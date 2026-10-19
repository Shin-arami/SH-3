from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_MODULE = "infrastructure.security.persistent_replay_ops"


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", _MODULE, *arguments],
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


@pytest.mark.parametrize(
    "arguments",
    (
        ("check", "--json"),
        (
            "check",
            "--database",
            "unused.sqlite3",
            "--json",
            "--timeout-seconds",
            "not-a-number",
        ),
        ("backup", "--database", "unused.sqlite3", "--json"),
        (
            "restore",
            "--backup",
            "unused-backup.sqlite3",
            "--destination",
            "unused-restore.sqlite3",
            "--timeout-seconds",
            "not-a-number",
            "--json",
        ),
    ),
    ids=(
        "check-missing-required-database",
        "check-invalid-timeout",
        "backup-missing-required-destination",
        "restore-invalid-timeout",
    ),
)
def test_argparse_usage_errors_are_not_operation_json_envelopes(
    arguments: tuple[str, ...],
) -> None:
    result = _run_cli(*arguments)

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.lower().startswith("usage:")
    assert "error:" in result.stderr.lower()
    assert "traceback" not in result.stderr.lower()

# PART11_51_PARSE_ERROR_DISCLOSURE_INVARIANCE

@pytest.mark.parametrize(
    "arguments",
    (
        ("check", "--json"),
        (
            "check",
            "--database",
            "private-parse-error.sqlite3",
            "--json",
            "--timeout-seconds",
            "not-a-number",
        ),
    ),
    ids=("missing-required-database", "invalid-timeout-conversion"),
)
def test_argparse_usage_error_is_invariant_under_pending_identifier_disclosure(
    arguments: tuple[str, ...],
) -> None:
    redacted = _run_cli(*arguments)
    disclosed = _run_cli(*arguments, "--include-pending-cycle-ids")

    assert redacted.returncode == disclosed.returncode == 2
    assert redacted.stdout == disclosed.stdout == ""
    assert redacted.stderr == disclosed.stderr
    assert redacted.stderr.lower().startswith("usage:")
    assert "error:" in redacted.stderr.lower()
    assert "traceback" not in redacted.stderr.lower()
    assert "private-parse-error.sqlite3" not in redacted.stderr
