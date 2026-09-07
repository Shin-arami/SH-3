from __future__ import annotations

from kernel import SH3Kernel
from kernel.meta_controller import MetaController


def test_tune_policy_installs_default_rules_when_policy_is_small() -> None:
    kernel = SH3Kernel()
    controller = MetaController(kernel)

    controller.tune_policy(controller.observe())

    assert [rule.name for rule in kernel.policy.rules] == [
        "length_preference",
        "non_empty_bias",
        "shortness_bias",
    ]


def test_run_cycle_observes_and_heals_low_health_state() -> None:
    kernel = SH3Kernel()

    result = MetaController(kernel).run_cycle()

    assert result["action"] == "heal"
    assert result["result"] == "heal_triggered"
    assert result["snapshot"]["kernel"]["depth"] == 0
