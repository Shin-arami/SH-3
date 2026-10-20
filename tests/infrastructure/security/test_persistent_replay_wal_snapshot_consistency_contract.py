from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import check_database
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)

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


def _initialize_database(path: Path) -> None:
    SQLiteEvidenceStore(path)
    SQLiteReplayClaimStore(path)


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _wal_evidence() -> EvidenceRecord:
    cycle_id = "learning-cycle:part11-58-wal-snapshot"
    result_id = "result:part11-58-wal-snapshot"
    return EvidenceRecord.create(
        evidence_id="learning-closed-loop:part11-58-wal-snapshot",
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id=result_id,
        version="1.1.0",
        trace_id="trace:part11-58-wal-snapshot",
        collected_at=datetime.now(UTC).isoformat(),
        payload={"cycle_id": cycle_id, "result_id": result_id, "status": "completed"},
    )


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_snapshot_includes_committed_wal_data_and_cleans_temporary_sidecars(
    tmp_path: Path,
    command: str,
) -> None:
    source = tmp_path / f"wal-source-{command}.sqlite3"
    destination = tmp_path / f"wal-snapshot-{command}.sqlite3"
    _initialize_database(source)

    # Keep one connection open so committed WAL frames remain available to the
    # online snapshot while the main database file is not checkpointed.
    anchor = sqlite3.connect(source, isolation_level=None)
    try:
        mode_row = anchor.execute("PRAGMA journal_mode = WAL").fetchone()
        assert mode_row is not None
        assert str(mode_row[0]).lower() == "wal"
        anchor.execute("PRAGMA wal_autocheckpoint = 0")
        main_database_before_write = source.read_bytes()

        SQLiteEvidenceStore(source).register(_wal_evidence())

        wal_path = Path(f"{source}-wal")
        assert wal_path.is_file()
        assert wal_path.stat().st_size > 32
        assert source.read_bytes() == main_database_before_write

        if command == "backup":
            arguments = (
                "backup",
                "--database",
                str(source),
                "--destination",
                str(destination),
                "--json",
            )
        else:
            arguments = (
                "restore",
                "--backup",
                str(source),
                "--destination",
                str(destination),
                "--json",
            )

        result = _run_cli(*arguments)

        assert result.returncode == 0, result.stderr
        assert result.stderr == ""
        assert result.stdout.count("\n") == 1
        report = _read_report(result.stdout)
        assert report["action"] == command
        assert report["database"] == str(destination.resolve())
        assert report["integrity_status"] == "pass"
        assert report["evidence_records"] == 1
        assert report["replay_claims"] == 0
        assert report["exit_code"] == 0

        destination_report = check_database(destination)
        assert destination_report.evidence_count == 1
        assert destination_report.replay_claim_count == 0
        assert destination_report.pending_evidence_reconciliation_count == 0

        # The source remains hot in WAL mode until the anchor is closed.
        assert source.read_bytes() == main_database_before_write
        assert wal_path.is_file()
        assert wal_path.stat().st_size > 32

        # The private temporary main file and its -wal/-shm/-journal sidecars
        # must not be left behind after snapshot verification/publication.
        assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))
    finally:
        anchor.close()
