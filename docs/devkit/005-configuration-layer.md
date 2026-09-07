# SH-3 DevKit Configuration Layer Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Core Infrastructure Architecture


---

# 1. Purpose

This document defines the Configuration Layer architecture of SH-3 DevKit.

The Configuration Layer provides a unified configuration system for all DevKit components.

The purpose is to eliminate:

- Duplicated configuration logic
- Hard-coded values
- Hidden environment dependencies
- Uncontrolled configuration access


---

# 2. Position


Configuration Layer belongs to the Application Core Layer.



Command

↓

Service

↓

Configuration Layer

↓

Configuration Source



All application components obtain configuration through this layer.


---

# 3. Design Principles


## Single Source of Truth


All project configuration must be resolved through:


```python
ConfigLoader.load()

No component may directly parse:

pyproject.toml
environment variables
configuration files
Immutable Configuration

Loaded configuration must be immutable.

Requirements:

frozen dataclass
explicit typing
no runtime mutation
Explicit Configuration

Every required dependency must be visible.

Forbidden:

GLOBAL_CONFIG

Allowed:

service = BuildService(
    config=config,
)
4. Directory Structure
sh3dev/config/

├── __init__.py
├── models.py
├── defaults.py
├── parser.py
└── loader.py
5. Configuration Model

Configuration data is represented by typed models.

Example:

@dataclass(
    frozen=True,
    slots=True,
)
class ProjectConfig:

    name: str

    version: str

    python_version: str

    architecture: str

    root: Path
6. Configuration Objects

Main models:

ProjectConfig

Contains:

Project name
Version
Root path
Architecture
RuntimeConfig

Contains:

Python version
Execution options
Environment information
GitHubConfig

Contains:

Repository information
Workflow settings
7. Configuration Sources

Supported sources:

pyproject.toml

        ↓

Environment Variables

        ↓

Default Values

Priority:

Explicit project configuration
Environment configuration
Default configuration
8. Parser Layer

Location:

config/parser.py

Responsibility:

Convert external configuration into raw data.

Example:

pyproject.toml

↓

dict[str, object]

Parser does not create application models.

9. Loader Layer

Location:

config/loader.py

Responsibility:

Convert raw configuration into typed models.

Flow:

Parser

↓

Validation

↓

ProjectConfig

↓

Application
10. Default Configuration

Location:

config/defaults.py

Defines:

DEFAULT_VERSION = "1.0.0"

DEFAULT_PYTHON = "3.12"

DEFAULT_ARCHITECTURE = (
    "Layered Kernel System"
)

Default values must be centralized.

11. Configuration Lifecycle

Standard lifecycle:

Application Start

↓

Locate Configuration

↓

Parse

↓

Validate

↓

Create Model

↓

Inject Dependencies

↓

Execute
12. Validation Rules

Configuration validation checks:

Required Fields

Example:

name
version
root
Type Validation

Example:

version: str

root: Path
Path Validation

Check:

Exists
Accessible
Correct format
13. Error Handling

Configuration errors use explicit exceptions.

Example:

raise ConfigurationError(
    "Missing project version"
)

No silent fallback is allowed for invalid configuration.

14. Service Integration

Example:

BuildService

↓

ConfigLoader

↓

ProjectConfig

↓

Build Process

Services receive configuration explicitly.

15. Testing Requirements

Required tests:

tests/config/

├── test_models.py
├── test_parser.py
├── test_loader.py
└── test_defaults.py

Test cases:

Valid configuration
Missing fields
Invalid types
Default values
Environment override
16. Future Extension

Configuration Layer supports:

YAML Provider
JSON Provider
Remote Configuration
Secret Manager
Environment Service

Through replaceable interfaces.

End of Document
