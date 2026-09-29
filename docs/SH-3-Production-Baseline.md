# SH-3 Complete Edition v2.0 — Production Baseline

## Baseline Identity

- Product: SH-3 Complete Edition v2.0
- Package: sh3 2.1.0
- Runtime: Python 3.12+
- Event Schema: 1.0.0
- Evidence Schema: 1.0.0
- Baseline Status: Production Ready / Validated
- Certification Date: 2026-09-27

## Certified Validation Gates

| Gate | Result |
|---|---|
| Ruff | PASS |
| mypy | PASS — 228 source files |
| Full pytest | PASS — 656 passed |
| DeprecationWarning gate | PASS — 656 passed |
| Build | PASS — sdist + wheel |
| Wheel installation | PASS — sh3 2.1.0 |
| Version governance | PASS |
| P0 remediation | CLOSED |
| P1 remediation | CLOSED |
| P2 remediation | CLOSED |

## Baseline Scope

This baseline covers the validated repository/runtime scope:

- Foundation / Types / Utils / Enums / Exceptions
- Infrastructure / EventBus / Events / Storage / Logging / Metrics / Tracing
- Runtime / Execution Layer
- Services / Planner / Memory / Policy / Learning / Optimizer / Healing
- Kernel / ServiceManager boundary
- Deployment / lifecycle / rollback verification
- Event-driven cross-layer propagation
- Self-Healing → EventBus → LearningLoop integration
- Learning success semantics and strategy feedback
- Optimizer action execution and rollback
- Recovery evidence and SHA-256 integrity verification
- Package/product/event/evidence version governance
- Security and release workflows

## Certification Boundary

This baseline does not establish environment-specific guarantees for external IAM, externally managed immutable evidence storage, key-management infrastructure, or production traffic-switching policy.

## Change Control

Any material change to architecture, dependencies, security, deployment, configuration, runtime behavior, event contracts, or evidence contracts invalidates this baseline until the applicable validation gates are rerun.

## Baseline Freeze Procedure

1. Confirm `git status` is clean except for intentionally staged baseline documentation.
2. Run Ruff, mypy, full pytest, deprecation-warning gate, build, install, and version checks.
3. Commit the certified state.
4. Create and push the release tag `v2.1.0`.
5. Publish the release only from the validated commit/tag.
6. Preserve this document together with the Production Certification Evidence.

## Re-certification Trigger

Re-certification is required after material architecture, dependency, security, deployment, configuration, event-schema, evidence-schema, or runtime changes.
