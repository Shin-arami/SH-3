from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

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
