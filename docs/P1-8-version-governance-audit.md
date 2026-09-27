# SH-3 P1-8 Version Governance Audit

Version: 1.0.0
Status: Remediated
Scope: package, product edition, event schema, evidence schema, release metadata, and compatibility governance

## 1. Audit Decision

P1-8 is remediated. SH-3 now has an explicit version-governance source for package and contract versions, package metadata derives its version from the canonical source, runtime package version exposes the same value, and the release workflow rejects release-tag/package-version drift.

## 2. Findings

| ID | Area | Result | Priority | Finding |
|---|---|---|---|---|
| VER-P1-001 | Package version | PASS | P1 | `foundation.version.PACKAGE_VERSION` is the canonical package version source. |
| VER-P1-002 | Package metadata | PASS | P1 | `pyproject.toml` derives the package version from the canonical source through setuptools dynamic metadata. |
| VER-P1-003 | Runtime version | PASS | P1 | `sh3dev.__version__` exposes the canonical package version. |
| VER-P1-004 | Product/package distinction | PASS | P1 | Product Edition `2.0` and package release `2.1.0` are explicitly represented as separate governed identifiers. |
| VER-P1-005 | Event contract version | PASS | P1 | Event creation and schema registry use the canonical event schema version `1.0.0`. |
| VER-P1-006 | Evidence contract version | PASS | P1 | Evidence records use the canonical evidence schema version `1.0.0`. |
| VER-P1-007 | Release consistency | PASS | P1 | Published release tags are validated against the canonical package version. |
| VER-P1-008 | Semantic Versioning | PASS | P1 | Canonical package and contract versions are validated against SemVer syntax. |
| VER-P1-009 | Compatibility policy | PASS | P1 | Major/minor/patch semantics remain aligned with ADR-0017 and ADR-0024. |

## 3. Version Model

```text
Product Edition       2.0
        │
        └── SH-3 package release 2.1.0
                │
                ├── Event Schema 1.0.0
                └── Evidence Schema 1.0.0
```

The product edition identifies the governed SH-3 Complete Edition line; the package version identifies the independently releasable Python distribution. Contract versions evolve independently and are not silently coupled to the package release.

## 4. Compatibility Policy

- Major: breaking architectural or compatibility changes.
- Minor: backward-compatible capability additions.
- Patch: bug fixes and other non-breaking corrections.
- Major upgrades require migration guidance.
- Unsupported deployment version combinations must not be activated.

## 5. Validation

P1-8 dedicated tests must verify canonical package/runtime metadata, SemVer validation, contract-version defaults, and release-version consistency.

## 6. Closure Gate

P1-8 is fully closed when the user environment confirms:

- dedicated P1-8 tests PASS
- Ruff PASS
- mypy PASS
- full pytest PASS
- release workflow version validation remains valid
