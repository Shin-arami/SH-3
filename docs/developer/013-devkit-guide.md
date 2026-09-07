# SH-3 DevKit Guide

Version:
1.0.0

Status:
Developer Guide

Category:
DevKit Guide

---

# 1. Purpose

This document defines the official usage of the SH-3 Development Kit (DevKit).

The DevKit standardizes project creation, code generation, validation, testing, documentation, and release preparation.

Its goals are:

- Accelerate development
- Enforce architectural consistency
- Reduce manual work
- Improve project quality
- Support reproducible workflows

---

# 2. DevKit Philosophy

The DevKit follows:

Everything Automated

+

Everything Reproducible

+

Everything Validated

The DevKit should generate code and project assets that conform to the SH-3 Architecture and Developer Guides.

---

# 3. Installation

Install the DevKit:

```bash
pip install sh3dev
```

Verify installation:

```bash
sh3dev --version
```

Display help:

```bash
sh3dev --help
```

---

# 4. Command Structure

General syntax:

```bash
sh3dev <command> <subcommand> [options]
```

Example:

```bash
sh3dev component create Planner
```

---

# 5. Project Commands

Create a new project:

```bash
sh3dev init MyProject
```

Upgrade project metadata:

```bash
sh3dev upgrade
```

Validate project structure:

```bash
sh3dev validate
```

---

# 6. Component Commands

Generate a component:

```bash
sh3dev component create Planner
```

Supported categories:

- runtime
- kernel
- service
- infrastructure
- persistence
- self_healing

Generated assets include:

- Interface
- Implementation
- Configuration
- Tests
- Documentation

---

# 7. Plugin Commands

Create a plugin:

```bash
sh3dev plugin create StoragePlugin
```

Validate a plugin:

```bash
sh3dev plugin validate
```

Package a plugin:

```bash
sh3dev plugin package
```

Publish a plugin:

```bash
sh3dev plugin publish
```

---

# 8. Documentation Commands

Generate documentation:

```bash
sh3dev docs build
```

Validate documentation:

```bash
sh3dev docs validate
```

Generate API documentation:

```bash
sh3dev docs api
```

---

# 9. RFC Commands

Create an RFC:

```bash
sh3dev rfc create
```

Validate RFC numbering:

```bash
sh3dev rfc validate
```

Generate RFC index:

```bash
sh3dev rfc index
```

---

# 10. ADR Commands

Create an ADR:

```bash
sh3dev adr create
```

Validate ADR references:

```bash
sh3dev adr validate
```

Generate ADR index:

```bash
sh3dev adr index
```

---

# 11. Validation Commands

Run project validation:

```bash
sh3dev validate
```

Validation should include:

- Project structure
- Architecture compliance
- Type checking
- Documentation consistency
- Configuration schema

---

# 12. Testing Commands

Run all tests:

```bash
sh3dev test
```

Run unit tests:

```bash
sh3dev test unit
```

Run integration tests:

```bash
sh3dev test integration
```

Run performance tests:

```bash
sh3dev test performance
```

---

# 13. Diagnostics

Display system health:

```bash
sh3dev health
```

Inspect registry:

```bash
sh3dev registry
```

Inspect event activity:

```bash
sh3dev events
```

Run diagnostics:

```bash
sh3dev diagnose
```

---

# 14. Build Commands

Build the project:

```bash
sh3dev build
```

Generate release artifacts:

```bash
sh3dev package
```

Verify artifacts:

```bash
sh3dev verify
```

---

# 15. Release Commands

Prepare a release:

```bash
sh3dev release prepare
```

Publish a release:

```bash
sh3dev release publish
```

Generate release notes:

```bash
sh3dev release notes
```

---

# 16. Configuration

The DevKit reads project configuration from:

```text
sh3.toml
```

Typical configuration includes:

- Project metadata
- Python version
- Documentation settings
- Validation options
- Plugin registry
- Build settings

---

# 17. Templates

The DevKit provides templates for:

- Components
- Plugins
- RFCs
- ADRs
- Documentation
- Test modules
- Configuration files

Generated templates should conform to SH-3 standards.

---

# 18. Continuous Integration

Bootstrap CI:

```bash
sh3dev bootstrap ci
```

Supported targets may include:

- GitHub Actions
- GitLab CI
- Azure Pipelines

Generated workflows should implement the SH-3 quality gates.

---

# 19. Extensibility

The DevKit should support extension through:

- Custom templates
- Plugin generators
- Validation extensions
- Documentation generators

Extensions should not require modification of the DevKit core.

---

# 20. Error Reporting

Command failures should report:

- Exit code
- Error summary
- Suggested resolution
- Relevant documentation

Messages should be actionable and concise.

---

# 21. Review Checklist

Verify that:

- Generated assets follow architecture.
- Validation succeeds.
- Templates remain current.
- Commands are documented.
- Output is deterministic.

---

# 22. Anti-Patterns

Avoid:

- Manual project scaffolding
- Editing generated files without understanding regeneration rules
- Skipping validation
- Using outdated templates
- Ignoring CLI diagnostics

---

# 23. Compliance Checklist

The DevKit is compliant when:

- Commands are deterministic.
- Generated assets follow SH-3 standards.
- Validation succeeds.
- Documentation is synchronized.
- Templates are versioned.
- CLI help is complete.

---

# 24. Final Definition

The SH-3 DevKit provides the standardized tooling required to create, validate, maintain, and release SH-3 projects while ensuring architectural consistency, developer productivity, and production readiness.

---

# End of Document
