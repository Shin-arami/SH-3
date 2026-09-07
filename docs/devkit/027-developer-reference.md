# SH-3 DevKit Developer Reference Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Developer Reference


---

# 1. Purpose

This document defines the developer reference for SH-3 DevKit.

It provides:

- Core API reference
- Protocol definitions
- Extension points
- Runtime usage
- Component integration rules


---

# 2. Developer Philosophy


SH-3 DevKit development follows:



Understand Contract

↓

Implement Extension

↓

Validate Behavior

↓

Integrate Safely



---

# 3. Core Architecture


Main components:


```text
Foundation

Infrastructure

Runtime

Services

Kernel

Deployment
``` id="4m7q1a"


---

# 4. Foundation Reference


Foundation provides base components.


Responsibilities:



Types

Enums

Exceptions

Utilities



---

# 5. Type System


SH-3 requires:


```python
Complete Type Annotation

Example:

def execute(
    request: Request,
) -> Result:
    ...
6. Exception System

Base exception:

class SH3Error(Exception):
    ...

Hierarchy:

SH3Error

├── ConfigurationError

├── ValidationError

├── RegistryError

├── RuntimeError

└── GenerationError
``` id="h6k9x1"


---

# 7. Infrastructure Reference


Infrastructure provides:



Filesystem

Logging

Storage

Metrics



---

# 8. Filesystem API


Purpose:


Safe filesystem abstraction.


Example:


```python
filesystem.write(
    path,
    content,
)

Rules:

Validate paths
Use abstraction
Support atomic operations
9. Logging API

Purpose:

Unified logging.

Example:

logger.info(
    "message"
)

Requirements:

Structured output
No secret leakage
10. Runtime Reference

Runtime provides:

Bootstrap

Context

Lifecycle

Container
``` id="2h4x8m"


---

# 11. Application Runtime API


Example:


```python
runtime.start()

runtime.stop()

Lifecycle:

CREATED

↓

INITIALIZED

↓

RUNNING

↓

STOPPED
``` id="5z8m2q"


---

# 12. Runtime Context


Context provides:


```python
context.config

context.project

context.services

Purpose:

Shared execution state.

13. Dependency Container

Container responsibilities:

Register dependency
Resolve dependency
Manage lifecycle

Example:

container.register(
    Service,
    instance,
)
14. Service Reference

Services provide domain functionality.

Examples:

GeneratorService

ValidationService

TemplateService
``` id="m4w7zs"


---

# 15. Service Design Rules


Services must:


- Depend on protocols
- Avoid global state
- Remain testable


---

# 16. Kernel Reference


Kernel provides:



Registry

Pipeline

Coordination



---

# 17. Registry API


Purpose:


Component discovery.


Example:


```python
registry.register(
    component
)
18. Registry Lifecycle

Flow:

Create

↓

Register

↓

Validate

↓

Freeze

↓

Resolve
``` id="q7c4mn"


---

# 19. Command Protocol


Commands implement:


```python
class CommandProtocol(Protocol):

    name: str

    def execute(
        self,
        args: object,
    ) -> Result:
        ...
20. Generator Protocol

Generators implement:

class GeneratorProtocol(Protocol):

    def generate(
        self,
        request: object,
    ) -> Result:
        ...
21. Validator Protocol

Validators implement:

class ValidatorProtocol(Protocol):

    def validate(
        self,
        target: object,
    ) -> ValidationResult:
        ...
22. Plugin Protocol

Plugins provide:

class PluginProtocol(Protocol):

    manifest: object

    def initialize(self) -> None:
        ...
23. Extension Points

Supported extensions:

Commands

Generators

Validators

Plugins

AI Extensions

Services
``` id="v8s2pm"


---

# 24. Creating an Extension


Standard flow:


```text
Define Protocol

↓

Implement Component

↓

Register

↓

Validate

↓

Test
``` id="g2m5ky"


---

# 25. Testing Reference


Required:



Unit Test

Integration Test

Contract Test



---

# 26. Static Analysis


Required:


```bash
ruff check .

mypy .

pytest
27. API Stability

Public APIs require:

Documentation
Compatibility
Tests
28. Runtime Integration Example

Flow:

Extension

↓

Registry

↓

Runtime

↓

Execution
``` id="x4q9ps"


---

# 29. AI Extension Reference


AI extensions may provide:



Agent

Tool

Memory

Reasoning



Integration:


```text
AI Extension API

↓

Runtime

↓

Services
30. Developer Checklist
[ ] Understand Layer

[ ] Implement Protocol

[ ] Add Types

[ ] Add Tests

[ ] Validate

[ ] Document
31. Production Development Standard

Component is complete when:

Architecture PASS

+

Type Check PASS

+

Tests PASS

+

Validation PASS
``` id="j3m7cz"


---

# End of Document
