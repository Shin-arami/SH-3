from infrastructure.events import EventPropagationContext
from self_healing import SelfHealingCore


def test_recovery_evidence_contains_failure_plan_and_attempts() -> None:
    healer = SelfHealingCore()
    snapshot = healer.detect(KeyError("missing"), {"component": "p1-7"})
    result = healer.recover(snapshot)
    evidence = healer.recovery_evidence()
    assert result["status"] == "fallback_used"
    assert evidence is not None
    assert evidence.kind == "recovery"
    assert evidence.source == "self-healing"
    assert evidence.trace_id == snapshot.trace_id
    assert evidence.verify()
    assert evidence.payload["failure"]["trace_id"] == snapshot.trace_id
    assert evidence.payload["plan"]["strategy"] == "fallback_default"
    assert evidence.payload["attempts"]


def test_recovery_evidence_is_registered_and_retrievable() -> None:
    healer = SelfHealingCore()
    snapshot = healer.detect(RuntimeError("failure"))
    healer.set_propagation_context(EventPropagationContext.create(correlation_id=snapshot.trace_id, trace_id=snapshot.trace_id))
    healer.recover(snapshot)
    evidence = healer.recovery_evidence()
    assert evidence is not None
    assert healer.evidence_store.get(evidence.evidence_id) == evidence
    assert healer.evidence_store.verify(evidence.evidence_id)
