# SH-3 Developer Reference

Version:
1.0.0

Status:
Developer Guide

Category:
Reference

---

# 1. Purpose

This document provides a consolidated reference for commonly used SH-3 concepts, commands, naming conventions, lifecycle stages, and document locations.

It is intended to serve as a quick-reference companion to the Architecture Specification and Developer Guide.

---

# 2. Core Principles

The SH-3 framework is built upon four foundational principles:

- Everything Event Driven
- Everything Replaceable
- Everything Typed
- Everything Testable

These principles apply across all layers of the framework.

---

# 3. Standard CLI Commands

## Project

```bash
sh3dev init
sh3dev validate
sh3dev build
sh3dev package
sh3dev upgrade
```

## Components

```bash
sh3dev component create
sh3dev component list
```

## Plugins

```bash
sh3dev plugin create
sh3dev plugin validate
sh3dev plugin package
sh3dev plugin publish
```

## Documentation

```bash
sh3dev docs build
sh3dev docs validate
sh3dev docs api
```

## RFC

```bash
sh3dev rfc create
sh3dev rfc validate
sh3dev rfc index
```

## ADR

```bash
sh3dev adr create
sh3dev adr validate
sh3dev adr index
```

## Testing

```bash
sh3dev test
sh3dev test unit
sh3dev test integration
sh3dev test performance
```

## Diagnostics

```bash
sh3dev diagnose
sh3dev health
sh3dev registry
sh3dev events
```

## Release

```bash
sh3dev release prepare
sh3dev release publish
sh3dev release notes
```

---

# 4. Recommended Project Structure

```text
docs/
src/
tests/
plugins/
examples/
scripts/
configs/
```

---

# 5. Layer Overview

| Layer | Responsibility |
|--------|----------------|
| Foundation | Shared types, utilities, contracts |
| Infrastructure | Common platform services |
| Runtime | Execution environment |
| Services | Intelligence and domain services |
| Kernel | Coordination and orchestration |
| Deployment | Packaging and delivery |

---

# 6. Component Categories

Typical component categories include:

- Runtime
- Kernel
- Service
- Infrastructure
- Persistence
- Plugin
- Self-Healing
- Learning
- Memory
- Planning

Each component should have a single well-defined responsibility.

---

# 7. Event Naming Convention

Recommended pattern:

```
<Entity><PastTenseVerb>
```

Examples:

- PluginRegistered
- GoalCreated
- MemoryUpdated
- TaskCompleted

Avoid imperative names such as:

- CreateGoal
- StartPlugin

---

# 8. Lifecycle States

Typical lifecycle:

```
Created

↓

Initialized

↓

Started

↓

Running

↓

Stopping

↓

Stopped

↓

Disposed
```

---

# 9. Logging Levels

Supported levels:

- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

Logs should include timestamps and correlation identifiers where appropriate.

---

# 10. Error Categories

Typical categories:

- ValidationError
- ConfigurationError
- DependencyError
- RuntimeError
- PluginError
- SecurityError
- PersistenceError
- NetworkError

Errors should be typed and documented.

---

# 11. Configuration Files

Typical project files:

```text
sh3.toml
pyproject.toml
ruff.toml
mypy.ini
```

Projects may define additional configuration files as needed.

---

# 12. Quality Gates

Standard validation pipeline:

```text
Formatting

↓

Static Analysis

↓

Type Checking

↓

Unit Tests

↓

Integration Tests

↓

Performance Validation

↓

Security Review
```

---

# 13. Documentation Set

Developer documentation:

- Developer Guide
- Style Guide
- FAQ
- Troubleshooting
- Reference

Architecture documentation:

- Architecture Specifications
- RFCs
- ADRs

Operational documentation:

- Deployment Guide
- Release Guide

---

# 14. Recommended Toolchain

Primary tools:

- Python 3.12+
- Ruff
- MyPy
- Pytest
- SH-3 DevKit

Additional tooling may be integrated where appropriate.

---

# 15. Common Abbreviations

| Abbreviation | Meaning |
|--------------|---------|
| ADR | Architecture Decision Record |
| API | Application Programming Interface |
| CI | Continuous Integration |
| CD | Continuous Delivery |
| CLI | Command Line Interface |
| DI | Dependency Injection |
| RFC | Request for Comments |
| SBOM | Software Bill of Materials |

---

# 16. Cross References

Primary references include:

- Architecture Specifications
- Developer Guide
- RFC Index
- ADR Index
- DevKit Guide

Developers should consult the appropriate specification before introducing architectural changes.

---

# 17. Compliance Checklist

Project artifacts are compliant when:

- Naming conventions are followed.
- Layer responsibilities are respected.
- Documentation is current.
- Validation passes.
- Public APIs are documented.
- Architecture references remain consistent.

---

# 18. Final Definition

The SH-3 Developer Reference provides a centralized reference for commands, conventions, terminology, and structural guidance, enabling developers to quickly locate authoritative information while maintaining consistency across the SH-3 AI Operating Framework.

---

# End of Document
