# SH-3 Best Practices Guide

Version:
1.0.0

Status:
Developer Guide

Category:
Best Practices

---

# 1. Purpose

This document collects recommended engineering practices for developing, reviewing, testing, and operating SH-3 components.

Unlike architecture specifications, these recommendations describe proven implementation approaches that improve maintainability, readability, reliability, and long-term evolution.

---

# 2. Core Principles

Every implementation should strive to be:

- Event Driven
- Replaceable
- Typed
- Testable
- Observable
- Deterministic

Whenever multiple implementations are possible, choose the one that best preserves these principles.

---

# 3. Keep Components Small

Components should have a single responsibility.

Good:

- Planner
- MemoryRepository
- EventDispatcher

Avoid:

- SystemManager
- GlobalController
- MegaService

Large components become difficult to test and maintain.

---

# 4. Prefer Composition

Prefer:

```
Planner
 ├── Memory
 ├── Policy
 └── EventBus
```

Instead of:

```
MegaPlanner
    ↑
HugePlanner
    ↑
UltimatePlanner
```

Composition generally provides greater flexibility than deep inheritance.

---

# 5. Depend on Contracts

Always depend on:

- Protocol
- Interface
- Abstract Contract

Avoid depending directly on concrete implementations unless unavoidable.

---

# 6. Constructor Injection

Inject dependencies through constructors.

Preferred:

```python
Planner(memory, policy, event_bus)
```

Avoid:

```python
planner = Planner()
planner.memory = ...
```

Dependencies should be explicit.

---

# 7. Immutable Models

Prefer immutable objects.

Examples:

- frozen dataclass
- tuple
- frozenset

Immutable models simplify reasoning and improve thread safety.

---

# 8. Events over Direct Calls

Prefer:

```
Publish Event

↓

Subscriber Handles Event
```

Instead of tightly coupled direct component interactions.

Use synchronous calls only when immediate results are required.

---

# 9. Explicit Configuration

Configuration should:

- Be validated
- Be versioned
- Be externalized
- Be immutable after initialization

Avoid hidden configuration sources.

---

# 10. Favor Readability

Readable code is preferred over clever code.

Choose descriptive names.

Prefer:

```python
load_configuration()
```

Over:

```python
lc()
```

---

# 11. Small Functions

Functions should:

- Perform one task
- Minimize branching
- Return predictable results

Complex logic should be decomposed into smaller functions.

---

# 12. Clear Error Handling

Raise meaningful exceptions.

Include:

- Cause
- Context
- Suggested resolution (when appropriate)

Do not suppress exceptions silently.

---

# 13. Logging

Log:

- State transitions
- Failures
- Recovery actions
- Important lifecycle events

Avoid excessive debug logging in performance-critical paths.

---

# 14. Testing Early

Write tests alongside implementation.

Recommended sequence:

```
Interface

↓

Tests

↓

Implementation

↓

Refinement
```

Testing should be continuous rather than postponed.

---

# 15. Measure Before Optimizing

Do not optimize without evidence.

Use:

- Profilers
- Benchmarks
- Metrics

Optimization should address measured bottlenecks.

---

# 16. Keep Public APIs Stable

Public interfaces should evolve cautiously.

Prefer extending behavior over breaking existing contracts.

Breaking changes require documentation and migration guidance.

---

# 17. Document Decisions

Document:

- Architectural decisions
- Public APIs
- Non-obvious algorithms
- Limitations

Explain *why* a decision exists, not only *what* it does.

---

# 18. Avoid Global State

Global mutable state should be avoided.

Prefer:

- Dependency Injection
- Registry
- Configuration Providers

Global state complicates testing and concurrency.

---

# 19. Review Continuously

During review, verify:

- Architecture compliance
- Readability
- Type safety
- Test coverage
- Documentation
- Security considerations

Reviews should focus on maintainability as well as correctness.

---

# 20. Learn from Incidents

After defects or incidents:

- Identify the root cause
- Improve tests
- Update documentation
- Capture lessons learned
- Prevent recurrence

Continuous improvement is part of the development process.

---

# 21. Anti-Patterns

Avoid:

- God Objects
- Circular dependencies
- Hidden side effects
- Untyped public APIs
- Hard-coded configuration
- Duplicate business logic
- Excessive inheritance
- Premature optimization

---

# 22. Compliance Checklist

Best practices are followed when:

- Components are cohesive.
- Dependencies are explicit.
- Public APIs remain stable.
- Events are preferred for decoupling.
- Tests accompany implementation.
- Documentation reflects design decisions.

---

# 23. Final Definition

The SH-3 Best Practices Guide captures the recommended engineering patterns that complement the formal architecture and coding standards, enabling developers to build consistent, maintainable, and production-quality systems across the SH-3 AI Operating Framework.

---

# End of Document
