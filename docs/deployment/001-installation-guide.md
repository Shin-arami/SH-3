# SH-3 Installation Guide

Version:
1.0.0

Status:
Deployment Guide

Category:
Installation Guide

---

# 1. Purpose

This document defines the standard installation procedure for the SH-3 AI Operating Framework.

Its objectives are:

- Standardize installation
- Ensure reproducibility
- Verify environment readiness
- Reduce setup errors
- Support multiple deployment targets

---

# 2. Supported Platforms

Officially supported platforms include:

- Linux (x86_64, ARM64)
- macOS
- Windows
- Docker-compatible environments
- Kubernetes clusters
- Public cloud virtual machines

Platform-specific notes are documented separately.

---

# 3. System Requirements

Minimum requirements:

- Python 3.12+
- pip (latest recommended)
- Git
- UTF-8 locale
- Network access for dependency installation

Recommended resources:

- CPU: 4 cores
- Memory: 8 GB
- Storage: 5 GB free space

Production deployments may require additional resources.

---

# 4. Verify Python Installation

Check the Python version:

```bash
python --version
```

Expected output:

```text
Python 3.12.x
```

If multiple Python versions are installed, ensure the intended interpreter is used.

---

# 5. Create a Virtual Environment

Create an isolated environment:

```bash
python -m venv .venv
```

Activate the environment.

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows:

```powershell
.venv\Scripts\activate
```

---

# 6. Upgrade Package Tools

Upgrade the package manager:

```bash
python -m pip install --upgrade pip
```

Optionally upgrade build tools:

```bash
pip install --upgrade setuptools wheel
```

---

# 7. Install SH-3

Install the framework:

```bash
pip install sh3
```

Verify installation:

```bash
python -c "import sh3"
```

The import should complete without errors.

---

# 8. Install the DevKit

Install the development toolkit:

```bash
pip install sh3dev
```

Verify:

```bash
sh3dev --version
```

Display help:

```bash
sh3dev --help
```

---

# 9. Create a New Project

Initialize a project:

```bash
sh3dev init MyProject
```

Example project structure:

```text
MyProject/
├── docs/
├── src/
├── tests/
├── plugins/
├── configs/
├── pyproject.toml
└── sh3.toml
```

---

# 10. Validate the Project

Run validation:

```bash
sh3dev validate
```

Validation should confirm:

- Project structure
- Configuration
- Toolchain
- Documentation
- Dependencies

---

# 11. Run Initial Tests

Execute the default test suite:

```bash
sh3dev test
```

Expected result:

- All tests pass
- No validation errors
- Exit code 0

---

# 12. Verify Runtime Startup

Perform a basic startup verification:

```bash
sh3dev health
```

Recommended checks:

- Runtime initialized
- Registry available
- Event Bus active
- Configuration loaded

---

# 13. Optional Development Tools

Recommended tools:

- Ruff
- MyPy
- Pytest
- Git
- Visual Studio Code (or equivalent IDE)

These tools improve development productivity but are not strictly required for runtime operation.

---

# 14. Updating an Installation

Update SH-3:

```bash
pip install --upgrade sh3
```

Update the DevKit:

```bash
pip install --upgrade sh3dev
```

After updating:

```bash
sh3dev validate
```

---

# 15. Uninstalling

Remove SH-3:

```bash
pip uninstall sh3
```

Remove the DevKit:

```bash
pip uninstall sh3dev
```

Delete any virtual environments and generated artifacts if they are no longer required.

---

# 16. Common Installation Issues

Typical issues include:

- Unsupported Python version
- Missing virtual environment activation
- Network connectivity problems
- Dependency conflicts
- Incorrect PATH configuration

Consult the Troubleshooting Guide for detailed resolutions.

---

# 17. Post-Installation Checklist

Verify:

- Python version supported
- Virtual environment active
- SH-3 installed
- DevKit installed
- Project initialized
- Validation completed
- Tests passed
- Runtime starts successfully

---

# 18. Final Definition

The SH-3 Installation Guide defines the standard process for preparing an environment, installing the framework and DevKit, validating the installation, and confirming operational readiness before development or deployment.

---

# End of Document
