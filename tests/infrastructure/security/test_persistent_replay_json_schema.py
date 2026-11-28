from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from foundation.utils.hash import short_id
from infrastructure.security import EvidenceRecord
from infrastructure.security.persistent_replay_ops import main
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "operations"
    / "schemas"
    / "persistent-replay-report-v1.schema.json"
)


def _load_schema() -> dict[str, Any]:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(schema, dict)
    return schema


def _schema_type_matches(instance: object, expected: object) -> bool:
    allowed_types = expected if isinstance(expected, list) else [expected]
    for type_name in allowed_types:
        if type_name == "object" and isinstance(instance, dict):
            return True
        if type_name == "array" and isinstance(instance, list):
            return True
        if type_name == "string" and isinstance(instance, str):
            return True
        if type_name == "integer" and isinstance(instance, int) and not isinstance(instance, bool):
            return True
        if type_name == "number" and isinstance(instance, (int, float)) and not isinstance(instance, bool):
            return True
        if type_name == "boolean" and isinstance(instance, bool):
            return True
        if type_name == "null" and instance is None:
            return True
    return False


def _validate_schema(
    instance: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str = "$",
) -> list[str]:
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/"):
            return [f"{path}: only local JSON Schema references are supported in this test"]
        target: Any = root_schema
        for part in reference[2:].split("/"):
            if not isinstance(target, dict) or part not in target:
                return [f"{path}: unresolved schema reference {reference}"]
            target = target[part]
        if not isinstance(target, dict):
            return [f"{path}: schema reference is not an object"]
        return _validate_schema(instance, target, root_schema, path)

    if "oneOf" in schema:
        branches = schema["oneOf"]
        matches = sum(
            not _validate_schema(instance, branch, root_schema, path)
            for branch in branches
        )
        return [] if matches == 1 else [f"{path}: expected exactly one oneOf schema to match; got {matches}"]

    errors: list[str] = []
    # JSON Schema conditional keywords used by the published contract.
    if "allOf" in schema:
        for subschema in schema["allOf"]:
            errors.extend(_validate_schema(instance, subschema, root_schema, path))
    if "if" in schema:
        condition = schema["if"]
        if isinstance(condition, dict):
            branch = "then" if not _validate_schema(instance, condition, root_schema, path) else "else"
            selected = schema.get(branch)
            if isinstance(selected, dict):
                errors.extend(_validate_schema(instance, selected, root_schema, path))
    if "not" in schema:
        forbidden = schema["not"]
        if isinstance(forbidden, dict) and not _validate_schema(instance, forbidden, root_schema, path):
            errors.append(f"{path}: instance matches a forbidden schema")
    if "type" in schema and not _schema_type_matches(instance, schema["type"]):
        return [f"{path}: does not match type {schema['type']!r}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value is outside the allowed enum")
    if isinstance(instance, str) and "minLength" in schema and len(instance) < schema["minLength"]:
        errors.append(f"{path}: string is shorter than minLength")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool) and "minimum" in schema and instance < schema["minimum"]:
        errors.append(f"{path}: number is below minimum")
    if isinstance(instance, dict):
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            errors.append(f"{path}: object has too many properties")
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in instance:
                errors.extend(
                    _validate_schema(instance[key], child_schema, root_schema, f"{path}.{key}")
                )
        if schema.get("additionalProperties") is False:
            extras = set(instance) - set(properties)
            errors.extend(f"{path}: unexpected property {key!r}" for key in sorted(extras))
    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(
                _validate_schema(item, schema["items"], root_schema, f"{path}[{index}]")
            )
    return errors


def _read_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _assert_report_matches_schema(report: dict[str, Any], schema: dict[str, Any]) -> None:
    errors = _validate_schema(report, schema, schema)
    assert not errors, "JSON report violates the published schema:\n" + "\n".join(errors)


def _initialize_database(path: Path) -> None:
    SQLiteEvidenceStore(path)
    SQLiteReplayClaimStore(path)


def test_published_schema_accepts_success_reports_for_all_commands(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _load_schema()
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    _initialize_database(source)

    commands = (
        ["check", "--database", str(source), "--json"],
        ["backup", "--database", str(source), "--destination", str(backup), "--json"],
        ["restore", "--backup", str(backup), "--destination", str(restored), "--json"],
    )
    for command in commands:
        assert main(command) == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out.count("\n") == 1
        report = _read_report(captured.out)
        assert report["exit_code"] == 0
        _assert_report_matches_schema(report, schema)


def test_published_schema_accepts_error_reports_for_all_commands(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _load_schema()
    source = tmp_path / "source.sqlite3"
    existing_destination = tmp_path / "existing.sqlite3"
    _initialize_database(source)
    existing_destination.write_bytes(b"preserve-existing-file")
    missing_backup = tmp_path / "missing-private-backup.sqlite3"

    commands = (
        ["check", "--database", str(tmp_path / "missing.sqlite3"), "--json"],
        ["backup", "--database", str(source), "--destination", str(existing_destination), "--json"],
        ["restore", "--backup", str(missing_backup), "--destination", str(tmp_path / "restored.sqlite3"), "--json"],
    )
    for command in commands:
        assert main(command) == 1
        captured = capsys.readouterr()
        assert captured.out.count("\n") == 1
        report = _read_report(captured.out)
        assert report["exit_code"] == 1
        assert captured.err.startswith("ERROR:")
        _assert_report_matches_schema(report, schema)

    assert existing_destination.read_bytes() == b"preserve-existing-file"


def test_published_schema_rejects_unversioned_fields_and_invalid_exit_code() -> None:
    schema = _load_schema()
    success_schema = schema["$defs"]["success"]
    sample: dict[str, Any] = {
        "schema_version": 1,
        "action": "check",
        "database": "state.sqlite3",
        "sqlite_version": "3.45.0",
        "journal_mode": "wal",
        "integrity_status": "pass",
        "evidence_records": 0,
        "replay_claims": 0,
        "expired_claims": 0,
        "pending_evidence_reconciliation": 0,
        "policy_gates": {},
        "exit_code": 0,
    }
    assert not _validate_schema(sample, success_schema, schema)

    invalid_exit = dict(sample, exit_code=1)
    assert _validate_schema(invalid_exit, success_schema, schema)

    invalid_extra = dict(sample, undocumented_future_field=True)
    assert _validate_schema(invalid_extra, success_schema, schema)


def test_schema_enforces_policy_gate_exit_code_consistency() -> None:
    schema = _load_schema()
    base: dict[str, Any] = {
        "schema_version": 1,
        "action": "check",
        "database": "state.sqlite3",
        "sqlite_version": "3.45.0",
        "journal_mode": "wal",
        "integrity_status": "pass",
        "evidence_records": 0,
        "replay_claims": 0,
        "expired_claims": 0,
        "pending_evidence_reconciliation": 0,
        "policy_gates": {},
        "exit_code": 0,
    }
    valid_cases: tuple[tuple[dict[str, str], int], ...] = (
        ({}, 0),
        ({"pending_reconciliation": "pass"}, 0),
        ({"expired_claims": "pass"}, 0),
        ({"pending_reconciliation": "pass", "expired_claims": "pass"}, 0),
        ({"pending_reconciliation": "fail"}, 2),
        ({"pending_reconciliation": "fail", "expired_claims": "fail"}, 2),
        ({"expired_claims": "fail"}, 3),
        ({"pending_reconciliation": "pass", "expired_claims": "fail"}, 3),
    )
    for gates, exit_code in valid_cases:
        report = dict(base, policy_gates=gates, exit_code=exit_code)
        assert not _validate_schema(report, schema, schema), (gates, exit_code)

    invalid_cases: tuple[tuple[dict[str, str], int], ...] = (
        ({"pending_reconciliation": "fail"}, 0),
        ({"expired_claims": "fail"}, 0),
        ({"expired_claims": "fail"}, 2),
        ({"pending_reconciliation": "pass"}, 2),
        ({}, 2),
        ({}, 3),
        ({"pending_reconciliation": "fail", "expired_claims": "fail"}, 3),
    )
    for gates, exit_code in invalid_cases:
        report = dict(base, policy_gates=gates, exit_code=exit_code)
        assert _validate_schema(report, schema, schema), (gates, exit_code)


# PART11_40_RUNTIME_POLICY_GATE_SCHEMA_CONTRACT

def _initialize_expired_claim(path: Path) -> None:
    _initialize_database(path)
    SQLiteReplayClaimStore(path).claim(
        "learning-cycle:part11-40-expired-claim",
        "sha256:part11-40-expired-claim",
        lease_seconds=5.0,
        now=datetime.now(UTC) - timedelta(seconds=60),
    )


def _initialize_claim_with_terminal_evidence(path: Path, *, expired: bool) -> None:
    _initialize_database(path)
    cycle_id = (
        "learning-cycle:part11-40-expired-pending"
        if expired
        else "learning-cycle:part11-40-active-pending"
    )
    result_id = f"result:{cycle_id}"
    now = datetime.now(UTC)
    claimed_at = now - timedelta(seconds=60) if expired else now
    lease_seconds = 5.0 if expired else 300.0
    SQLiteReplayClaimStore(path).claim(
        cycle_id,
        f"sha256:{cycle_id}",
        lease_seconds=lease_seconds,
        now=claimed_at,
    )
    evidence = EvidenceRecord.create(
        evidence_id=short_id(cycle_id, prefix="learning-closed-loop:"),
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id=result_id,
        version="1.1.0",
        trace_id=f"trace:{cycle_id}",
        collected_at=datetime.now(UTC).isoformat(),
        payload={"cycle_id": cycle_id, "result_id": result_id, "status": "completed"},
    )
    SQLiteEvidenceStore(path).register(evidence)


def _run_schema_checked_json_check(
    database: Path,
    flags: tuple[str, ...],
    *,
    expected_exit_code: int,
    expected_gates: dict[str, str],
    schema: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> str:
    exit_code = main(["check", "--database", str(database), "--json", *flags])
    captured = capsys.readouterr()
    assert exit_code == expected_exit_code
    assert captured.out.count("\n") == 1
    report = _read_report(captured.out)
    assert report["exit_code"] == exit_code
    assert report["policy_gates"] == expected_gates
    _assert_report_matches_schema(report, schema)
    return captured.err


def test_runtime_policy_gate_reports_conform_to_schema_for_pass_and_pending_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _load_schema()
    clean_database = tmp_path / "runtime-gates-pass.sqlite3"
    _initialize_database(clean_database)
    stderr = _run_schema_checked_json_check(
        clean_database,
        ("--fail-on-pending-reconciliation", "--fail-on-expired-claims"),
        expected_exit_code=0,
        expected_gates={"pending_reconciliation": "pass", "expired_claims": "pass"},
        schema=schema,
        capsys=capsys,
    )
    assert stderr == ""

    pending_database = tmp_path / "runtime-pending-active.sqlite3"
    _initialize_claim_with_terminal_evidence(pending_database, expired=False)
    stderr = _run_schema_checked_json_check(
        pending_database,
        ("--fail-on-pending-reconciliation", "--fail-on-expired-claims"),
        expected_exit_code=2,
        expected_gates={"pending_reconciliation": "fail", "expired_claims": "pass"},
        schema=schema,
        capsys=capsys,
    )
    assert "PENDING_RECONCILIATION_GATE: FAIL" in stderr
    assert "EXPIRED_CLAIM_GATE: FAIL" not in stderr


def test_runtime_policy_gate_reports_conform_to_schema_for_expired_and_combined_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _load_schema()
    expired_database = tmp_path / "runtime-expired-only.sqlite3"
    _initialize_expired_claim(expired_database)
    stderr = _run_schema_checked_json_check(
        expired_database,
        ("--fail-on-expired-claims",),
        expected_exit_code=3,
        expected_gates={"expired_claims": "fail"},
        schema=schema,
        capsys=capsys,
    )
    assert "EXPIRED_CLAIM_GATE: FAIL" in stderr
    assert "PENDING_RECONCILIATION_GATE: FAIL" not in stderr

    combined_database = tmp_path / "runtime-both-gates-fail.sqlite3"
    _initialize_claim_with_terminal_evidence(combined_database, expired=True)
    stderr = _run_schema_checked_json_check(
        combined_database,
        ("--fail-on-pending-reconciliation", "--fail-on-expired-claims"),
        expected_exit_code=2,
        expected_gates={"pending_reconciliation": "fail", "expired_claims": "fail"},
        schema=schema,
        capsys=capsys,
    )
    assert "PENDING_RECONCILIATION_GATE: FAIL" in stderr
    assert "EXPIRED_CLAIM_GATE: FAIL" in stderr

# PART11_45_JSON_SCHEMA_IDENTIFIER_DISCLOSURE_CONTRACT

def test_published_schema_accepts_redacted_and_explicit_pending_identifier_reports(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _load_schema()
    database = tmp_path / "schema-pending-identifiers.sqlite3"
    _initialize_database(database)
    cycle_id = "learning-cycle:schema-identifier-disclosure"
    result_id = "result:schema-identifier-disclosure"
    SQLiteReplayClaimStore(database).claim(
        cycle_id,
        "sha256:schema-identifier-disclosure",
        lease_seconds=5.0,
        now=datetime.now(UTC) - timedelta(seconds=60),
    )
    evidence_id = short_id(cycle_id, prefix="learning-closed-loop:")
    evidence = EvidenceRecord.create(
        evidence_id=evidence_id,
        kind="learning.closed_loop",
        source="kernel.learning_feedback_loop",
        subject_id=result_id,
        version="1.1.0",
        trace_id=f"trace:{cycle_id}",
        collected_at=datetime.now(UTC).isoformat(),
        payload={"cycle_id": cycle_id, "result_id": result_id, "status": "completed"},
    )
    SQLiteEvidenceStore(database).register(evidence)

    assert main(["check", "--database", str(database), "--json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    redacted_report = _read_report(captured.out)
    assert redacted_report["pending_evidence_reconciliation"] == 1
    assert "pending_reconciliations" not in redacted_report
    assert cycle_id not in captured.out
    assert evidence_id not in captured.out
    _assert_report_matches_schema(redacted_report, schema)

    assert main(
        [
            "check",
            "--database",
            str(database),
            "--json",
            "--include-pending-cycle-ids",
        ]
    ) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    disclosed_report = _read_report(captured.out)
    assert disclosed_report["pending_evidence_reconciliation"] == 1
    details = disclosed_report["pending_reconciliations"]
    assert len(details) == 1
    assert details[0]["cycle_id"] == cycle_id
    assert details[0]["evidence_id"] == evidence_id
    assert details[0]["lease_expired"] is True
    _assert_report_matches_schema(disclosed_report, schema)

# PART11_46_JSON_POLICY_GATE_DISCLOSURE_INVARIANCE

def test_pending_identifier_disclosure_does_not_change_policy_gate_result(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _load_schema()
    database = tmp_path / "policy-gate-disclosure-invariance.sqlite3"
    _initialize_claim_with_terminal_evidence(database, expired=False)
    cycle_id = "learning-cycle:part11-40-active-pending"
    evidence_id = short_id(cycle_id, prefix="learning-closed-loop:")
    arguments = [
        "check",
        "--database",
        str(database),
        "--json",
        "--fail-on-pending-reconciliation",
    ]

    assert main(arguments) == 2
    redacted_capture = capsys.readouterr()
    assert redacted_capture.out.count("\n") == 1
    assert cycle_id not in redacted_capture.out
    assert evidence_id not in redacted_capture.out
    assert "PENDING_RECONCILIATION_GATE: FAIL" in redacted_capture.err
    redacted_report = _read_report(redacted_capture.out)
    assert redacted_report["pending_evidence_reconciliation"] == 1
    assert redacted_report["policy_gates"] == {"pending_reconciliation": "fail"}
    assert redacted_report["exit_code"] == 2
    assert "pending_reconciliations" not in redacted_report
    _assert_report_matches_schema(redacted_report, schema)

    assert main([*arguments, "--include-pending-cycle-ids"]) == 2
    disclosed_capture = capsys.readouterr()
    assert disclosed_capture.out.count("\n") == 1
    assert disclosed_capture.err == redacted_capture.err
    disclosed_report = _read_report(disclosed_capture.out)
    assert disclosed_report["pending_evidence_reconciliation"] == 1
    assert disclosed_report["policy_gates"] == {"pending_reconciliation": "fail"}
    assert disclosed_report["exit_code"] == 2
    details = disclosed_report["pending_reconciliations"]
    assert len(details) == 1
    assert details[0]["cycle_id"] == cycle_id
    assert details[0]["evidence_id"] == evidence_id
    assert details[0]["lease_expired"] is False
    assert redacted_report == {
        key: value
        for key, value in disclosed_report.items()
        if key != "pending_reconciliations"
    }
    _assert_report_matches_schema(disclosed_report, schema)
