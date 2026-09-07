# SH-3 Type System Guide

Version:
1.0.0

Status:
Developer Guide

Category:
Type System

---

# 1. Purpose

This document defines the type system guidelines for SH-3.

The objectives are:

- Ensure type safety
- Improve readability
- Support static analysis
- Enable safe extensibility
- Standardize API contracts

All public APIs in SH-3 shall follow these guidelines.

---

# 2. Type System Philosophy

SH-3 follows:

Everything Typed

+

Everything Explicit

+

Everything Verifiable

Type information is considered part of the public contract.

---

# 3. Python Version

Required:

Python 3.12+

The latest typing features should be preferred.

---

# 4. General Rules

Every public function, method, class attribute, and constant shall have explicit type annotations.

Example:

```python
def load(path: Path) -> Configuration:
    ...
```

Avoid implicit typing in public APIs.

---

# 5. Built-in Generic Types

Prefer built-in generics.

Good:

```python
list[str]
dict[str, int]
set[int]
tuple[int, str]
```

Avoid legacy forms:

```python
List[str]
Dict[str, int]
```

---

# 6. Protocols

Use `Protocol` to define behavioral contracts.

Example:

```python
class EventPublisher(Protocol):
    def publish(self, event: Event) -> None: ...
```

Preferred for dependency inversion.

---

# 7. Abstract Base Classes

Use `ABC` only when:

- Shared implementation is required.
- Lifecycle methods are provided.

Prefer `Protocol` for interface-only definitions.

---

# 8. Generics

Use generics to create reusable abstractions.

Example:

```python
T = TypeVar("T")

class Repository(Generic[T]):
    ...
```

Avoid untyped containers.

---

# 9. Type Variables

Recommended names:

```
T
KT
VT
E
R
```

Use bounded type variables when appropriate.

---

# 10. Dataclasses

Use:

```python
@dataclass(frozen=True)
```

for immutable value objects.

Mutable dataclasses require architectural justification.

---

# 11. TypedDict

Use `TypedDict` for:

- External JSON payloads
- Configuration dictionaries
- API request/response structures

Avoid `dict[str, Any]` when a fixed schema exists.

---

# 12. Enum

Use `Enum` for closed sets of values.

Example:

```python
class HealthStatus(Enum):
    HEALTHY = "healthy"
    FAILED = "failed"
```

Avoid raw string literals for state values.

---

# 13. Literal

Use `Literal` when only a few exact values are valid.

Example:

```python
Literal["json", "yaml"]
```

---

# 14. Optional

Prefer:

```python
str | None
```

instead of:

```python
Optional[str]
```

---

# 15. Union

Use the `|` operator.

Example:

```python
Path | str
```

instead of `Union[Path, str]`.

---

# 16. Result Pattern

Operations that may fail should return a structured result.

Recommended model:

```python
Result[T, E]
```

Where:

- `T` = success type
- `E` = error type

Avoid returning `(bool, value)` tuples.

---

# 17. Exception Typing

Raise specific exception classes.

Do not use:

```python
raise Exception(...)
```

Use domain-specific exceptions.

---

# 18. Configuration Types

Configuration objects should be represented as immutable models.

Preferred:

- dataclass
- Pydantic model (external boundaries)

Avoid untyped dictionaries internally.

---

# 19. Event Types

Every event shall have:

- Dedicated class
- Typed payload
- Immutable structure

Events should never be anonymous dictionaries.

---

# 20. API Models

Public APIs expose typed request and response models.

No public API shall return `Any`.

---

# 21. Dependency Injection

Dependencies should be typed by interface (`Protocol`) rather than implementation.

Example:

```python
class Planner:
    def __init__(self, memory: MemoryRepository):
        ...
```

---

# 22. Static Analysis

Every module must pass:

- MyPy
- Ruff
- Pyright (optional)

No ignored type errors without justification.

---

# 23. Serialization

Serialized models should preserve type information where practical.

Version fields are recommended for persisted schemas.

---

# 24. Anti-Patterns

Avoid:

- Any in public APIs
- Untyped collections
- Anonymous dictionaries
- Mutable shared models
- Runtime type guessing
- Duck typing without Protocol

---

# 25. Type Review Checklist

Reviewers verify:

- Complete annotations
- Correct interface usage
- Appropriate Protocol/ABC selection
- Immutable models where applicable
- Static analysis compliance

---

# 26. Compliance Checklist

The type system is compliant when:

- Public APIs are fully typed
- Protocols are used for contracts
- Immutable models are preferred
- Static analysis passes
- No unnecessary `Any` usage exists

---

# 27. Final Definition

The SH-3 Type System defines the mandatory typing rules that provide a safe, explicit, and maintainable foundation for the entire SH-3 AI Operating Framework.

---

# End of Document
