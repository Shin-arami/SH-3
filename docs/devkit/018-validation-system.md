# SH-3 DevKit Validation System Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Quality Assurance Architecture


---

# 1. Purpose

This document defines the Validation System architecture of SH-3 DevKit.

The Validation System provides automated verification for:

- Project structure
- Configuration
- Documentation
- Generated artifacts
- Runtime requirements


---

# 2. Validation Philosophy


SH-3 DevKit follows:



Validate Early

Validate Automatically

Validate Continuously



Validation is required before:

- Build
- Release
- Deployment


---

# 3. Validation Position


Validation belongs to the Service Layer.



CLI

↓

Validator

↓

Validation Engine

↓

Filesystem / Configuration

↓

Validation Result



---

# 4. Validation Principles


## Deterministic


Same input produces same result.


---

## Explicit


Validation rules must be defined.


---

## Independent


Validators must be replaceable.


---

# 5. Directory Structure


``` id="k7j5wb"
sh3dev/validators/

├── __init__.py

├── base.py

├── project.py

├── structure.py

├── configuration.py

├── documentation.py

└── result.py
6. Validator Protocol

All validators implement:

class ValidatorProtocol(Protocol):

    name: str


    def validate(
        self,
        target: object,
    ) -> ValidationResult:
        ...
7. Validation Result Model

All validation returns:

@dataclass(
    frozen=True,
    slots=True,
)
class ValidationResult:

    valid: bool

    errors: tuple[str, ...]

    warnings: tuple[str, ...]
8. Validation Categories

SH-3 DevKit validates:

Project

├── Structure

├── Configuration

├── Documentation

├── Source

├── Tests

└── Build
9. Project Structure Validation

Purpose:

Verify required directories and files.

Example:

Required:

foundation/

runtime/

services/

kernel/

docs/

tests/
10. Structure Validator

Responsibilities:

Directory existence
Required files
Naming rules

Example:

StructureValidator.validate(
    project
)
11. Configuration Validation

Checks:

File existence
Schema correctness
Required fields
Version compatibility

Example:

pyproject.toml

configuration.yaml
12. Documentation Validation

Checks:

Required documents
RFC format
Version consistency

Example:

docs/rfc/

docs/architecture/
13. RFC Validation

RFC validator checks:

RFC Number

Title

Metadata

Sections

Format

Example:

rfc-0001-foundation.md
14. Source Validation

Checks:

Import correctness
Package structure
Type requirements
15. Test Validation

Checks:

Test directory exists
Test execution result
Coverage requirement
16. Build Validation

Checks:

Package Build

↓

Artifact Creation

↓

Installation Test
17. Validation Pipeline

Standard flow:

Target Project

↓

Validator Discovery

↓

Validation Execution

↓

Result Aggregation

↓

Report Generation
18. Validation Report

Human output:

Project: SH-3

Structure: OK

Documents: OK

Status: SUCCESS

Machine output:

{
 "valid": true,
 "errors": []
}
19. Validation Severity

Levels:

ERROR

WARNING

INFO

ERROR blocks execution.

20. CI Integration

CI flow:

Commit

↓

Validation

↓

Tests

↓

Build

↓

Release
21. CLI Integration

Command:

sh3dev validate

Execution:

CLI

↓

ValidateCommand

↓

ValidationService

↓

Validators
22. Performance Requirements

Validators should:

Avoid unnecessary scans
Reuse loaded data
Support incremental validation
23. Extension Model

Future validators:

Custom Validator

↓

ValidatorProtocol

↓

ValidatorRegistry
24. AI Validation Support

Future SH-3 AI systems may provide:

AI Analyzer

↓

Validation Engine

↓

Quality Recommendation

AI suggestions do not replace deterministic validation.

25. Production Validation Criteria

Project is valid when:

Structure PASS

+

Configuration PASS

+

Tests PASS

+

Build PASS

+

Documentation PASS
End of Document

---

## 完成状態

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
017-cli-specification.md       ✅
018-validation-system.md       ✅
