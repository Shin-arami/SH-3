from infrastructure.security import EvidenceRecord, EvidenceStore


def test_evidence_record_hash_is_deterministic_and_verifiable() -> None:
    record = EvidenceRecord.create(evidence_id="ev-1", kind="security", source="ci", subject_id="sh3", payload={"result": "pass", "count": 3})
    assert record.integrity.startswith("sha256:")
    assert record.verify()
    assert record.to_dict()["payload"] == {"count": 3, "result": "pass"}


def test_evidence_store_rejects_tampered_record() -> None:
    record = EvidenceRecord.create(evidence_id="ev-2", kind="security", source="ci", subject_id="sh3", payload={"result": "pass"})
    tampered = EvidenceRecord(record.evidence_id, record.kind, record.source, record.subject_id, record.version, record.collected_at, {"result": "fail"}, record.trace_id, record.integrity)
    store = EvidenceStore()
    try:
        store.register(tampered)
    except ValueError as exc:
        assert "integrity" in str(exc)
    else:
        raise AssertionError("tampered evidence must be rejected")


def test_evidence_store_is_idempotent_for_identical_records() -> None:
    record = EvidenceRecord.create(evidence_id="ev-3", kind="security", source="ci", subject_id="sh3", collected_at="2026-09-01T00:00:00+00:00")
    store = EvidenceStore()
    assert store.register(record) is record
    assert store.register(record) == record
    assert store.verify("ev-3")
    assert store.records() == (record,)
