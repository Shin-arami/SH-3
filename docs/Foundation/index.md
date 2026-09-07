# SH-3 Foundation

## Purpose

`docs/foundation/` defines the lowest-level architectural contracts shared by every SH-3 layer.

The Foundation layer contains:

- Types
- Enums
- Exceptions
- Utilities

## Dependency Rule

Foundation must not depend on higher SH-3 layers.

```text
Application
    ↓
Deployment
    ↓
Kernel
    ↓
Services
    ↓
Runtime
    ↓
Infrastructure
    ↓
Foundation
```

## Principles

- Fully Typed
- Deterministic
- Thread Safe
- Replaceable
- Testable
- No Runtime-Cycle Dependency
- No Business Logic Leakage

## Components

| Component | Responsibility |
|---|---|
| Types | Shared structural and semantic type contracts |
| Enums | Controlled finite-state and classification values |
| Exceptions | Typed failure contracts |
| Utils | Small deterministic infrastructure-independent helpers |

## Stability

Foundation APIs are high-impact contracts. Changes require compatibility analysis across the dependency graph.

## Forbidden Dependencies

Foundation must not depend on application modules, deployment modules, kernel services, runtime implementations, infrastructure implementations, or external provider-specific logic.

## Completion Criteria

Foundation is complete when Types, Enums, Exceptions, Utils, Tests, and Documentation are consistent, typed, deterministic, and independently testable.

---

# End of Document
