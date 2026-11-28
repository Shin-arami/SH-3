from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from infrastructure.security.persistent_replay_ops import check_database
from infrastructure.security.persistent_replay_provision import (
    main,
    provision_persistent_replay_database,
)
from infrastructure.security.persistent_replay_runtime import (
    PERSISTENT_REPLAY_DATABASE_ENV,
    create_persistent_replay_stores,
)


def test_provision_requires_explicit_first_use_confirmation(tmp_path: Path) -> None:
    database = tmp_path / "evidence.sqlite3"

    with pytest.raises(ValueError, match="confirm_first_use=True"):
        provision_persistent_replay_database(database)

    assert not database.exists()


def test_provision_creates_valid_paired_schema_at_explicit_new_path(
    tmp_path: Path,
) -> None:
    database = tmp_path / "evidence.sqlite3"

    report = provision_persistent_replay_database(
        database,
        confirm_first_use=True,
    )

    assert report.database_path == database.resolve()
    assert report.evidence_count == 0
    assert report.replay_claim_count == 0
    assert report.expired_claim_count == 0
    assert database.is_file()

    stores = create_persistent_replay_stores(database)
    assert stores.database_path == database.resolve()
    assert stores.evidence_store.database_path == stores.database_path
    assert stores.replay_claim_store.database_path == stores.database_path
    assert check_database(database).evidence_count == 0


def test_provision_refuses_existing_file_without_modifying_contents(
    tmp_path: Path,
) -> None:
    database = tmp_path / "do-not-overwrite.sqlite3"
    original = b"operator-owned file; must remain byte-for-byte unchanged"
    database.write_bytes(original)

    with pytest.raises(FileExistsError, match="refusing to provision"):
        provision_persistent_replay_database(
            database,
            confirm_first_use=True,
        )

    assert database.read_bytes() == original


def test_provision_does_not_create_missing_parent_directory(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "missing-parent"
    database = parent / "evidence.sqlite3"

    with pytest.raises(FileNotFoundError, match="parent directory must already exist"):
        provision_persistent_replay_database(
            database,
            confirm_first_use=True,
        )

    assert not parent.exists()
    assert not database.exists()


def test_provision_resolves_database_path_from_environment(
    tmp_path: Path,
) -> None:
    database = tmp_path / "configured.sqlite3"

    report = provision_persistent_replay_database(
        confirm_first_use=True,
        environ={PERSISTENT_REPLAY_DATABASE_ENV: str(database)},
    )

    assert report.database_path == database.resolve()
    assert database.is_file()


def test_provision_cli_requires_confirmation_flag(tmp_path: Path) -> None:
    database = tmp_path / "cli.sqlite3"

    with pytest.raises(SystemExit) as captured:
        main(["--database", str(database)])

    assert captured.value.code == 2
    assert not database.exists()


def test_provision_cli_returns_nonzero_for_existing_path(
    tmp_path: Path,
    capsys: Any,
) -> None:
    database = tmp_path / "existing.sqlite3"
    database.write_bytes(b"keep me")

    result = main(
        ["--database", str(database), "--confirm-first-use"],
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "refusing to provision an existing database path" in captured.err
    assert database.read_bytes() == b"keep me"


def test_provision_cli_success_reports_ready_database(
    tmp_path: Path,
    capsys: Any,
) -> None:
    database = tmp_path / "cli-new.sqlite3"

    result = main(
        ["--database", str(database), "--confirm-first-use"],
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "PROVISION: PASS" in captured.out
    assert f"database={database.resolve()}" in captured.out
    assert check_database(database).evidence_count == 0
