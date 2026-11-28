from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

import infrastructure.security.persistent_replay_ops as replay_ops
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
)

_REQUIRED_INDEX = "sh3_replay_claims_state_idx"
_PROBE_INDEX = "sh3_replay_claims_part11_106_checkpoint_observation_probe_idx"
_SAVEPOINT = "part11_106_checkpoint_observation_scope"
_COLLISION_ATTEMPTS = 3
_MAX_USER_VERSION = 2_147_483_647
_WRITE_MARKER_DELTA = 106_106
_INNER_MARKER_DELTA = 106_906


def _initialize_database(database: Path) -> None:
    SQLiteEvidenceStore(database)
    SQLiteReplayClaimStore(database)


def _prepare_destination(
    source: Path,
    backup: Path,
    destination: Path,
    *,
    scenario: str,
) -> tuple[Path, ...]:
    if scenario == "backup-destination":
        replay_ops.backup_database(source, destination)
        return (source,)
    replay_ops.backup_database(source, backup)
    replay_ops.restore_database(backup, destination)
    return (source, backup)


def _set_wal_mode(database: Path) -> None:
    connection = sqlite3.connect(database, timeout=0.0, isolation_level=None)
    try:
        row = connection.execute("PRAGMA journal_mode = WAL").fetchone()
        assert row is not None
        assert str(row[0]).casefold() == "wal"
    finally:
        connection.close()


def _read_user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    assert row is not None
    return int(row[0])


def _has_index(connection: sqlite3.Connection, index_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
            (index_name,),
        ).fetchone()
        is not None
    )


def _claim_state_index_definition(
    connection: sqlite3.Connection,
) -> tuple[str, bool, bool, tuple[str, ...]]:
    owner_row = connection.execute(
        "SELECT tbl_name FROM sqlite_master "
        "WHERE type = 'index' AND name = ? COLLATE NOCASE",
        (_REQUIRED_INDEX,),
    ).fetchone()
    assert owner_row is not None
    index_row = next(
        row
        for row in connection.execute(
            "PRAGMA index_list(sh3_replay_claims)"
        ).fetchall()
        if str(row[1]).casefold() == _REQUIRED_INDEX.casefold()
    )
    columns = connection.execute(
        f"PRAGMA index_info({_REQUIRED_INDEX})"
    ).fetchall()
    return (
        str(owner_row[0]),
        bool(index_row[2]),
        bool(index_row[4]),
        tuple(str(row[2]) for row in columns),
    )


def _readiness_report(output: str) -> dict[str, Any]:
    report = json.loads(output)
    assert isinstance(report, dict)
    return report


def _expected_cli_report(
    database: Path,
    readiness: Any,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "action": "check",
        "database": str(database.resolve()),
        "sqlite_version": readiness.sqlite_version,
        "journal_mode": readiness.journal_mode,
        "integrity_status": "pass",
        "evidence_records": readiness.evidence_count,
        "replay_claims": readiness.replay_claim_count,
        "expired_claims": readiness.expired_claim_count,
        "pending_evidence_reconciliation": (
            readiness.pending_evidence_reconciliation_count
        ),
        "policy_gates": {},
        "exit_code": 0,
    }


def _residual_artifact_names(directory: Path, destination: Path) -> tuple[str, ...]:
    prefix = f".{destination.name}."
    return tuple(
        sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(prefix) and ".partial" in path.name
        )
    )


@pytest.mark.parametrize(
    "scenario",
    ("backup-destination", "restore-destination"),
    ids=("backup-destination", "restore-destination"),
)
def test_readiness_checks_remain_observational_between_external_wal_checkpoints(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    source = tmp_path / f"readiness-observation-{scenario}-source.sqlite3"
    backup = tmp_path / f"readiness-observation-{scenario}-backup.sqlite3"
    destination = tmp_path / f"readiness-observation-{scenario}-destination.sqlite3"
    _initialize_database(source)
    protected_sources = _prepare_destination(
        source,
        backup,
        destination,
        scenario=scenario,
    )
    protected_source_bytes = {path: path.read_bytes() for path in protected_sources}
    _set_wal_mode(destination)

    readiness = replay_ops.check_database(destination)
    assert readiness.journal_mode.casefold() == "wal"
    expected_report = _expected_cli_report(destination, readiness)
    canonical_definition = (
        "sh3_replay_claims",
        False,
        False,
        ("state", "lease_expires_at"),
    )
    original_marker_connection = sqlite3.connect(
        f"{destination.as_uri()}?mode=ro",
        uri=True,
        timeout=0.0,
        isolation_level=None,
    )
    try:
        original_marker = _read_user_version(original_marker_connection)
    finally:
        original_marker_connection.close()
    claim_count = readiness.replay_claim_count
    marker = (original_marker + _WRITE_MARKER_DELTA) % _MAX_USER_VERSION
    inner_marker = (marker + _INNER_MARKER_DELTA) % _MAX_USER_VERSION
    assert len({original_marker, marker, inner_marker}) == 3

    temporary_main = (
        tmp_path / f".{destination.name}.part11-106-checkpoint-observation.partial"
    )
    residual_contents = {
        temporary_main: b"part11-106 checkpoint-observation partial snapshot",
        Path(f"{temporary_main}-wal"): b"part11-106 checkpoint-observation WAL residue",
        Path(f"{temporary_main}-shm"): b"part11-106 checkpoint-observation SHM residue",
        Path(f"{temporary_main}-journal"): (
            b"part11-106 checkpoint-observation journal residue"
        ),
    }
    for artifact, contents in residual_contents.items():
        artifact.write_bytes(contents)
    residual_names_before = _residual_artifact_names(tmp_path, destination)
    assert residual_names_before == tuple(
        sorted(artifact.name for artifact in residual_contents)
    )

    reader = sqlite3.connect(destination, timeout=0.0, isolation_level=None)
    writer = sqlite3.connect(destination, timeout=0.0, isolation_level=None)
    checkpoint = sqlite3.connect(destination, timeout=0.0, isolation_level=None)
    reader_closed = False
    try:
        reader.execute("BEGIN")
        initial_claims = reader.execute(
            "SELECT COUNT(*) FROM sh3_replay_claims"
        ).fetchone()
        assert initial_claims is not None
        assert int(initial_claims[0]) == claim_count
        assert _read_user_version(reader) == original_marker
        assert _claim_state_index_definition(reader) == canonical_definition
        assert not _has_index(reader, _PROBE_INDEX)

        writer.execute("BEGIN IMMEDIATE")
        writer.execute(f"PRAGMA user_version = {marker}")
        writer.execute(
            f"CREATE INDEX {_PROBE_INDEX} "
            "ON sh3_replay_claims(lease_expires_at)"
        )
        assert writer.in_transaction
        assert _read_user_version(writer) == marker
        assert _has_index(writer, _PROBE_INDEX)

        collision_messages: list[str] = []
        for _ in range(_COLLISION_ATTEMPTS):
            writer.execute(f"SAVEPOINT {_SAVEPOINT}")
            writer.execute(f"PRAGMA user_version = {inner_marker}")
            with pytest.raises(
                sqlite3.OperationalError,
                match="already exists",
            ) as collision_error:
                writer.execute(
                    f"CREATE INDEX {_REQUIRED_INDEX} "
                    "ON sh3_replay_claims(lease_expires_at, state)"
                )
            collision_messages.append(str(collision_error.value))
            assert writer.in_transaction
            assert _read_user_version(writer) == inner_marker
            writer.execute(f"ROLLBACK TO SAVEPOINT {_SAVEPOINT}")
            writer.execute(f"RELEASE SAVEPOINT {_SAVEPOINT}")
            assert writer.in_transaction
            assert _read_user_version(writer) == marker
            assert _has_index(writer, _PROBE_INDEX)
            assert _claim_state_index_definition(writer) == canonical_definition
            row = writer.execute(
                "SELECT COUNT(*) FROM sh3_replay_claims"
            ).fetchone()
            assert row is not None
            assert int(row[0]) == claim_count
        assert len(set(collision_messages)) == 1

        # Capture the committed database image and current WAL after the writer
        # has staged uncommitted changes; observational checks must not alter either.
        database_bytes_before_checks = destination.read_bytes()
        wal_path = Path(f"{destination}-wal")
        wal_bytes_before_checks = wal_path.read_bytes() if wal_path.exists() else None
        assert wal_bytes_before_checks is not None

        reports: list[dict[str, Any]] = []
        for _ in range(3):
            current_readiness = replay_ops.check_database(destination)
            assert current_readiness == readiness
            assert destination.read_bytes() == database_bytes_before_checks
            assert wal_path.read_bytes() == wal_bytes_before_checks
            assert _read_user_version(reader) == original_marker
            assert not _has_index(reader, _PROBE_INDEX)
            assert _read_user_version(writer) == marker
            assert _has_index(writer, _PROBE_INDEX)
            assert _claim_state_index_definition(writer) == canonical_definition

        for _ in range(2):
            exit_code = replay_ops.main(
                ["check", "--database", str(destination), "--json"]
            )
            captured = capsys.readouterr()
            assert exit_code == 0
            assert captured.out.count("\n") == 1
            assert captured.err == ""
            report = _readiness_report(captured.out)
            assert report == expected_report
            assert destination.read_bytes() == database_bytes_before_checks
            assert wal_path.read_bytes() == wal_bytes_before_checks
            assert _read_user_version(reader) == original_marker
            assert not _has_index(reader, _PROBE_INDEX)
            reports.append(report)
        assert reports[0] == reports[1]

        # Readiness checks above did not commit, checkpoint, or repair anything.
        writer.execute("COMMIT")
        assert not writer.in_transaction
        assert _read_user_version(writer) == marker
        assert _has_index(writer, _PROBE_INDEX)
        assert _claim_state_index_definition(writer) == canonical_definition
        assert _read_user_version(reader) == original_marker
        assert not _has_index(reader, _PROBE_INDEX)

        # Run checkpoint modes on an independent connection, interleaved with
        # readiness observations. Every readiness call must be a read-only
        # observer of the state left by the preceding checkpoint attempt.
        checkpoint_modes = (
            "PASSIVE",
            "FULL",
            "RESTART",
            "TRUNCATE",
            "FULL",
            "RESTART",
            "TRUNCATE",
        )
        checkpoint_results: list[tuple[str, int, int, int]] = []
        checkpoint_cli_reports: list[dict[str, Any]] = []
        for attempt, mode in enumerate(checkpoint_modes):
            result = checkpoint.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
            assert result is not None
            assert len(result) == 3
            busy, log_frames, checkpointed_frames = (int(value) for value in result)
            assert log_frames >= 0
            assert 0 <= checkpointed_frames <= log_frames
            if mode == "PASSIVE":
                assert busy == 0
            else:
                assert busy == 1
                assert log_frames > 0
                assert checkpointed_frames < log_frames
            checkpoint_results.append((mode, busy, log_frames, checkpointed_frames))
            assert _read_user_version(reader) == original_marker
            assert not _has_index(reader, _PROBE_INDEX)
            assert _claim_state_index_definition(reader) == canonical_definition
            assert _read_user_version(writer) == marker
            assert _has_index(writer, _PROBE_INDEX)

            # The checkpoint itself may legitimately change database/WAL bytes.
            # Capture the post-checkpoint image and prove the readiness call does
            # not change either file while this WAL history remains active.
            database_bytes_before_readiness = destination.read_bytes()
            wal_path = Path(f"{destination}-wal")
            assert wal_path.is_file()
            wal_bytes_before_readiness = wal_path.read_bytes()
            current_readiness = replay_ops.check_database(destination)
            assert current_readiness == readiness
            assert destination.read_bytes() == database_bytes_before_readiness
            assert wal_path.read_bytes() == wal_bytes_before_readiness
            assert _read_user_version(reader) == original_marker
            assert not _has_index(reader, _PROBE_INDEX)
            assert _read_user_version(writer) == marker
            assert _has_index(writer, _PROBE_INDEX)

            if attempt % 2 == 0:
                database_bytes_before_cli = destination.read_bytes()
                wal_bytes_before_cli = wal_path.read_bytes()
                exit_code = replay_ops.main(
                    ["check", "--database", str(destination), "--json"]
                )
                captured = capsys.readouterr()
                assert exit_code == 0
                assert captured.out.count("\n") == 1
                assert captured.err == ""
                report = _readiness_report(captured.out)
                assert report == expected_report
                assert destination.read_bytes() == database_bytes_before_cli
                assert wal_path.read_bytes() == wal_bytes_before_cli
                assert _read_user_version(reader) == original_marker
                assert not _has_index(reader, _PROBE_INDEX)
                checkpoint_cli_reports.append(report)

            assert _residual_artifact_names(tmp_path, destination) == residual_names_before
            for artifact, contents in residual_contents.items():
                assert artifact.is_file()
                assert artifact.read_bytes() == contents
            for protected_source in protected_sources:
                assert protected_source.read_bytes() == protected_source_bytes[protected_source]

        assert len(checkpoint_results) == len(checkpoint_modes)
        assert [row[0] for row in checkpoint_results] == list(checkpoint_modes)
        assert checkpoint_cli_reports
        assert all(report == expected_report for report in checkpoint_cli_reports)

        reader.execute("ROLLBACK")
        assert not reader.in_transaction
        reader.close()
        reader_closed = True

        final_checkpoint = checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        assert final_checkpoint is not None
        assert tuple(int(value) for value in final_checkpoint) == (0, 0, 0)
        if wal_path.exists():
            assert wal_path.stat().st_size == 0
        assert _read_user_version(writer) == marker
        assert _has_index(writer, _PROBE_INDEX)
    finally:
        if not reader_closed:
            if reader.in_transaction:
                reader.execute("ROLLBACK")
            reader.close()
        if writer.in_transaction:
            writer.execute("ROLLBACK")
        checkpoint.close()
        writer.close()

    assert _residual_artifact_names(tmp_path, destination) == residual_names_before
    for artifact, contents in residual_contents.items():
        assert artifact.is_file()
        assert artifact.read_bytes() == contents
    for protected_source in protected_sources:
        assert protected_source.read_bytes() == protected_source_bytes[protected_source]

    committed_readiness = replay_ops.check_database(destination)
    assert committed_readiness == readiness
    stable_reports: list[dict[str, Any]] = []
    for _ in range(2):
        exit_code = replay_ops.main(
            ["check", "--database", str(destination), "--json"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.out.count("\n") == 1
        assert captured.err == ""
        report = _readiness_report(captured.out)
        assert report == expected_report
        stable_reports.append(report)
        assert _residual_artifact_names(tmp_path, destination) == residual_names_before
        for artifact, contents in residual_contents.items():
            assert artifact.read_bytes() == contents
        for protected_source in protected_sources:
            assert (
                protected_source.read_bytes() == protected_source_bytes[protected_source]
            )
    assert stable_reports[0] == stable_reports[1]
