# SH-3 DevKit API Design Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
API Architecture


---

# 1. Purpose

This document defines the API design architecture of SH-3 DevKit.

The API architecture provides:

- Stable extension points
- Clear component boundaries
- Backward compatibility
- External integration support


---

# 2. API Philosophy


SH-3 DevKit follows:



Stable Interface

Replaceable Implementation

Explicit Contract



APIs define behavior, not implementation.


---

# 3. API Categories


SH-3 DevKit separates APIs into:



Public API

↓

Extension API

↓

Internal API



---

# 4. Public API


Public API is officially supported.


Targets:


- External developers
- Plugins
- Automation tools


Examples:



Project API

Generator API

Registry API

Validation API



---

# 5. Internal API


Internal APIs are implementation details.


Examples:



Private Helpers

Internal Utilities

Runtime Components



Rules:


- May change without notice
- Must not be used externally


---

# 6. API Design Principles


## Protocol First


Interfaces are defined using protocols.


Example:


```python
class GeneratorProtocol(Protocol):

    def generate(
        self,
        request: object,
    ) -> GenerationResult:
        ...
Implementation Independence

API users depend on:

Protocol

not

Concrete Class
``` id="9q7x2p"


---

# 7. Type Safety


All public APIs require:


- Type hints
- Explicit return values
- Defined exceptions


Example:


```python
def validate(
    project: Path,
) -> ValidationResult:
    ...
8. API Naming Rules

Public classes:

PascalCase

Example:

ProjectConfig

GenerationResult

ValidationResult

Methods:

snake_case

Example:

load_config()

generate_project()
9. Data Model Design

Public data uses immutable models.

Example:

@dataclass(
    frozen=True,
    slots=True,
)
class ProjectInfo:

    name: str

    version: str
10. Result Objects

APIs return typed results.

Example:

@dataclass(frozen=True)
class OperationResult:

    success: bool

    message: str

Avoid:

dict[str, object]

for public interfaces.

11. Exception Design

APIs use explicit exceptions.

Hierarchy:

SH3Error

├── ConfigurationError

├── RegistryError

├── GenerationError

├── ValidationError

└── FilesystemError
12. API Versioning

SH-3 DevKit uses semantic versioning.

Format:

MAJOR.MINOR.PATCH
13. Breaking Changes

Breaking changes require:

Major Version Increase

Example:

1.x.x

↓

2.x.x
14. Backward Compatibility

Minor releases should maintain:

Existing APIs
Existing behavior
Existing plugins
15. Deprecation Policy

Deprecated APIs follow:

Announcement

↓

Warning

↓

Removal

Minimum migration period should be documented.

16. API Documentation

Public APIs require:

Description
Parameters
Return values
Exceptions
Examples
17. Plugin API

Plugin developers use:

PluginProtocol

RegistryProtocol

CommandProtocol

GeneratorProtocol
18. Automation API

Future automation tools may access:

SH-3 API

↓

Service Layer

↓

Execution Result

CLI behavior should map to API behavior.

19. AI Agent API

Future SH-3 AI systems may use:

AI Agent

↓

Public API

↓

Service Layer

↓

Core Execution

AI integration must not bypass API contracts.

20. API Testing

Public APIs require:

Contract Test

+

Integration Test

+

Compatibility Test
21. API Security

Public APIs must validate:

Input
Permissions
Capability
22. API Stability Levels

API maturity:

Experimental

↓

Stable

↓

Deprecated
23. External Developer Support

Official documentation provides:

API Reference
Plugin Guide
Examples
Migration Guide
24. Production API Criteria

An API is production ready when:

Defined Contract

+

Tests PASS

+

Documentation Complete

+

Compatibility Verified
End of Document

---

## 完成状態

現在:

```text
docs/devkit/

000-overview.md                ✅
001-directory-layout.md        ✅
002-layer-architecture.md      ✅
003-command-framework.md       ✅
004-service-layer.md           ✅
005-configuration-layer.md     ✅
006-generator-layer.md         ✅
007-registry-layer.md          ✅
008-filesystem-layer.md        ✅
009-plugin-system.md           ✅
010-testing-strategy.md        ✅
011-packaging.md               ✅
012-release-process.md         ✅
013-development-workflow.md    ✅
014-security-model.md          ✅
015-performance-guidelines.md  ✅
016-api-design.md              ✅
