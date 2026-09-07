# SUPPORT.md

# SH-3 Support Guide

## Overview

Thank you for using SH-3.

This document explains how to request support, report problems, propose improvements, and participate in the SH-3 project.

SH-3 is developed as a production-oriented AI Operating System Framework. Clear communication helps maintain project quality.

---

# Where to Ask for Help

Choose the appropriate channel depending on your request.

| Purpose               | Location            |
| --------------------- | ------------------- |
| Question about usage  | GitHub Discussions  |
| Bug report            | GitHub Issues       |
| Feature proposal      | GitHub Issues       |
| Architecture proposal | RFC                 |
| Code contribution     | Pull Request        |
| Security problem      | SECURITY.md process |

---

# GitHub Discussions

Use Discussions for:

* General questions
* Design discussions
* Usage guidance
* Ideas before implementation
* Community knowledge sharing

Examples:

```
How should I implement a custom SH-3 service?

What is the recommended Runtime architecture?

How does the Event system work?
```

Discussions are preferred before opening large architectural changes.

---

# GitHub Issues

Use Issues for concrete development tasks.

Good Issue examples:

```
Fix EventBus race condition

Add Memory storage backend

Implement CLI generator command
```

A good Issue should include:

## Overview

What needs to be changed.

## Motivation

Why the change is needed.

## Scope

Which components are affected.

## Acceptance Criteria

How completion is verified.

---

# Bug Reports

Before creating a bug report:

1. Confirm you are using the latest version.
2. Check existing Issues.
3. Provide reproduction information.

Include:

* SH-3 version
* Python version
* Operating system
* Steps to reproduce
* Expected behavior
* Actual behavior
* Error logs

Example:

```
Version:
SH-3 DevKit 1.0.0

Python:
3.12.x

Problem:
Command generation fails when template is missing.
```

---

# Feature Requests

Feature requests should explain:

* The problem being solved.
* Why the feature is valuable.
* Possible implementation approach.
* Compatibility considerations.

Large features should begin with an RFC.

---

# RFC Process

Architecture-level changes require an RFC.

Examples:

* New subsystem
* Kernel changes
* Runtime redesign
* New communication protocol
* Major API changes

RFC lifecycle:

```
Draft
 ↓
Discussion
 ↓
Review
 ↓
Accepted
 ↓
Implementation
```

---

# Pull Requests

Pull Requests are for completed code changes.

Before submitting:

* Tests pass.
* Formatting passes.
* Type checking passes.
* Documentation is updated.

PR descriptions should include:

* Summary
* Motivation
* Implementation details
* Testing performed

---

# Development Environment Support

Recommended environment:

```
Python 3.12+

pytest

ruff

mypy

git
```

---

# Common Commands

Run tests:

```bash
pytest
```

Run lint:

```bash
ruff check .
```

Run type checking:

```bash
mypy .
```

---

# Community Guidelines

Please:

* Be respectful.
* Provide technical details.
* Search before asking.
* Share reproducible examples.
* Help improve documentation.

Avoid:

* Duplicate Issues
* Unclear bug reports
* Personal attacks
* Unrelated discussions

---

# Maintainer Response

Maintainers and contributors are volunteers.

Response time depends on:

* Issue complexity
* Available maintainers
* Project priorities

Urgent security issues are handled separately according to SECURITY.md.

---

# SH-3 Development Philosophy

All contributions should respect:

* Everything Event Driven
* Everything Replaceable
* Everything Typed
* Everything Testable

Technical decisions should be based on:

* Maintainability
* Reliability
* Determinism
* Long-term architecture

---

Thank you for supporting SH-3.
