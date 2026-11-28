from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_store import (
    ReplayClaimStatus,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)


def _evidence() -> EvidenceRecord:
    return EvidenceRecord.create(
        evidence_id="learning-closed-loop:lock-timeout",
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id="result:lock-timeout",
        version="1.1.0",
        trace_id="trace:lock-timeout",
        collected_at="2026-11-01T00:00:00+00:00",
        payload={"cycle_id": "learning-cycle:lock-timeout", "status": "completed"},
    )


def _hold_writer_lock(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        database,
        timeout=0.0,
        isolation_level=None,
    )
    connection.execute("BEGIN IMMEDIATE")
    assert connection.in_transaction
    return connection


def _release_writer_lock(connection: sqlite3.Connection) -> None:
    try:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
    finally:
        connection.close()


def test_evidence_registration_times_out_without_partial_row_and_retries(
    tmp_path: Path,
) -> None:
    database = tmp_path / "evidence.sqlite3"
    store = SQLiteEvidenceStore(database, timeout_seconds=0.05)
    evidence = _evidence()
    writer = _hold_writer_lock(database)
    try:
        with pytest.raises(sqlite3.OperationalError, match=r"locked|busy"):
            store.register(evidence)
    finally:
        _release_writer_lock(writer)

    assert store.get(evidence.evidence_id) is None
    assert store.count() == 0

    persisted = store.register(evidence)
    assert persisted == evidence
    assert store.get(evidence.evidence_id) == evidence
    assert store.count() == 1


def test_claim_creation_times_out_without_increment_and_retries_as_generation_one(
    tmp_path: Path,
) -> None:
    database = tmp_path / "claims.sqlite3"
    store = SQLiteReplayClaimStore(database, timeout_seconds=0.05)
    cycle_id = "learning-cycle:claim-timeout"
    fingerprint = "sha256:claim-timeout"
    writer = _hold_writer_lock(database)
    try:
        with pytest.raises(sqlite3.OperationalError, match=r"locked|busy"):
            store.claim(cycle_id, fingerprint, lease_seconds=60.0)
    finally:
        _release_writer_lock(writer)

    assert store.get(cycle_id) is None

    claim = store.claim(cycle_id, fingerprint, lease_seconds=60.0)
    assert claim.status is ReplayClaimStatus.CLAIMED
    assert claim.generation == 1
    assert claim.attempts == 1
    assert claim.owner_token is not None


def test_claim_completion_timeout_preserves_owner_and_retries_same_generation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "claims.sqlite3"
    store = SQLiteReplayClaimStore(database, timeout_seconds=0.05)
    cycle_id = "learning-cycle:complete-timeout"
    fingerprint = "sha256:complete-timeout"
    claim = store.claim(cycle_id, fingerprint, lease_seconds=60.0)
    assert claim.owner_token is not None
    assert claim.lease_expires_at is not None
    evidence_id = "learning-closed-loop:complete-timeout"

    writer = _hold_writer_lock(database)
    try:
        with pytest.raises(sqlite3.OperationalError, match=r"locked|busy"):
            store.complete(
                cycle_id,
                fingerprint,
                claim.owner_token,
                claim.generation,
                evidence_id,
            )
    finally:
        _release_writer_lock(writer)

    after_timeout = store.get(cycle_id)
    assert after_timeout is not None
    assert after_timeout.status is ReplayClaimStatus.CLAIMED
    assert after_timeout.owner_token == claim.owner_token
    assert after_timeout.generation == claim.generation
    assert after_timeout.attempts == claim.attempts
    assert after_timeout.lease_expires_at == claim.lease_expires_at
    assert after_timeout.evidence_id is None

    store.complete(
        cycle_id,
        fingerprint,
        claim.owner_token,
        claim.generation,
        evidence_id,
    )

    completed = store.get(cycle_id)
    assert completed is not None
    assert completed.status is ReplayClaimStatus.COMPLETED
    assert completed.generation == claim.generation
    assert completed.attempts == claim.attempts
    assert completed.owner_token is None
    assert completed.lease_expires_at is None
    assert completed.evidence_id == evidence_id
