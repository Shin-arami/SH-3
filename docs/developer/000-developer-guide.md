# SH-3 Developer Guide

Version:
1.0.0

Status:
Developer Guide

Category:
Developer Documentation

---

# 1. Purpose

This document introduces the SH-3 development environment.

It explains how developers should implement, extend, test, and maintain SH-3 components while remaining compliant with the architecture specifications.

This guide is the primary entry point for all SH-3 developers.

---

# 2. Intended Audience

This guide is intended for:

- Framework Developers
- Plugin Developers
- Service Developers
- Runtime Developers
- Contributors
- Integrators

---

# 3. Prerequisites

Development requires:

- Python 3.12+
- Git
- Ruff
- MyPy
- Pytest
- SH-3 DevKit

Recommended:

- VS Code
- Docker
- Make

---

# 4. Development Principles

Every implementation must follow:

- Everything Event Driven
- Everything Replaceable
- Everything Typed
- Everything Testable
- Everything Observable

---

# 5. Coding Rules

Developers shall:

- Use type hints everywhere
- Avoid global mutable state
- Prefer dependency injection
- Avoid circular dependencies
- Keep components independent

---

# 6. Development Workflow

Typical workflow:

Design

↓

RFC

↓

Implementation

↓

Testing

↓

Review

↓

Merge

↓

Release

---

# 7. Project Structure

The SH-3 project is organized into:

- foundation/
- infrastructure/
- runtime/
- services/
- kernel/
- persistence/
- self_healing/
- docs/
- tests/

Each directory has a clearly defined responsibility.

---

# 8. Architecture Compliance

All code must comply with:

- Architecture Specifications
- RFCs
- ADRs
- Coding Standards

---

# 9. Testing

Every contribution requires:

- Unit Tests
- Type Checking
- Static Analysis
- Integration Tests

---

# 10. Documentation

Every public component should include:

- Module documentation
- API documentation
- Type annotations
- Usage examples

---

# 11. DevKit

The SH-3 DevKit provides:

- Project generation
- Architecture templates
- RFC templates
- CI templates
- Validation commands

---

# 12. Next Documents

Developers should continue with:

001 Getting Started

002 Project Structure

003 Coding Standards

004 Type System

---

# End of Document
