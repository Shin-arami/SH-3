from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _arguments(command: str, source: Path, destination: Path) -> list[str]:
    if command == "backup":
        return [
            "backup",
            "--database",
            str(source),
            "--destination",
            str(destination),
            "--json",
        ]
    return [
        "restore",
        "--backup",
        str(source),
        "--destination",
        str(destination),
        "--json",
    ]


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_retry_after_post_publication_cleanup_failure_does_not_replace_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    source = tmp_path / f"retry-{command}-source.sqlite3"
    destination = tmp_path / f"retry-{command}-destination.sqlite3"
    _initialize_database(source)
    source_bytes_before = source.read_bytes()
    original_unlink = Path.unlink
    residual_sidecars: list[Path] = []
    cleanup_failure_injected = False

    def fail_first_wal_cleanup(path: Path, *, missing_ok: bool = False) -> None:
        nonlocal cleanup_failure_injected
        candidate = Path(path)
        is_temporary_artifact = (
            candidate.parent == destination.parent
            and candidate.name.startswith(f".{destination.name}.")
            and ".partial" in candidate.name
        )
        if (
            is_temporary_artifact
            and candidate.name.endswith(".partial-wal")
            and not cleanup_failure_injected
        ):
            cleanup_failure_injected = True
            candidate.write_text("injected residual WAL sidecar", encoding="utf-8")
            residual_sidecars.append(candidate)
            raise PermissionError("injected post-publication WAL cleanup denial")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_first_wal_cleanup)
    try:
        first_exit_code = replay_ops.main(_arguments(command, source, destination))
        first_capture = capsys.readouterr()

        assert cleanup_failure_injected
        assert first_exit_code == 1
        assert first_capture.out.count("\n") == 1
        assert _read_report(first_capture.out) == {
            "schema_version": 1,
            "action": command,
            "integrity_status": "error",
            "policy_gates": {},
            "error": {"code": "operating_system_error", "type": "OSError"},
            "exit_code": 1,
        }
        assert "snapshot was published, but temporary cleanup was incomplete" in (
            first_capture.err
        )
        assert "verify the destination before retrying" in first_capture.err.lower()
        assert source.is_file()
        assert source.read_bytes() == source_bytes_before
        assert destination.is_file()
        assert len(residual_sidecars) == 1
        assert residual_sidecars[0].read_text(encoding="utf-8") == (
            "injected residual WAL sidecar"
        )

        published_bytes = destination.read_bytes()
        published_report = replay_ops.check_database(destination)

        retry_exit_code = replay_ops.main(_arguments(command, source, destination))
        retry_capture = capsys.readouterr()

        assert retry_exit_code == 1
        assert retry_capture.out.count("\n") == 1
        retry_report = _read_report(retry_capture.out)
        assert retry_report["schema_version"] == 1
        assert retry_report["action"] == command
        assert retry_report["integrity_status"] == "error"
        assert retry_report["policy_gates"] == {}
        assert retry_report["exit_code"] == 1
        assert isinstance(retry_report["error"], dict)
        assert retry_report["error"]
        assert source.read_bytes() == source_bytes_before
        assert destination.read_bytes() == published_bytes
        assert destination.is_file()
        assert residual_sidecars[0].is_file()
        assert residual_sidecars[0].read_text(encoding="utf-8") == (
            "injected residual WAL sidecar"
        )

        retry_destination_report = replay_ops.check_database(destination)
        assert retry_destination_report.evidence_count == published_report.evidence_count
        assert retry_destination_report.replay_claim_count == published_report.replay_claim_count

        captured_text = first_capture.out + first_capture.err + retry_capture.out + retry_capture.err
        assert str(source) not in captured_text
        assert str(destination) not in captured_text
    finally:
        for sidecar in residual_sidecars:
            original_unlink(sidecar, missing_ok=True)
