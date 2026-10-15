from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import (
    PersistentReplayReadinessError,
    backup_database,
    check_database,
    restore_database,
)
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _evidence(evidence_id: str = "learning-closed-loop:ops-check") -> EvidenceRecord:
    return EvidenceRecord.create(
        evidence_id=evidence_id,
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id="result:ops-check",
        version="1.1.0",
        trace_id="trace:ops-check",
        collected_at="2026-10-15T00:00:00+00:00",
        payload={"cycle_id": "learning-cycle:ops-check", "status": "completed"},
    )


def _seed_database(database: Path) -> None:
    SQLiteEvidenceStore(database).register(_evidence())
    old_time = datetime.now(UTC) - timedelta(seconds=10)
    SQLiteReplayClaimStore(database).claim(
        "learning-cycle:expired-ops-check",
        "sha256:ops-check",
        lease_seconds=1.0,
        now=old_time,
    )


def test_check_reports_counts_and_expired_claims(tmp_path: Path) -> None:
    database = tmp_path / "evidence.sqlite3"
    _seed_database(database)

    report = check_database(database)

    assert report.database_path == database.resolve()
    assert report.evidence_count == 1
    assert report.replay_claim_count == 1
    assert report.expired_claim_count == 1
    assert report.sqlite_version
    assert report.journal_mode in {
        "wal",
        "delete",
        "truncate",
        "persist",
        "memory",
        "off",
    }


def test_check_fails_closed_on_application_evidence_tampering(tmp_path: Path) -> None:
    database = tmp_path / "evidence.sqlite3"
    _seed_database(database)
    evidence = _evidence()

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT record_json FROM sh3_evidence_records WHERE evidence_id = ?",
            (evidence.evidence_id,),
        ).fetchone()
        assert row is not None
        payload = json.loads(row[0])
        payload["payload"]["status"] = "tampered"
        connection.execute(
            "UPDATE sh3_evidence_records SET record_json = ? WHERE evidence_id = ?",
            (
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                evidence.evidence_id,
            ),
        )

    with pytest.raises(PersistentReplayReadinessError, match="application integrity"):
        check_database(database)


def test_backup_and_restore_create_verified_non_overwriting_copies(
    tmp_path: Path,
) -> None:
    database = tmp_path / "evidence.sqlite3"
    backup = tmp_path / "backups" / "evidence-backup.sqlite3"
    restored = tmp_path / "recovered" / "evidence-restored.sqlite3"
    _seed_database(database)

    backup_report = backup_database(database, backup)
    restore_report = restore_database(backup, restored)

    assert backup_report.evidence_count == 1
    assert backup_report.replay_claim_count == 1
    assert restore_report.evidence_count == 1
    assert restore_report.replay_claim_count == 1
    assert check_database(restored).expired_claim_count == 1
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        restore_database(backup, restored)


def test_backup_refuses_to_overwrite_existing_destination(tmp_path: Path) -> None:
    database = tmp_path / "evidence.sqlite3"
    destination = tmp_path / "existing-backup.sqlite3"
    _seed_database(database)
    destination.write_bytes(b"do-not-overwrite")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        backup_database(database, destination)

    assert destination.read_bytes() == b"do-not-overwrite"


def test_check_rejects_inconsistent_claim_ownership_state(tmp_path: Path) -> None:
    database = tmp_path / "evidence.sqlite3"
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database).claim(
        "learning-cycle:invalid-claim",
        "sha256:invalid-claim",
        lease_seconds=60.0,
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sh3_replay_claims SET owner_token = NULL "
            "WHERE cycle_id = ?",
            ("learning-cycle:invalid-claim",),
        )

    with pytest.raises(PersistentReplayReadinessError, match="no owner token"):
        check_database(database)
