# SH-3

# SH-3 AI Operating System Framework

SH-3 is a production-oriented AI Operating System Framework based on a layered kernel architecture.

The goal of SH-3 is to provide a modular, extensible, deterministic, and testable foundation for building advanced AI systems.

---

# Project Status

## Development Status

```text
Version: Development

Status: Active Development
```

SH-3 is under continuous development.

The project is designed with long-term extensibility and production deployment in mind.

---

# Core Philosophy

SH-3 follows four fundamental principles.

## Everything Event Driven

All major system communication is based on events.

Benefits:

* Loose coupling
* Extensibility
* Observability
* Replaceable components

---

## Everything Replaceable

Every subsystem should be replaceable without rewriting the entire system.

Examples:

* Storage backends
* Runtime components
* AI services
* Tools
* Models

---

## Everything Typed

All components should use explicit type definitions.

Goals:

* Safer development
* Better IDE support
* Easier maintenance
* Reduced runtime errors

---

## Everything Testable

Every component should be designed for verification.

Testing includes:

* Unit tests
* Integration tests
* System tests

---

# Architecture

SH-3 uses a layered architecture.

```text
Application

    ↓

Deployment

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

Dependencies flow downward only.

Circular dependencies are prohibited.

---

# System Layers

## Foundation

Core definitions.

Responsibilities:

* Types
* Enums
* Exceptions
* Utilities
* Base interfaces

---

## Infrastructure

Common system services.

Responsibilities:

* EventBus
* Logging
* Storage
* Metrics
* Tracing

---

## Runtime

Execution environment.

Responsibilities:

* Execution management
* Context handling
* Scheduling
* Runtime lifecycle

---

## Services

Intelligence capabilities.

Responsibilities:

* Planning
* Memory
* Policy
* Learning
* Optimization
* Self Healing

---

## Kernel

System coordination layer.

Responsibilities:

* Component coordination
* Registry management
* Pipeline control
* Lifecycle management

---

## Deployment

Distribution and operation layer.

Responsibilities:

* Packaging
* Installation
* Configuration
* Deployment management

---

# Repository Structure

```text
SH-3/

├── foundation/
├── infrastructure/
├── runtime/
├── services/
├── kernel/
├── persistence/
├── self_healing/
│
├── sh3dev/
│   ├── cli.py
│   ├── commands/
│   ├── registry/
│   └── generators/
│
├── docs/
│   ├── architecture/
│   ├── rfc/
│   └── specifications/
│
├── tests/
│
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── SUPPORT.md
├── GOVERNANCE.md
└── MAINTAINERS.md
```

---

# SH-3 DevKit

SH-3 includes a development toolkit for automation and project management.

Example:

```bash
python -m sh3dev --version
```

Output:

```text
SH-3 DevKit 1.0.0
```

Future capabilities:

* Project generation
* RFC generation
* Code generation
* Validation
* Build automation
* Testing automation

---

# Development Environment

Recommended environment:

```text
Python 3.12+

pytest

ruff

mypy

git
```

---

# Installation

Clone the repository:

```bash
git clone https://github.com/Shin-arami/SH-3.git
```

Move into the project:

```bash
cd SH-3
```

Create virtual environment:

```bash
python -m venv .venv
```

Activate environment:

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

---

# Development Commands

Run tests:

```bash
pytest
```

Lint:

```bash
ruff check .
```

Type check:

```bash
mypy .
```

---

# Documentation

SH-3 documentation is managed through:

* Architecture Documents
* RFC Documents
* ADR Documents
* Developer Guides

Major architecture changes require RFC review.

---

# Contributing

Contributions are welcome.

Before contributing, please read:

* CONTRIBUTING.md
* CODE_OF_CONDUCT.md
* GOVERNANCE.md

All contributions should follow SH-3 development principles.

---

# Security

For security issues, please follow:

`SECURITY.md`

Do not publicly disclose security vulnerabilities before coordinated resolution.

---

# Roadmap

Future development areas:

* Advanced Runtime Architecture
* Distributed Intelligence
* Autonomous Learning Systems
* Self-Healing Infrastructure
* Multi-Agent Coordination
* Production Deployment Framework

---

# License

This project is licensed under the project license.

See:

```text
LICENSE
```

for details.

---

# Vision

SH-3 aims to become a reliable foundation for next-generation AI systems.

Through modular architecture, strong engineering practices, and open collaboration, SH-3 continues to evolve as an extensible AI Operating System Framework.

---

# Maintainers

See:

```text
MAINTAINERS.md
```
for project maintenance information.

# Part 10-9 — Cognition EventBus / Evidence / Observability

Adds typed cognition observability around the existing contract path.

## Changed
- `cognition/observability.py`
  - `CognitionObservability`
  - `CognitionObservationReport`
  - EventBus publication for Policy / Decision / Execution / Result
  - deterministic stage evidence IDs
  - idempotent evidence reuse with integrity verification
- `cognition/core.py`
  - EventPublisher / EvidenceStore / CognitionObservability injection
  - automatic observation of `run_contract()` / `execute_contract()` results
  - public `observe_result()` access
- `tests/cognition/test_cognition_observability.py`
  - EventBus causation chain
  - Evidence integrity and stage records
  - policy denial / execution failure audit paths
  - direct typed observation

## Expected user-side baseline
Part 10-8 baseline: 840 passed.
Part 10-9 adds 7 cognition tests, so expected full suite: 847 passed.

## Validation
```powershell
py -3.12 -m ruff check cognition foundation tests\cognition tests\runtime
py -3.12 -m mypy cognition foundation tests\cognition tests\runtime --explicit-package-bases
py -3.12 -m pytest tests\cognition -q
py -3.12 -m pytest -q
py -3.12 -m pytest -q -W error::DeprecationWarning
```

# Part 10-9 — Cognition EventBus / Evidence / Observability

Adds typed cognition observability around the existing contract path.

## Changed
- `cognition/observability.py`
  - `CognitionObservability`
  - `CognitionObservationReport`
  - EventBus publication for Policy / Decision / Execution / Result
  - deterministic stage evidence IDs
  - idempotent evidence reuse with integrity verification
- `cognition/core.py`
  - EventPublisher / EvidenceStore / CognitionObservability injection
  - automatic observation of `run_contract()` / `execute_contract()` results
  - public `observe_result()` access
- `tests/cognition/test_cognition_observability.py`
  - EventBus causation chain
  - Evidence integrity and stage records
  - policy denial / execution failure audit paths
  - direct typed observation

## Expected user-side baseline
Part 10-8 baseline: 840 passed.
Part 10-9 adds 7 cognition tests, so expected full suite: 847 passed.

## Validation
```powershell
py -3.12 -m ruff check cognition foundation tests\cognition tests\runtime
py -3.12 -m mypy cognition foundation tests\cognition tests\runtime --explicit-package-bases
py -3.12 -m pytest tests\cognition -q
py -3.12 -m pytest -q
py -3.12 -m pytest -q -W error::DeprecationWarning
```
