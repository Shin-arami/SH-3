from __future__ import annotations

from pathlib import Path

from kernel import SH3Kernel
from persistence.core import PersistenceCore


def test_save_and_load_state_round_trip(tmp_path: Path) -> None:
    persistence = PersistenceCore(str(tmp_path))

    file_id = persistence.save_state("checkpoint", {"cycle": 3})

    loaded = persistence.load_state(file_id)

    assert loaded is not None
    assert loaded["name"] == "checkpoint"
    assert loaded["state"] == {"cycle": 3}
    assert loaded["version"] == 1
    assert loaded["timestamp"]


def test_restore_clears_context_through_context_manager_api(tmp_path: Path) -> None:
    kernel = SH3Kernel()
    kernel.context_manager.push("active")
    persistence = PersistenceCore(str(tmp_path))

    result = persistence.restore({"state": {"kernel": {"context": {}, "memory": {}}}}, kernel)

    assert result["status"] == "restored"
    assert kernel.context_manager.snapshot()["depth"] == 0
