# SH-3 Foundation Types

## Purpose

This document defines the shared type-system contract of SH-3 Foundation.

Types provide explicit boundaries between components and prevent implicit data contracts.

## Principles

- Every public boundary is typed.
- Generic containers specify their element types.
- Optional values are explicit.
- Runtime behavior does not depend on ambiguous dynamic values.
- Serialization boundaries have explicit representations.

## Type Categories

```text
Identifiers
Primitive Aliases
Result Types
State Types
Event Types
Configuration Types
Metadata Types
Protocol Types
```

## Identifier Types

SH-3 identifiers should use dedicated semantic types where practical, including ComponentId, EventId, RequestId, ExecutionId, CorrelationId, TraceId, and SessionId.

## Result Types

Operations that can produce controlled success or failure should expose an explicit result contract. Exceptions remain appropriate for exceptional control-flow failures.

## Metadata

Metadata must remain serializable, deterministic, bounded, and traceable. It must not become an uncontrolled storage mechanism.

## Immutability

Foundation value objects should prefer immutable representations. Mutable shared state requires an explicit ownership model.

## Generic Types

Generic interfaces must preserve type information across API boundaries.

## Protocols

Structural interfaces should use protocol-style contracts when implementations must remain replaceable.

## Serialization

Serializable Foundation types define canonical representation, validation, versioning, and compatibility.

## Type Compatibility

Breaking type changes require impact analysis, migration strategy, version update, and test coverage.

## Anti-Patterns

- `Any` as a substitute for a real contract
- Untyped dictionaries at public boundaries
- Stringly-typed state machines
- Hidden nullable values
- Implicit serialization contracts
- Provider-specific types leaking into Foundation

## Completion Criteria

Foundation Types are complete when shared contracts are explicit, stable, fully typed, serializable where required, and independently testable.

---

# End of Document
