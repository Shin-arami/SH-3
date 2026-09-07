# SH-3 DevKit Directory Layout Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Development Infrastructure Architecture


---

# 1. Purpose

This document defines the official directory layout of SH-3 DevKit.

The directory structure is designed to support:

- Maintainability
- Extensibility
- Testability
- Replaceable components
- Long-term evolution


---

# 2. Root Structure



sh3dev/

├── init.py
├── main.py
├── cli.py
│
├── commands/
├── services/
├── config/
├── registry/
├── generators/
├── validators/
├── filesystem/
├── initialization/
├── release/
├── monitoring/
├── integrations/
├── templates/
├── models/
├── protocols/
├── utils/
└── exceptions/



---

# 3. Core Package


## sh3dev/

Root package.

Responsibilities:

- Package initialization
- CLI entry point
- Shared package metadata


Files:


init.py
main.py
cli.py



---

# 4. CLI Layer


Location:


sh3dev/cli.py



Responsibilities:

- Argument parsing
- Application startup
- Command dispatch


Restrictions:

CLI must not contain:

- Business logic
- File generation logic
- Validation logic


---

# 5. Command Layer


Location:


sh3dev/commands/



Purpose:

Define user-facing commands.


Example:


commands/

├── info.py
├── version.py
├── init.py
├── build.py
├── release.py
├── validate.py
├── doctor.py
└── status.py



Responsibilities:

- Command metadata
- Argument handling
- Service invocation


Command must not:

- Directly access filesystem
- Generate files
- Parse configuration


---

# 6. Service Layer


Location:


sh3dev/services/



Purpose:

Application workflow layer.


Example:


services/

├── init_service.py
├── build_service.py
├── release_service.py
├── status_service.py
└── doctor_service.py



Responsibilities:

- Workflow execution
- Component coordination
- Business rules


Services are the main execution units.


---

# 7. Configuration Layer


Location:


sh3dev/config/



Structure:


config/

├── models.py
├── defaults.py
├── parser.py
├── loader.py
└── init.py



Responsibilities:

- Configuration loading
- Configuration validation
- Project metadata management


Single access point:

```python
ConfigLoader.load()
8. Registry Layer

Location:

sh3dev/registry/

Responsibilities:

Component registration
Discovery
Lookup

Examples:

CommandRegistry

TemplateRegistry

PluginRegistry

Registry must not execute business logic.

9. Generator Layer

Location:

sh3dev/generators/

Responsibilities:

File generation
Document generation
Template expansion

Examples:

RFCGenerator

ArchitectureGenerator

ReleaseNotesGenerator

GitHubIssueGenerator

Generators must be:

Stateless
Deterministic
Testable
10. Validator Layer

Location:

sh3dev/validators/

Responsibilities:

Structure validation
Configuration validation
Project validation

Examples:

ProjectValidator

RFCValidator

TemplateValidator

Validators return explicit results.

11. Filesystem Layer

Location:

sh3dev/filesystem/

Responsibilities:

Centralize file operations.

Example:

filesystem/

├── reader.py
├── writer.py
├── scanner.py
└── path.py

Direct pathlib usage should be minimized outside this layer.

12. Initialization Layer

Location:

sh3dev/initialization/

Responsibilities:

Generate new SH-3 projects.

Components:

ProjectInitializer

BootstrapGenerator
13. Release Layer

Location:

sh3dev/release/

Responsibilities:

Release preparation
Release metadata
Release reports
14. Integration Layer

Location:

sh3dev/integrations/

Responsibilities:

External systems.

Examples:

GitHub

CI/CD

External APIs
15. Templates

Location:

sh3dev/templates/

Responsibilities:

Store reusable generation templates.

Examples:

templates/

├── rfc/
├── architecture/
├── github/
└── project/
16. Models

Location:

sh3dev/models/

Responsibilities:

Shared data models.

Examples:

ProjectInfo

CommandMetadata

ValidationResult

BuildResult
17. Protocols

Location:

sh3dev/protocols/

Responsibilities:

Define replaceable interfaces.

Examples:

GeneratorProtocol

ValidatorProtocol

StorageProtocol

# 18. Exceptions

Location:

sh3dev/exceptions/

Responsibilities:

Central error definitions.

Requirements:

Explicit error types
No silent failures

# 19. Import Rules

Allowed dependency direction:

commands

↓

services

↓

config / registry / generators / validators

↓

filesystem


Forbidden:

filesystem

↓

commands
generator

↓

cli

Upper layers must never be imported by lower layers.

# 20. Production Requirement

The final package must support:

pip install -e .

and:

sh3dev status

sh3dev doctor

sh3dev init

# End of Document
