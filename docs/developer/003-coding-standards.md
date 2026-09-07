# SH-3 Coding Standards

Version:
1.0.0

Status:
Developer Guide

Category:
Coding Standards

---

# 1. Purpose

This document defines the official coding standards for SH-3.

The objectives are:

- Consistent implementation
- High readability
- Maintainability
- Type safety
- Deterministic behavior
- Production-quality software

All SH-3 source code shall conform to this document.

---

# 2. Fundamental Principles

Every implementation shall be:

- Readable
- Deterministic
- Fully Typed
- Testable
- Replaceable
- Documented

---

# 3. Supported Python Version

Required:

Python 3.12+

Older versions are not supported.

---

# 4. Formatting

Formatting shall follow:

- Ruff Formatter
- UTF-8
- LF line endings
- Four-space indentation

Manual formatting should be minimized.

---

# 5. Naming Conventions

Packages:

snake_case

Modules:

snake_case

Classes:

PascalCase

Functions:

snake_case

Variables:

snake_case

Constants:

UPPER_CASE

Private Members:

_leading_underscore

Type Variables:

T

KT

VT

---

# 6. Imports

Import order:

1. Standard Library

2. Third-Party Packages

3. SH-3 Packages

Example:

```python
from pathlib import Path

from pydantic import BaseModel

from sh3.runtime.context import RuntimeContext
```

Wildcard imports are prohibited.

```
from module import *
```

Relative imports between top-level packages should be avoided.

---

# 7. Typing

All public APIs shall include type annotations.

Example:

```python
def load(path: Path) -> Configuration:
    ...
```

Avoid:

```python
def load(path):
    ...
```

---

# 8. Any

The use of `Any` should be avoided.

Use:

- Protocol
- Generic
- TypedDict
- dataclass
- Literal
- Enum

before introducing `Any`.

---

# 9. Generic Types

Prefer:

```python
class Repository[T]:
    ...
```

over untyped collections.

---

# 10. Dataclasses

Immutable data should prefer:

```python
@dataclass(frozen=True)
```

Mutable dataclasses require justification.

---

# 11. Exceptions

Raise specific exceptions.

Good:

```python
raise ConfigurationError(...)
```

Avoid:

```python
raise Exception(...)
```

Exceptions should include actionable messages.

---

# 12. Logging

Do not use:

```python
print(...)
```

Use the SH-3 logging abstraction.

Log levels:

- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

---

# 13. Configuration

Configuration values shall not be hard-coded.

Use:

- Configuration Provider
- Environment Resolver
- Dependency Injection

---

# 14. Dependency Injection

Prefer constructor injection.

Example:

```python
class Planner:

    def __init__(
        self,
        repository: Repository,
    ):
        self._repository = repository
```

Avoid service locators in business logic.

---

# 15. Component Size

Recommended limits:

Function:

20–40 logical lines

Class:

≤300 logical lines

Module:

≤500 logical lines

Larger modules require architectural justification.

---

# 16. Single Responsibility

Each class should have one primary responsibility.

Avoid "God Objects".

---

# 17. Circular Dependencies

Circular imports are prohibited.

Preferred:

```
Protocol

↓

Implementation

↓

Registration
```

Avoid:

```
A → B → C → A
```

---

# 18. Event Communication

Components should communicate through:

- Events
- Interfaces
- Registry

Avoid direct coupling across layers.

---

# 19. Immutability

Prefer immutable structures.

Examples:

- tuple
- frozenset
- frozen dataclass

Mutable shared state should be minimized.

---

# 20. Thread Safety

Shared mutable state requires synchronization.

Components should be safe for concurrent execution.

---

# 21. Documentation

Every public module shall include:

- Purpose
- Public API
- Usage Notes

Every public class shall include a docstring.

Complex algorithms should explain "why", not only "what".

---

# 22. Testing

Every public component requires:

- Unit Tests
- Type Checking
- Static Analysis

Critical components additionally require:

- Integration Tests
- Performance Tests

---

# 23. Static Analysis

Every commit should pass:

```text
ruff check
ruff format --check
mypy
pytest
```

No warnings should be ignored without documented justification.

---

# 24. Performance

Prefer algorithmic improvements before micro-optimizations.

Avoid unnecessary allocations.

Profile before optimizing.

---

# 25. Security

Never:

- Commit secrets
- Log credentials
- Disable validation

Always validate external input.

---

# 26. Backward Compatibility

Public APIs should remain stable.

Breaking changes require:

- RFC
- Version update
- Migration guidance

---

# 27. Code Review Checklist

Reviewers verify:

- Architecture compliance
- Type safety
- Readability
- Test coverage
- Performance impact
- Security considerations
- Documentation updates

---

# 28. Anti-Patterns

Avoid:

- Global mutable state
- Circular imports
- Hidden side effects
- Excessive inheritance
- Hard-coded configuration
- Untyped public APIs
- Catching broad Exception without justification

---

# 29. Compliance Checklist

Code is compliant when:

- Fully typed
- Ruff clean
- MyPy clean
- Tests passing
- Architecture compliant
- Documentation updated

---

# 30. Final Definition

The SH-3 Coding Standards define the mandatory implementation practices that ensure consistency, maintainability, and production-grade quality across the entire SH-3 AI Operating Framework.

---

# End of Document
