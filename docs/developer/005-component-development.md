# SH-3 Component Development Guide

Version:
1.0.0

Status:
Developer Guide

Category:
Component Development

---

# 1. Purpose

This document defines the standard process for designing, implementing, testing, and maintaining SH-3 components.

Every component in the SH-3 ecosystem shall follow this specification to ensure consistency, interoperability, and maintainability.

---

# 2. Component Philosophy

Every component shall be:

- Replaceable
- Independent
- Typed
- Testable
- Observable
- Deterministic

A component should provide one primary responsibility.

---

# 3. Component Lifecycle

The standard lifecycle is:

```
Created

↓

Configured

↓

Initialized

↓

Started

↓

Running

↓

Paused (Optional)

↓

Stopped

↓

Disposed
```

Lifecycle transitions should be explicit and idempotent.

---

# 4. Component Categories

Typical component types include:

- Runtime Component
- Kernel Component
- Service Component
- Infrastructure Component
- Persistence Component
- Self-Healing Component
- Plugin Component

Each category follows the same structural conventions.

---

# 5. Canonical Directory Layout

A component should be organized as follows:

```text
planner/

├── __init__.py
├── interface.py
├── implementation.py
├── config.py
├── events.py
├── exceptions.py
├── models.py
├── registry.py
└── tests/
```

Supporting modules may be added as needed, but responsibilities should remain cohesive.

---

# 6. Public Interface

Expose a stable interface using a `Protocol` where possible.

Example:

```python
class Planner(Protocol):
    def plan(self, goal: Goal) -> Plan: ...
```

Business logic should depend on the interface rather than the implementation.

---

# 7. Implementation

Implementations should:

- Satisfy the public contract
- Avoid hidden side effects
- Remain deterministic for identical inputs
- Encapsulate internal state

Implementation classes should not be imported directly by unrelated layers.

---

# 8. Configuration

Each configurable component should define a dedicated configuration model.

Configuration should be:

- Immutable
- Validated
- Version-aware

Configuration should be injected rather than loaded internally.

---

# 9. Dependency Injection

Dependencies shall be provided through constructors.

Example:

```python
class PlannerImpl:

    def __init__(
        self,
        memory: MemoryRepository,
        event_bus: EventBus,
    ) -> None:
        ...
```

Do not create dependencies internally.

---

# 10. Registry Integration

Components register themselves through the Kernel registry.

Registration should include:

- Identifier
- Version
- Interface
- Implementation
- Metadata

Registration must be repeatable and idempotent.

---

# 11. Event Integration

Components communicate through events.

Typical flow:

```
Receive Event

↓

Process

↓

Publish Event
```

Avoid direct cross-layer calls when an event-based interaction is appropriate.

---

# 12. State Management

Internal state should be:

- Minimal
- Consistent
- Recoverable

Long-lived state belongs in the Persistence layer.

---

# 13. Error Handling

Use domain-specific exceptions.

Recoverable conditions should produce meaningful diagnostics.

Unexpected failures should propagate through the framework's error-handling mechanisms.

---

# 14. Logging

Use the SH-3 logging abstraction.

Recommended log points:

- Initialization
- State transitions
- Errors
- Recovery actions
- Shutdown

Avoid excessive logging inside hot paths.

---

# 15. Metrics

Components should expose metrics such as:

- Request count
- Execution time
- Failure count
- Retry count
- Queue length (where applicable)

Metrics should integrate with the Observability subsystem.

---

# 16. Health Monitoring

Components should provide a health status when applicable.

Suggested states:

- Healthy
- Degraded
- Unavailable

Health reporting should avoid expensive operations.

---

# 17. Thread Safety

Components intended for concurrent use shall:

- Protect mutable shared state
- Avoid race conditions
- Document synchronization strategy

Prefer immutability over locking when practical.

---

# 18. Testing

Each component requires:

- Unit tests
- Integration tests
- Static analysis

Recommended layout:

```text
tests/
├── test_interface.py
├── test_implementation.py
├── test_events.py
└── test_config.py
```

---

# 19. Documentation

Each component should include:

- Purpose
- Public interface
- Configuration
- Events
- Usage example
- Known limitations (if any)

Documentation should evolve with the implementation.

---

# 20. Versioning

Each component should declare:

- Name
- Version
- Compatibility information

Breaking public interface changes require a major version increment.

---

# 21. Extensibility

Extension points should be clearly identified.

Preferred mechanisms:

- Protocols
- Plugins
- Registries
- Dependency injection

Avoid requiring source-code modification for extensions.

---

# 22. Review Checklist

During review, verify:

- Single responsibility
- Stable public interface
- Proper dependency injection
- Event integration
- Thread safety
- Test coverage
- Documentation completeness

---

# 23. Anti-Patterns

Avoid:

- Circular dependencies
- Global mutable state
- Hidden configuration loading
- Direct layer violations
- Business logic in infrastructure components
- Excessively large components

---

# 24. Compliance Checklist

A component is compliant when:

- It follows the canonical layout
- Public APIs are fully typed
- Dependencies are injected
- Events are used appropriately
- Tests pass
- Documentation is complete
- Registry integration is implemented

---

# 25. Final Definition

A SH-3 component is a self-contained, replaceable, typed, observable, and testable unit of functionality that integrates with the framework through stable interfaces, dependency injection, and the event-driven architecture.

---

# End of Document
