# SH-3 Foundation Utilities

## Purpose

This document defines the utility-layer contract of SH-3 Foundation.

Utilities provide small, reusable, deterministic operations that do not belong to higher-level domain components.

## Principles

- Utilities have narrow responsibilities.
- Utilities are deterministic.
- Utilities are side-effect free where practical.
- Utilities are independently testable.
- Utilities contain no domain orchestration.

## Utility Categories

```text
Normalization
Validation Helpers
Serialization Helpers
Comparison
Collection Helpers
Identifier Helpers
Time Helpers
String Helpers
```

## Normalization

Normalization converts equivalent input representations into canonical representations and should be deterministic, documented, and idempotent.

```text
normalize(normalize(x)) == normalize(x)
```

## Validation Helpers

Validation utilities perform reusable structural checks. Domain-specific validation belongs in the appropriate higher layer.

## Serialization Helpers

Serialization helpers define input type, output representation, encoding, failure behavior, and compatibility.

## Collection Helpers

Collection utilities preserve explicit type information and predictable ordering semantics. They must not silently change ordering unless ordering behavior is part of the contract.

## Identifier Helpers

Identifier generation specifies format, uniqueness, determinism, and scope.

## Time Utilities

Time-sensitive utilities distinguish wall-clock time, monotonic time, and logical time. Elapsed-duration measurement should prefer monotonic time.

## Thread Safety

Shared utility functions should be safe for concurrent use. Mutable module-level state is prohibited unless explicitly synchronized and justified.

## Side Effects

Utilities should avoid network access, database access, global mutation, hidden file I/O, and implicit logging. Such behavior belongs in Infrastructure or higher layers.

## Error Handling

Utilities should raise Foundation exceptions when a failure belongs to a defined SH-3 error contract.

## API Stability

Frequently reused utilities are high-impact dependencies and should be changed conservatively.

## Anti-Patterns

- God utility modules
- Hidden global state
- Domain orchestration
- Provider-specific behavior
- Non-deterministic output without explicit contract
- Silent data loss
- Hidden I/O
- Catch-and-ignore error handling

## Completion Criteria

Foundation Utilities are complete when each utility has a narrow contract, deterministic behavior, explicit typing, defined failure semantics, and independent tests.

---

# End of Document
