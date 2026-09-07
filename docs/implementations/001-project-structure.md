# SH-3 Project Structure Specification

Version:
1.0.0

Status:
Implementation Specification

Category:
Project Structure

---

# 1. Purpose

This document defines the repository and package structure of the SH-3 AI Operating Framework.

The objectives are:

- Maintain architectural consistency
- Define module boundaries
- Prevent dependency violations
- Improve maintainability
- Support production development

---

# 2. Project Structure Philosophy

SH-3 source organization follows:

```text
Clear Responsibility

+

Layer Isolation

+

Explicit Dependencies

+

Replaceable Components
```

Every directory represents a defined architectural responsibility.

---

# 3. Repository Root Structure

Recommended structure:

```text
SH-3/

├── SH3/

├── tests/

├── docs/

├── tools/

├── scripts/

├── examples/

├── pyproject.toml

├── README.md

└── LICENSE
```

---

# 4. Main Package Structure

Core implementation:

```text
SH3/

├── foundation/

├── infrastructure/

├── runtime/

├── services/

├── kernel/

├── deployment/

└── __init__.py
```

---

# 5. Foundation Layer

Location:

```text
SH3/foundation/
```

Responsibility:

- Base types
- Constants
- Enums
- Exceptions
- Utilities

Structure:

```text
foundation/

├── types/

├── enums/

├── exceptions/

├── utils/

└── config/
```

Foundation must not depend on higher layers.

---

# 6. Infrastructure Layer

Location:

```text
SH3/infrastructure/
```

Responsibility:

- External resources
- Common services
- System integrations

Structure:

```text
infrastructure/

├── event/

├── storage/

├── logging/

├── metrics/

├── tracing/

└── security/
```

---

# 7. Runtime Layer

Location:

```text
SH3/runtime/
```

Responsibility:

- Execution management
- Lifecycle control
- Runtime context

Structure:

```text
runtime/

├── context/

├── lifecycle/

├── scheduler/

├── executor/

└── event_bus/
```

---

# 8. Services Layer

Location:

```text
SH3/services/
```

Responsibility:

- Intelligence capabilities
- Domain services

Structure:

```text
services/

├── planner/

├── memory/

├── policy/

├── learning/

├── optimizer/

└── healing/
```

---

# 9. Kernel Layer

Location:

```text
SH3/kernel/
```

Responsibility:

- System coordination
- Component management
- Execution orchestration

Structure:

```text
kernel/

├── registry/

├── pipeline/

├── coordinator/

└── controller/
```

---

# 10. Deployment Layer

Location:

```text
SH3/deployment/
```

Responsibility:

- Runtime packaging
- Environment integration

Structure:

```text
deployment/

├── loaders/

├── environment/

├── bootstrap/

└── management/
```

---

# 11. Test Structure

Tests mirror source structure.

Example:

```text
tests/

├── foundation/

├── infrastructure/

├── runtime/

├── services/

├── kernel/

└── deployment/
```

---

# 12. Module Naming Rules

Rules:

- lowercase names
- snake_case files
- meaningful names

Examples:

Valid:

```text
event_bus.py

runtime_context.py
```

Invalid:

```text
EventBus.py

runtimeContext.py
```

---

# 13. Class Naming Rules

Classes use:

```text
PascalCase
```

Examples:

```python
class EventBus:
    ...
```

---

# 14. Function Naming Rules

Functions use:

```text
snake_case
```

Examples:

```python
def publish_event():
    ...
```

---

# 15. Import Rules

Imports must follow:

```text
Standard Library

↓

External Libraries

↓

SH-3 Internal Modules
```

Example:

```python
import asyncio

from pydantic import BaseModel

from SH3.foundation.types import Event
```

---

# 16. Layer Import Rules

Allowed:

```text
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

Forbidden:

```text
Foundation

↓

Services
```

---

# 17. Public API Boundary

Each package should expose:

```python
__init__.py
```

Public interfaces only.

Internal modules should remain private.

---

# 18. Internal Module Rules

Private implementation details:

Prefix:

```text
_
```

Example:

```text
_internal.py
```

Internal modules must not become public dependencies.

---

# 19. Configuration Location

Configuration should exist in:

```text
foundation/config/
```

or:

```text
deployment/environment/
```

Application logic must not contain environment-specific values.

---

# 20. Dependency Injection Boundary

External dependencies should enter through:

- Constructors
- Providers
- Factories

Avoid:

- Global singleton state
- Hidden imports

---

# 21. Generated Files

Generated files must be separated:

```text
.generated/
```

Source files must remain manually maintainable.

---

# 22. Documentation Relationship

Code documentation:

```text
docs/

├── architecture/

├── developer/

├── implementation/

└── deployment/
```

Implementation documents describe code behavior.

---

# 23. Anti-Patterns

Avoid:

- Mixed layer responsibilities
- Random module placement
- Circular imports
- Hidden dependencies
- Large uncontrolled packages

---

# 24. Final Definition

The SH-3 Project Structure Specification defines the repository organization and package boundaries required to maintain a scalable, modular, and production-ready AI Operating Framework.

---

# End of Document
