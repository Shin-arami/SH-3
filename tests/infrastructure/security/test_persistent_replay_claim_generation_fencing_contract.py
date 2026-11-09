from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from infrastructure.security.persistent_store import (
    ReplayClaimOwnershipError,
    ReplayClaimStatus,
    SQLiteReplayClaimStore,
)


def test_expired_owner_cannot_finalize_or_renew_after_new_generation_is_claimed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "claims.sqlite3"
    store = SQLiteReplayClaimStore(database)
    cycle_id = "learning-cycle:generation-fencing"
    fingerprint = "sha256:generation-fencing"
    first_time = datetime(2026, 11, 1, tzinfo=UTC)
    takeover_time = first_time + timedelta(seconds=6)

    first_owner = store.claim(
        cycle_id,
        fingerprint,
        lease_seconds=5.0,
        now=first_time,
    )
    assert first_owner.status is ReplayClaimStatus.CLAIMED
    assert first_owner.owner_token is not None
    assert first_owner.generation == 1
    assert first_owner.attempts == 1

    second_owner = store.claim(
        cycle_id,
        fingerprint,
        lease_seconds=30.0,
        now=takeover_time,
    )
    assert second_owner.status is ReplayClaimStatus.CLAIMED
    assert second_owner.owner_token is not None
    assert second_owner.owner_token != first_owner.owner_token
    assert second_owner.generation == 2
    assert second_owner.attempts == 2

    with pytest.raises(ReplayClaimOwnershipError, match="ownership was lost"):
        store.complete(
            cycle_id,
            fingerprint,
            first_owner.owner_token,
            first_owner.generation,
            "learning-closed-loop:stale-owner",
            now=takeover_time,
        )

    with pytest.raises(ReplayClaimOwnershipError, match="ownership was lost"):
        store.renew(
            cycle_id,
            fingerprint,
            first_owner.owner_token,
            first_owner.generation,
            lease_seconds=30.0,
            now=takeover_time,
        )

    assert not store.release(
        cycle_id,
        first_owner.owner_token,
        first_owner.generation,
        now=takeover_time,
    )

    current = store.get(cycle_id)
    assert current is not None
    assert current.status is ReplayClaimStatus.CLAIMED
    assert current.owner_token == second_owner.owner_token
    assert current.generation == second_owner.generation
    assert current.attempts == second_owner.attempts
    assert current.evidence_id is None

    evidence_id = "learning-closed-loop:current-owner"
    store.complete(
        cycle_id,
        fingerprint,
        second_owner.owner_token,
        second_owner.generation,
        evidence_id,
        now=takeover_time + timedelta(seconds=1),
    )

    completed = store.get(cycle_id)
    assert completed is not None
    assert completed.status is ReplayClaimStatus.COMPLETED
    assert completed.generation == 2
    assert completed.attempts == 2
    assert completed.owner_token is None
    assert completed.evidence_id == evidence_id

    with pytest.raises(ReplayClaimOwnershipError, match="ownership was lost"):
        store.complete(
            cycle_id,
            fingerprint,
            first_owner.owner_token,
            first_owner.generation,
            evidence_id,
            now=takeover_time + timedelta(seconds=2),
        )

def test_owner_cannot_renew_complete_or_release_at_exact_lease_expiry(
    tmp_path: Path,
) -> None:
    database = tmp_path / "claims-exact-expiry.sqlite3"
    store = SQLiteReplayClaimStore(database)
    cycle_id = "learning-cycle:exact-lease-expiry"
    fingerprint = "sha256:exact-lease-expiry"
    first_time = datetime(2026, 11, 1, tzinfo=UTC)
    expiry_time = first_time + timedelta(seconds=5)

    first_owner = store.claim(
        cycle_id,
        fingerprint,
        lease_seconds=5.0,
        now=first_time,
    )
    assert first_owner.owner_token is not None
    assert first_owner.lease_expires_at is not None

    with pytest.raises(ReplayClaimOwnershipError, match="lease expired"):
        store.renew(
            cycle_id,
            fingerprint,
            first_owner.owner_token,
            first_owner.generation,
            lease_seconds=30.0,
            now=expiry_time,
        )

    with pytest.raises(ReplayClaimOwnershipError, match="lease expired"):
        store.complete(
            cycle_id,
            fingerprint,
            first_owner.owner_token,
            first_owner.generation,
            "learning-closed-loop:expired-owner",
            now=expiry_time,
        )

    assert not store.release(
        cycle_id,
        first_owner.owner_token,
        first_owner.generation,
        now=expiry_time,
    )

    second_owner = store.claim(
        cycle_id,
        fingerprint,
        lease_seconds=30.0,
        now=expiry_time,
    )
    assert second_owner.status is ReplayClaimStatus.CLAIMED
    assert second_owner.generation == first_owner.generation + 1
    assert second_owner.owner_token is not None
    assert second_owner.owner_token != first_owner.owner_token

def test_reconciliation_cannot_complete_a_newer_generation_with_stale_evidence(
    tmp_path: Path,
) -> None:
    database = tmp_path / "claims-stale-evidence-generation.sqlite3"
    store = SQLiteReplayClaimStore(database)
    cycle_id = "learning-cycle:stale-evidence-generation"
    fingerprint = "sha256:stale-evidence-generation"
    first_time = datetime(2026, 11, 1, tzinfo=UTC)
    first_owner = store.claim(
        cycle_id,
        fingerprint,
        lease_seconds=5.0,
        now=first_time,
    )
    takeover_time = first_time + timedelta(seconds=6)
    second_owner = store.claim(
        cycle_id,
        fingerprint,
        lease_seconds=30.0,
        now=takeover_time,
    )
    assert second_owner.generation == first_owner.generation + 1

    with pytest.raises(ReplayClaimOwnershipError, match="ownership was lost"):
        store.reconcile_completed(
            cycle_id,
            fingerprint,
            "learning-closed-loop:old-generation-evidence",
            generation=first_owner.generation,
        )

    with pytest.raises(ReplayClaimOwnershipError, match="generation is required"):
        store.reconcile_completed(
            cycle_id,
            fingerprint,
            "learning-closed-loop:legacy-evidence-without-generation",
        )

    current = store.get(cycle_id)
    assert current is not None
    assert current.status is ReplayClaimStatus.CLAIMED
    assert current.generation == second_owner.generation
    assert current.owner_token == second_owner.owner_token

    store.reconcile_completed(
        cycle_id,
        fingerprint,
        "learning-closed-loop:current-generation-evidence",
        generation=second_owner.generation,
    )
    completed = store.get(cycle_id)
    assert completed is not None
    assert completed.status is ReplayClaimStatus.COMPLETED
    assert completed.generation == second_owner.generation
    assert completed.evidence_id == "learning-closed-loop:current-generation-evidence"

def test_legacy_reconciliation_rejects_same_evidence_from_completed_newer_generation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "claims-completed-generation-legacy-reconcile.sqlite3"
    store = SQLiteReplayClaimStore(database)
    cycle_id = "learning-cycle:completed-generation-legacy-reconcile"
    fingerprint = "sha256:completed-generation-legacy-reconcile"
    first_time = datetime(2026, 11, 1, tzinfo=UTC)

    first_owner = store.claim(
        cycle_id,
        fingerprint,
        lease_seconds=5.0,
        now=first_time,
    )
    takeover_time = first_time + timedelta(seconds=6)
    second_owner = store.claim(
        cycle_id,
        fingerprint,
        lease_seconds=30.0,
        now=takeover_time,
    )
    assert second_owner.generation == first_owner.generation + 1
    assert second_owner.owner_token is not None

    evidence_id = "learning-closed-loop:generation-two-evidence"
    store.complete(
        cycle_id,
        fingerprint,
        second_owner.owner_token,
        second_owner.generation,
        evidence_id,
        now=takeover_time + timedelta(seconds=1),
    )

    with pytest.raises(ReplayClaimOwnershipError, match="generation is required"):
        store.reconcile_completed(cycle_id, fingerprint, evidence_id)

    completed = store.get(cycle_id)
    assert completed is not None
    assert completed.status is ReplayClaimStatus.COMPLETED
    assert completed.generation == second_owner.generation
    assert completed.evidence_id == evidence_id
