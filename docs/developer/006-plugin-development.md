# SH-3 Plugin Development Guide

Version:
1.0.0

Status:
Developer Guide

Category:
Plugin Development

---

# 1. Purpose

This document defines the standard process for developing, packaging, distributing, and maintaining SH-3 plugins.

Plugins extend the SH-3 framework without modifying the core implementation.

---

# 2. Plugin Philosophy

Every plugin shall be:

- Replaceable
- Isolated
- Versioned
- Typed
- Testable
- Secure

A plugin should extend behavior, not alter the framework's architecture.

---

# 3. Plugin Types

Typical plugin categories include:

- Storage
- Memory
- LLM
- Event
- Runtime
- Authentication
- Metrics
- Tracing
- Persistence
- Custom Service

Each category follows the same lifecycle and registration process.

---

# 4. Plugin Lifecycle

Standard lifecycle:

```
Discovered

↓

Validated

↓

Registered

↓

Initialized

↓

Started

↓

Running

↓

Stopped

↓

Unloaded
```

Each transition should be safe and repeatable.

---

# 5. Canonical Directory Layout

```text
plugins/

my_plugin/

├── __init__.py
├── manifest.py
├── plugin.py
├── config.py
├── events.py
├── models.py
├── exceptions.py
├── README.md
└── tests/
```

The layout should remain consistent across plugins.

---

# 6. Plugin Manifest

Every plugin should declare metadata including:

- Name
- Identifier
- Version
- Description
- Author
- License
- Compatible SH-3 versions
- Required capabilities
- Optional capabilities

The manifest serves as the plugin's public identity.

---

# 7. Public Interface

Expose functionality through a stable interface.

Prefer `Protocol` definitions for public contracts.

Example:

```python
class StoragePlugin(Protocol):
    def save(self, key: str, value: bytes) -> None: ...
```

---

# 8. Registration

Plugins register with the Kernel plugin registry.

Registration should include:

- Plugin identifier
- Interface
- Implementation
- Version
- Metadata

Registration must be idempotent.

---

# 9. Dependency Injection

Dependencies are provided by the framework.

Plugins should not instantiate core services directly.

Constructor injection is preferred.

---

# 10. Configuration

Configuration should be:

- External
- Immutable
- Validated
- Version-aware

Avoid embedding configuration values in source code.

---

# 11. Event Integration

Plugins communicate through the Event Bus.

Typical flow:

```
Receive Event

↓

Process

↓

Publish Event
```

Plugins should avoid direct dependencies on unrelated components.

---

# 12. Resource Management

Plugins should:

- Allocate resources during initialization.
- Release resources during shutdown.
- Avoid resource leaks.
- Support repeated load/unload cycles.

---

# 13. Version Compatibility

Every plugin declares:

- Minimum supported SH-3 version
- Maximum tested SH-3 version (optional)
- Plugin version

Breaking interface changes require a major version increment.

---

# 14. Security

Plugins should:

- Validate external input.
- Avoid executing arbitrary code.
- Respect permission boundaries.
- Avoid exposing secrets.

Security-sensitive plugins require additional review.

---

# 15. Observability

Plugins should integrate with the SH-3 observability subsystem.

Recommended outputs:

- Logs
- Metrics
- Health status
- Trace information

---

# 16. Testing

Each plugin requires:

- Unit tests
- Integration tests
- Compatibility tests

Suggested structure:

```text
tests/

test_manifest.py
test_plugin.py
test_events.py
test_config.py
```

---

# 17. Packaging

Plugins should be distributed as standard Python packages.

Required files:

- pyproject.toml
- README.md
- LICENSE
- Manifest

Package metadata should match the plugin manifest.

---

# 18. Distribution

Recommended distribution methods:

- Internal registry
- Python package index
- Source repository

Every release should include versioned release notes.

---

# 19. DevKit Integration

The SH-3 DevKit should provide commands such as:

```bash
sh3dev plugin create MyPlugin
```

```bash
sh3dev plugin validate
```

```bash
sh3dev plugin package
```

```bash
sh3dev plugin publish
```

These commands should generate or validate the canonical plugin structure.

---

# 20. Documentation

Every plugin should include:

- Purpose
- Installation
- Configuration
- Public API
- Events
- Examples
- Compatibility information

---

# 21. Review Checklist

During review, verify:

- Manifest completeness
- Stable public interface
- Dependency injection
- Event integration
- Security considerations
- Version compatibility
- Test coverage
- Documentation

---

# 22. Anti-Patterns

Avoid:

- Modifying SH-3 core packages
- Circular dependencies
- Hidden global state
- Runtime monkey patching
- Hard-coded configuration
- Untyped public APIs

---

# 23. Compliance Checklist

A plugin is compliant when:

- Canonical directory layout is followed.
- Manifest is complete.
- Public APIs are fully typed.
- Registration succeeds.
- Dependencies are injected.
- Tests pass.
- Documentation is complete.
- Version compatibility is declared.

---

# 24. Final Definition

A SH-3 plugin is a versioned, isolated, replaceable extension that integrates with the framework through stable interfaces, dependency injection, and the event-driven architecture while remaining independent of the core implementation.

---

# End of Document
