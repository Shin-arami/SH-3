# SH-3 Unit Testing Specification

Version:
1.0.0

Status:
Testing Specification

Category:
Unit Testing

---

# 1. Purpose

This document defines the unit testing standards for the SH-3 AI Operating Framework.

The objectives are:

- Verify individual implementation units
- Detect defects early
- Maintain deterministic behavior
- Support safe refactoring
- Ensure code quality

---

# 2. Unit Testing Philosophy

SH-3 Unit Testing follows:

```text
Small Scope

+

Fast Execution

+

Deterministic Result

+

Independent Verification
```

A unit test verifies one responsibility.

---

# 3. Unit Test Scope

Unit tests target:

```text
Function

Class

Method

Data Model

Value Object

Utility
```

A unit should be testable without the complete system.

---

# 4. Unit Test Structure

Recommended structure:

```text
tests/

└── unit/

    ├── foundation/

    ├── infrastructure/

    ├── runtime/

    ├── services/

    └── kernel/
```

Tests follow source structure.

---

# 5. Test Naming Standard

Format:

```text
test_<component>_<scenario>_<expected>
```

Examples:

```python
test_registry_register_component_success()

test_event_bus_publish_invalid_event_error()
```

Names must describe behavior.

---

# 6. Arrange-Act-Assert Pattern

Unit tests should follow:

```text
Arrange

↓

Act

↓

Assert
```

Example:

```python
# Arrange
component = create_component()

# Act
result = component.execute()

# Assert
assert result.success
```

---

# 7. Test Isolation

Unit tests must be isolated from:

- Database
- Network
- File System
- External Services
- Global State

External dependencies require abstraction.

---

# 8. Deterministic Testing

Unit tests must avoid:

- Random values
- Real time dependency
- Uncontrolled concurrency
- External environment dependency

Use controlled inputs.

---

# 9. Mock Policy

Mocks are allowed for:

```text
External APIs

Storage

Network

System Clock

Hardware Resources
```

---

# 10. Mock Restrictions

Avoid mocking:

- Core business logic
- Simple value objects
- Internal algorithms

Excessive mocking reduces test confidence.

---

# 11. Fixture Usage

Fixtures provide reusable:

```text
Configuration

Test Objects

Mock Services

Execution Context
```

Fixtures must remain minimal.

---

# 12. Fixture Rules

Fixtures should:

- Have single purpose
- Avoid hidden behavior
- Be reusable
- Be deterministic

---

# 13. Input Testing

Unit tests must validate:

```text
Valid Input

Invalid Input

Boundary Input

Empty Input

Maximum Input
```

---

# 14. Output Testing

Verify:

```text
Return Type

Return Value

State Change

Side Effects
```

---

# 15. Exception Testing

All expected exceptions require tests.

Verify:

```text
Exception Type

Exception Condition

Error Context
```

---

# 16. Type Safety Testing

Typed components require:

- Correct input types
- Correct output types
- Protocol compliance

Runtime type assumptions must be tested.

---

# 17. State Testing

Stateful components require:

```text
Initial State

Transition

Final State
```

Examples:

- Registry
- Pipeline
- Lifecycle Manager

---

# 18. Coverage Rules

Minimum targets:

```text
Foundation:

≥95%

Infrastructure:

≥90%

Runtime:

≥90%

Services:

≥90%

Kernel:

≥90%
```

---

# 19. Coverage Quality

Coverage percentage alone is insufficient.

Tests must verify:

```text
Important Branches

Error Paths

Boundary Conditions

Critical Logic
```

---

# 20. Performance Requirements

Unit tests should:

- Execute quickly
- Avoid unnecessary setup
- Run independently

Slow unit tests should be reviewed.

---

# 21. Regression Usage

Every fixed defect should add:

```text
Regression Unit Test
```

The test prevents recurrence.

---

# 22. Async Testing

Async components require:

```text
Async Execution

Await Validation

Cancellation Handling

Exception Propagation
```

---

# 23. Thread Safety Testing

Thread-safe components require:

```text
Concurrent Access Test

State Consistency Test

Race Condition Test
```

---

# 24. Anti-Patterns

Avoid:

- Testing multiple responsibilities in one test
- Depending on test order
- Using production resources
- Ignoring error cases
- Excessive mocks

---

# 25. Final Definition

The SH-3 Unit Testing Specification defines the standards required to verify individual components with deterministic, isolated, maintainable, and production-quality tests.

---

# End of Document
