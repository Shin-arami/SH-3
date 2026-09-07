# SH-3 Foundation Enums

## Purpose

This document defines the enum contract for SH-3 Foundation.

Enums provide controlled finite sets of values for states, classifications, modes, and policy decisions.

## Principles

- Values have explicit semantic meaning.
- Enum members remain stable once published.
- Enums do not encode business behavior.
- Unknown external values are handled explicitly.
- Serialization representation is controlled.

## Enum Categories

```text
Lifecycle State
Execution State
Operation Mode
Severity
Priority
Status
Classification
Result
```

## Lifecycle Enums

Lifecycle states describe valid lifecycle conditions rather than implementation details.

Example:

```text
CREATED
ACTIVE
SUSPENDED
TERMINATED
```

## Severity

```text
INFO
LOW
MEDIUM
HIGH
CRITICAL
```

## Stability

Published enum values are compatibility-sensitive. Removing or renaming a value may break serialization, persistence, events, configuration, and external integrations.

## Unknown Values

External data containing unknown enum values must not be silently converted into an unrelated valid value. The contract must explicitly reject, preserve unknown state, or use a defined fallback.

## Serialization

Each serialized enum defines its canonical representation. Stable symbolic values are preferred over implementation-dependent numeric ordinals.

## Thread Safety

Enum values are immutable and safe to share across threads.

## Anti-Patterns

- Numeric magic values
- Implicit ordinal dependencies
- String comparisons replacing enum semantics
- Mutable enum state
- Provider-specific enums in Foundation

## Completion Criteria

Foundation Enums are complete when finite-state and classification contracts are explicit, stable, serializable where required, and independent of higher-layer behavior.

---

# End of Document
