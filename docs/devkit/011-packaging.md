# SH-3 DevKit Packaging Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Deployment Architecture


---

# 1. Purpose

This document defines the packaging architecture of SH-3 DevKit.

The packaging system provides:

- Python package distribution
- CLI installation
- Version management
- Release artifact generation
- Deployment consistency


---

# 2. Packaging Goals


SH-3 DevKit must support:


## Editable Development Install


```bash
pip install -e .
Production Install
pip install sh3dev
CLI Execution
sh3dev --version

sh3dev info

sh3dev init ProjectName
3. Package Structure

Official structure:

sh3dev/

├── sh3dev/

│   ├── __init__.py

│   ├── __main__.py

│   ├── cli.py

│   ├── commands/

│   ├── services/

│   ├── config/

│   ├── registry/

│   ├── generators/

│   ├── validators/

│   ├── filesystem/

│   └── exceptions/

│

├── tests/

├── docs/

├── pyproject.toml

├── README.md

└── LICENSE
4. Build System

SH-3 DevKit uses modern Python packaging.

Required:

pyproject.toml

Build backend:

setuptools

or compatible PEP 517 backend.

5. pyproject.toml Requirements

Minimum metadata:

[project]

name = "sh3dev"

version = "1.0.0"

requires-python = ">=3.12"
6. Dependencies

Dependencies must be explicit.

Example:

dependencies = [

]

Rules:

Minimal dependencies
No unnecessary packages
Reproducible builds
7. CLI Entry Point

SH-3 DevKit exposes:

sh3dev

Entry configuration:

[project.scripts]

sh3dev = "sh3dev.cli:main"

Flow:

Terminal

↓

sh3dev

↓

cli.main()

↓

Command Dispatcher
8. Module Execution

SH-3 DevKit supports:

python -m sh3dev

Entry:

sh3dev/__main__.py

Implementation:

from sh3dev.cli import main

main()
9. Version Management

Version source:

Single source:

sh3dev/__init__.py

Example:

__version__ = "1.0.0"

No duplicated version definitions.

10. Release Artifact

Release produces:

dist/

├── sh3dev-x.x.x.tar.gz

└── sh3dev-x.x.x-py3-none-any.whl
11. Build Process

Standard release flow:

Update Version

↓

Run Tests

↓

Run Lint

↓

Build Package

↓

Verify Artifact

↓

Release
12. Build Command

Required:

python -m build

Generated:

dist/
13. Package Validation

Before release:

Check:

Package Import

CLI Startup

Version Output

Command Discovery

Project Generation
14. Installation Validation

Clean environment test:

Create Virtual Environment

↓

Install Package

↓

Execute sh3dev

↓

Run Validation
15. Dependency Isolation

Packages must avoid:

Global state
User environment dependency
Local development assumptions
16. Configuration Files

Managed files:

pyproject.toml

README.md

LICENSE

CHANGELOG.md
17. Development Mode

Developers use:

pip install -e ".[dev]"

Development extras:

[project.optional-dependencies]

dev = [
    "pytest",
    "ruff",
    "mypy"
]
18. CI Integration

CI pipeline:

Checkout

↓

Install

↓

Lint

↓

Type Check

↓

Test

↓

Build
19. Compatibility Policy

Supported:

Python >=3.12

Future:

Python 3.x

Compatibility changes require documentation update.

20. Future Expansion

Packaging architecture supports:

PyPI publishing
Private package registry
Enterprise distribution
Plugin package ecosystem
Automated release pipeline
End of Document

---

## 完成状態

現在:

```text
docs/devkit/

000-overview.md              ✅
001-directory-layout.md      ✅
002-layer-architecture.md    ✅
003-command-framework.md     ✅
004-service-layer.md         ✅
005-configuration-layer.md   ✅
006-generator-layer.md       ✅
007-registry-layer.md        ✅
008-filesystem-layer.md      ✅
009-plugin-system.md         ✅
010-testing-strategy.md      ✅
011-packaging.md             ✅
