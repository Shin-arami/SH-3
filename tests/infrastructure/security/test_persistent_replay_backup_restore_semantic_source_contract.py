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


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _initialize_semantically_corrupt_database(path: Path) -> None:
    SQLiteEvidenceStore(path)
    SQLiteReplayClaimStore(path)
    evidence = EvidenceRecord.create(
        evidence_id="learning-closed-loop:part11-59-semantic-source",
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id="result:part11-59-semantic-source",
        version="1.1.0",
        trace_id="trace:part11-59-semantic-source",
        collected_at=datetime.now(UTC).isoformat(),
        payload={
            "cycle_id": "learning-cycle:part11-59-semantic-source",
            "result_id": "result:part11-59-semantic-source",
            "status": "completed",
        },
    )
    SQLiteEvidenceStore(path).register(evidence)

    # Preserve SQLite validity and row/document metadata agreement while
    # breaking the application's evidence integrity digest.
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT record_json FROM sh3_evidence_records WHERE evidence_id = ?",
            (evidence.evidence_id,),
        ).fetchone()
        assert row is not None
        record = json.loads(str(row[0]))
        record["payload"]["status"] = "tampered"
        connection.execute(
            "UPDATE sh3_evidence_records SET record_json = ? WHERE evidence_id = ?",
            (
                json.dumps(record, sort_keys=True, separators=(",", ":")),
                evidence.evidence_id,
            ),
        )
    connection.close()


@pytest.mark.parametrize("command", ("backup", "restore"), ids=("backup", "restore"))
def test_semantically_corrupt_source_is_rejected_before_destination_preparation(
    tmp_path: Path,
    command: str,
) -> None:
    source = tmp_path / f"private-{command}-semantically-corrupt.sqlite3"
    _initialize_semantically_corrupt_database(source)
    original_source_bytes = source.read_bytes()

    destination_parent = tmp_path / "destination-parent-must-not-be-created"
    destination = destination_parent / f"{command}-destination.sqlite3"
    assert not destination_parent.exists()

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

    assert result.returncode == 1
    assert result.stdout.count("\n") == 1
    assert _read_report(result.stdout) == {
        "schema_version": 1,
        "action": command,
        "integrity_status": "error",
        "policy_gates": {},
        "error": {
            "code": "readiness_check_failed",
            "type": "PersistentReplayReadinessError",
        },
        "exit_code": 1,
    }
    assert result.stderr == (
        "ERROR: evidence row 1 failed application integrity verification\n"
    )
    assert str(source) not in result.stdout + result.stderr
    assert str(destination) not in result.stdout + result.stderr
    assert "traceback" not in result.stderr.lower()
    assert source.is_file()
    assert source.read_bytes() == original_source_bytes
    assert not destination_parent.exists()
    assert not destination.exists()
    assert not list(tmp_path.glob(f".{destination.name}.*.partial*"))
