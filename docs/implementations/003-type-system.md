# SH-3 Type System Specification

Version:
1.0.0

Status:
Implementation Specification

Category:
Type System

---

# 1. Purpose

This document defines the type system architecture for the SH-3 AI Operating Framework.

The objectives are:

- Establish strong type safety
- Prevent invalid state
- Improve component contracts
- Enable deterministic development
- Support static verification

---

# 2. Type System Philosophy

SH-3 follows:

```text
Everything Typed

+

Explicit Contracts

+

Static Verification

+

Runtime Validation
```

Types are part of the architecture.

---

# 3. Type Requirements

All SH-3 components must provide:

- Explicit interfaces
- Typed inputs
- Typed outputs
- Typed events
- Typed configuration

Untyped communication is prohibited.

---

# 4. Type Architecture

SH-3 type hierarchy:

```text
Base Types

↓

Domain Types

↓

Component Types

↓

Event Types

↓

Runtime Types

↓

API Types
```

---

# 5. Foundation Types

Foundation provides common types.

Location:

```text
SH3/foundation/types/
```

Examples:

```text
Identifier

Timestamp

Version

Result

Status

Metadata
```

---

# 6. Identifier Types

Identifiers should use dedicated types.

Example:

```python
from typing import NewType

ComponentID = NewType(
    "ComponentID",
    str
)
```

Avoid raw strings for important identifiers.

---

# 7. Timestamp Types

Time values should use explicit types.

Example:

```python
datetime
```

Requirements:

- Timezone aware
- Consistent format
- Serializable

---

# 8. Version Types

Version information should be typed.

Example:

```python
@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
```

---

# 9. Result Types

Operations should return structured results.

Example:

```python
@dataclass
class Result[T]:
    success: bool
    value: T | None
    error: Exception | None
```

Avoid ambiguous return values.

---

# 10. Status Types

Lifecycle and operational states require enums.

Example:

```python
class ComponentStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
```

---

# 11. Event Type System

Events are strongly typed.

Structure:

```text
Event

├── Event ID

├── Event Type

├── Source

├── Timestamp

└── Payload
```

---

# 12. Event Base Type

Example:

```python
@dataclass(frozen=True)
class Event:
    id: EventID
    timestamp: datetime
    source: str
```

All events inherit from this model.

---

# 13. Domain Event Types

Each domain event requires a dedicated type.

Example:

```python
@dataclass(frozen=True)
class GoalCreated(Event):
    goal_id: GoalID
```

Avoid generic dictionaries.

---

# 14. Payload Typing

Event payloads must be typed.

Bad:

```python
dict[str, Any]
```

Preferred:

```python
@dataclass
class TaskPayload:
    task_id: TaskID
```

---

# 15. Protocol Design

SH-3 uses Protocol based interfaces.

Example:

```python
from typing import Protocol


class Storage(Protocol):

    async def save(
        self,
        key: str,
        value: bytes
    ) -> None:
        ...
```

Advantages:

- Replaceability
- Testing
- Loose coupling

---

# 16. Interface Types

Every major component requires:

- Input type
- Output type
- Error type
- Lifecycle contract

Example:

```text
Planner

Input:
Goal

Output:
Plan

Error:
PlanningError
```

---

# 17. Generic Types

Generic types should be used for reusable structures.

Examples:

- Result
- Repository
- Queue
- Cache

Example:

```python
class Repository[T]:
    ...
```

---

# 18. Collection Types

Use explicit collections.

Preferred:

```python
list[Event]
dict[str, Component]
set[ComponentID]
```

Avoid:

```python
list
dict
```

---

# 19. Optional Types

Optional values must be explicit.

Example:

```python
Component | None
```

Avoid implicit None behavior.

---

# 20. Type Validation

Runtime validation is required at boundaries.

Validation points:

```text
External Input

↓

Validation

↓

Typed Object

↓

Internal Processing
```

---

# 21. Configuration Types

Configuration must be typed.

Example:

```python
@dataclass(frozen=True)
class RuntimeConfig:
    workers: int
    timeout: float
```

---

# 22. Serialization Types

Serialized data requires:

- Schema definition
- Validation
- Version control

Supported formats:

- JSON
- MessagePack
- Binary formats

---

# 23. Mypy Requirements

SH-3 uses strict checking.

Recommended:

```toml
[tool.mypy]
strict = true
```

Required checks:

- Missing annotations
- Invalid overrides
- Untyped calls
- Return consistency

---

# 24. Type Safety Rules

Forbidden:

```python
def process(data):
    ...
```

Required:

```python
def process(data: Event) -> Result:
    ...
```

---

# 25. Type Evolution

When changing types:

Required:

- Compatibility analysis
- Migration plan
- Version update
- Test updates

---

# 26. Anti-Patterns

Avoid:

- Excessive Any usage
- Untyped dictionaries
- Hidden conversions
- Implicit state
- Weak interfaces

---

# 27. Final Definition

The SH-3 Type System Specification defines the type architecture required to achieve a strongly typed, replaceable, testable, and deterministic AI Operating Framework.

---

# End of Document
