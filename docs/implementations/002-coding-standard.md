# SH-3 Coding Standard Specification

Version:
1.0.0

Status:
Implementation Specification

Category:
Coding Standard

---

# 1. Purpose

This document defines the coding standards for implementing the SH-3 AI Operating Framework.

The objectives are:

- Maintain consistent source quality
- Improve readability
- Reduce implementation errors
- Ensure long-term maintainability
- Support automated validation

---

# 2. Coding Philosophy

SH-3 code follows:

```text
Readable

+

Predictable

+

Typed

+

Testable

+

Maintainable
```

Code should communicate design intent.

---

# 3. Language Requirements

Primary language:

```text
Python 3.12+
```

Required:

- Type annotations
- Modern syntax
- Explicit interfaces
- Structured exceptions

---

# 4. Code Quality Requirements

All code must satisfy:

```text
Ruff

↓

Mypy

↓

Tests

↓

Review
```

Code failing validation must not enter production.

---

# 5. Formatting Rules

Formatting standard:

- PEP 8 compatible
- Ruff formatter compatible
- Consistent indentation
- No unnecessary complexity

Recommended:

```text
Line length:
88 characters
```

---

# 6. Import Rules

Import order:

```python
# Standard Library

import asyncio

# Third Party

from pydantic import BaseModel

# SH-3 Internal

from SH3.foundation.types import Event
```

Rules:

- No wildcard imports
- No unused imports
- No circular imports

---

# 7. Naming Convention

## Modules

Use:

```text
snake_case
```

Example:

```text
event_bus.py
runtime_context.py
```

---

## Classes

Use:

```text
PascalCase
```

Example:

```python
class RuntimeContext:
    ...
```

---

## Functions

Use:

```text
snake_case
```

Example:

```python
def create_context():
    ...
```

---

## Constants

Use:

```text
UPPER_CASE
```

Example:

```python
DEFAULT_TIMEOUT = 30
```

---

# 8. Type Annotation Rules

All public APIs require annotations.

Example:

```python
def publish(event: Event) -> None:
    ...
```

Required:

- Parameters typed
- Return values typed
- Collections typed

---

# 9. Any Usage Policy

`Any` should be avoided.

Allowed only when:

- External API is dynamic
- Serialization boundary exists
- Type information is unavailable

Every use requires justification.

---

# 10. Class Design Rules

Classes should:

- Have one responsibility
- Expose clear interfaces
- Avoid hidden state
- Support testing

Avoid:

- God classes
- Excessive inheritance
- Mutable global state

---

# 11. Dataclass Rules

Dataclasses should be preferred for:

- Value objects
- Configuration models
- Immutable structures

Example:

```python
@dataclass(frozen=True)
class EventMetadata:
    event_id: str
```

---

# 12. Exception Handling Rules

Exceptions must be:

- Typed
- Meaningful
- Recoverable where possible

Example:

```python
class SH3RuntimeError(Exception):
    pass
```

Avoid:

```python
except Exception:
    pass
```

---

# 13. Logging Rules

Logging must:

Include:

- Component
- Operation
- Context

Example:

```python
logger.info(
    "runtime_started",
    extra={"component": "runtime"}
)
```

Do not log:

- Secrets
- Credentials
- Personal data

---

# 14. Async Programming Rules

Async code must:

- Avoid blocking calls
- Manage cancellation
- Handle exceptions

Example:

```python
async def start() -> None:
    ...
```

---

# 15. Thread Safety Rules

Shared state requires:

- Locks
- Queues
- Immutable structures

Avoid:

- Unprotected mutable globals
- Race conditions

---

# 16. Dependency Injection Rules

Dependencies should be injected.

Preferred:

```python
class Service:
    def __init__(self, storage: Storage):
        self.storage = storage
```

Avoid:

```python
storage = GlobalStorage()
```

---

# 17. Documentation Rules

Public classes and functions require:

- Purpose
- Parameters
- Return values
- Exceptions

Example:

```python
def load_config() -> Config:
    """
    Load validated configuration.

    Returns:
        Config instance.
    """
```

---

# 18. Comment Rules

Comments should explain:

- Why something exists
- Design decisions
- Constraints

Avoid comments that repeat code.

Bad:

```python
# increment counter
counter += 1
```

---

# 19. Testability Rules

Code should support:

- Dependency replacement
- Unit testing
- Deterministic execution

Avoid:

- Hidden environment dependencies
- Time-dependent behavior
- Random behavior

---

# 20. File Size Guidelines

Recommended:

- Small focused modules
- Clear responsibilities

Large modules should be split when:

- Multiple responsibilities exist
- Testing becomes difficult
- Dependencies become complex

---

# 21. Ruff Configuration Requirements

Ruff should check:

- Formatting
- Imports
- Complexity
- Common bugs
- Code style

Configuration belongs in:

```text
pyproject.toml
```

---

# 22. Mypy Configuration Requirements

Mypy should enforce:

- Strict typing
- Missing annotation detection
- Interface consistency

Recommended:

```text
strict = true
```

---

# 23. Code Review Requirements

Review should verify:

- Architecture compliance
- Type safety
- Tests
- Error handling
- Performance impact

---

# 24. Anti-Patterns

Avoid:

- Untyped public functions
- Silent exception handling
- Global mutable state
- Circular dependencies
- Hidden side effects
- Excessive abstraction

---

# 25. Final Definition

The SH-3 Coding Standard Specification defines the implementation rules required to maintain a high-quality, typed, deterministic, and production-ready Python codebase.

---

# End of Document
