# SH-3 Getting Started Guide

Version:
1.0.0

Status:
Developer Guide

Category:
Getting Started

---

# 1. Purpose

This document explains how to install, configure, and start developing with SH-3.

It is intended to help new developers create a working SH-3 project with minimal effort.

---

# 2. Requirements

Minimum requirements:

- Python 3.12+
- Git
- pip
- Virtual Environment

Recommended:

- VS Code
- Docker Desktop
- Make
- Ruff
- MyPy
- Pytest

---

# 3. Installation

Install the SH-3 DevKit:

```bash
pip install sh3dev
```

Verify installation:

```bash
sh3dev --version
```

---

# 4. Create a Project

Generate a new project:

```bash
sh3dev init MyProject
```

Result:

```text
MyProject/
├── foundation/
├── infrastructure/
├── runtime/
├── services/
├── kernel/
├── persistence/
├── self_healing/
├── docs/
├── tests/
├── pyproject.toml
└── README.md
```

---

# 5. Enter the Project

```bash
cd MyProject
```

---

# 6. Create a Virtual Environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

# 7. Install Dependencies

```bash
pip install -e .
```

Developer tools:

```bash
pip install ruff mypy pytest
```

---

# 8. Verify the Environment

Run:

```bash
python -m pytest
```

Expected:

```text
All tests passed
```

---

# 9. Verify Type Safety

```bash
mypy .
```

Expected:

```text
Success: no issues found
```

---

# 10. Verify Code Style

```bash
ruff check .
```

Expected:

```text
All checks passed
```

---

# 11. Build Documentation

Generate documentation:

```bash
sh3dev docs build
```

---

# 12. Generate RFC

Create a new RFC:

```bash
sh3dev rfc create
```

---

# 13. Generate a Component

Create a service:

```bash
sh3dev component create service Planner
```

Create a plugin:

```bash
sh3dev plugin create StoragePlugin
```

---

# 14. Run Validation

Validate the project:

```bash
sh3dev validate
```

Validation includes:

- Directory structure
- Configuration
- Type checking
- Architecture compliance

---

# 15. Continuous Integration

Bootstrap GitHub Actions:

```bash
sh3dev bootstrap ci
```

Generated:

```text
.github/workflows/ci.yml
```

---

# 16. Recommended Workflow

```
Create Project

↓

Implement Component

↓

Run Tests

↓

Validate

↓

Commit

↓

CI

↓

Release
```

---

# 17. Where to Go Next

Continue with:

- 002 Project Structure
- 003 Coding Standards
- 004 Type System
- 005 Component Development

---

# 18. Quick Checklist

Before writing code:

- Python installed
- Virtual environment activated
- Dependencies installed
- Tests passing
- Ruff passing
- MyPy passing

---

# 19. Troubleshooting

Common issues:

- Missing Python version
- Virtual environment not activated
- Missing dependencies
- Validation failures

See:

```
018-troubleshooting.md
```

---

# 20. Final Definition

After completing this guide, a developer should be able to:

- Create a SH-3 project
- Configure the environment
- Validate the project
- Begin implementing SH-3 components

---

# End of Document
