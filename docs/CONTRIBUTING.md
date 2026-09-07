# CONTRIBUTING.md

# Contributing to SH-3

Thank you for contributing to SH-3.

SH-3 is a production-oriented AI Operating System Framework designed around deterministic, typed, modular, and event-driven principles.

Please read this document before submitting changes.

---

# Development Philosophy

Every contribution SHALL follow these principles.

* Everything Event Driven
* Everything Replaceable
* Everything Typed
* Everything Testable
* Standard Library First
* Production Ready
* Deterministic Behavior

These principles have higher priority than implementation convenience.

---

# Development Workflow

Every change follows the same lifecycle.

```
RFC
    ↓
Issue
    ↓
Feature Branch
    ↓
Implementation
    ↓
Tests
    ↓
Pull Request
    ↓
Review
    ↓
Merge
```

Direct commits to `main` are discouraged.

---

# Branch Naming

Use descriptive branch names.

Examples

```
feature/runtime-eventbus

feature/devkit-cli

feature/memory-manager

bugfix/event-dispatch

refactor/context-manager

docs/rfc-0025
```

---

# Commit Message Convention

Use Conventional Commits.

Examples

```
feat(runtime): add event dispatcher

feat(devkit): implement command registry

fix(kernel): resolve race condition

refactor(memory): simplify cache layer

docs(rfc): add architecture specification

test(runtime): improve dispatcher coverage
```

---

# Pull Requests

Each Pull Request should implement one logical feature.

A Pull Request should remain focused.

Large changes should be split into multiple Pull Requests.

Every Pull Request should include

* purpose
* implementation summary
* tests
* documentation updates if applicable

---

# Issue Policy

Before implementation

* Architecture should be discussed.
* An Issue should exist.
* Acceptance criteria should be defined.

Every Issue should include

* Overview
* Goals
* Scope
* Acceptance Criteria

---

# Coding Standards

Python Version

```
Python 3.12+
```

Formatting

```
Ruff
```

Type Checking

```
mypy
```

Testing

```
pytest
```

All code must be fully typed.

Avoid dynamic typing unless absolutely necessary.

---

# Project Structure

Typical layout

```
foundation/
infrastructure/
runtime/
services/
kernel/
persistence/
self_healing/
sh3dev/
docs/
tests/
```

Dependencies flow downward only.

```
Application
    ↓
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

Circular dependencies are prohibited.

---

# Testing

Every feature should include tests whenever practical.

Preferred test order

```
Unit Tests

↓

Integration Tests

↓

End-to-End Tests
```

CI must pass before merge.

---

# Documentation

Documentation is part of the implementation.

Update documentation whenever

* architecture changes
* public APIs change
* user behavior changes

RFC documents should be updated before implementation when introducing new architecture.

---

# Performance

Prefer

* readability
* correctness
* determinism

before micro-optimizations.

Optimize only after measurement.

---

# Error Handling

Never silently ignore exceptions.

Raise explicit exceptions.

Errors should provide actionable information.

---

# Logging

Use structured logging.

Avoid print statements outside CLI tools and examples.

---

# Security

Never commit

* secrets
* API keys
* tokens
* credentials

Use environment variables or configuration files.

---

# AI Generated Code

AI-assisted code is welcome.

Every generated change must be reviewed before merging.

Generated code should follow the same quality standards as handwritten code.

---

# Definition of Done

A feature is complete only when

* implementation finished
* tests added
* Ruff passes
* mypy passes
* documentation updated
* review completed
* merged into main

---

# Code of Conduct

Be respectful.

Be constructive.

Prefer technical discussion over personal opinion.

Focus on improving the project.

---

Thank you for helping build SH-3.
