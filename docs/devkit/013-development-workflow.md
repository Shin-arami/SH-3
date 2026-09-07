# SH-3 DevKit Development Workflow Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Developer Process Architecture


---

# 1. Purpose

This document defines the official development workflow of SH-3 DevKit.

The workflow establishes:

- Development lifecycle
- Source control rules
- Review process
- Quality standards
- Collaboration model


---

# 2. Development Principles


SH-3 DevKit follows:



Small Change

↓

Validated Change

↓

Reviewed Change

↓

Integrated Change



Development must maintain:


- Quality
- Traceability
- Reproducibility


---

# 3. Development Lifecycle


Standard lifecycle:



Issue Creation

↓

Design

↓

Implementation

↓

Testing

↓

Review

↓

Merge

↓

Release



---

# 4. Repository Workflow


Recommended flow:



main

|

develop

|

feature branch



---

# 5. Branch Strategy


## Main Branch


Branch:



main



Purpose:


- Stable release
- Production state


Rules:


- Direct commits prohibited
- Protected branch


---

## Development Branch


Branch:



develop



Purpose:


- Integration
- Feature testing


---

## Feature Branch


Format:



feature/<name>



Example:



feature/plugin-loader



Purpose:


- New features
- Architecture changes


---

## Bugfix Branch


Format:



fix/<name>



Example:



fix/registry-import-error



---

## Release Branch


Format:



release/<version>



Purpose:


- Release preparation


---

# 6. Commit Rules


Commits must be:


- Small
- Atomic
- Descriptive


Format:



type: description



---

# 7. Commit Types


Supported:



feat:

fix:

docs:

refactor:

test:

build:

ci:

chore:



Examples:



feat: add rfc generator

fix: resolve registry import cycle

docs: update architecture spec



---

# 8. Commit Requirements


Each commit should:


- Build successfully
- Pass tests
- Avoid unrelated changes


---

# 9. Issue Workflow


All work begins with an Issue.


Issue contains:



Title

Description

Problem

Expected Result

Acceptance Criteria



---

# 10. Issue Categories


Recommended labels:



feature

bug

documentation

architecture

refactor

security

performance



---

# 11. Pull Request Workflow


PR flow:



Feature Branch

↓

Pull Request

↓

CI Validation

↓

Review

↓

Merge



---

# 12. Pull Request Requirements


PR must include:



Summary

Changes

Testing

Impact

Related Issue



---

# 13. Code Review Rules


Review checks:


## Architecture


- Correct layer
- Dependency direction


---

## Quality


- Type safety
- Test coverage
- Readability


---

## Compatibility


- No breaking changes
- Documentation updated


---

# 14. Development Environment


Required:



Python >=3.12

Git

Virtual Environment

Ruff

Mypy

Pytest



---

# 15. Local Development Setup


Example:


```bash
git clone repository

cd sh3dev

python -m venv .venv

pip install -e ".[dev]"
16. Before Commit

Run:

ruff check .

mypy .

pytest

All must pass.

17. Documentation Workflow

Architecture changes require:

Code Change

+

Documentation Update

Required documents:

Architecture
RFC
Changelog
18. Refactoring Rules

Refactoring must:

Preserve behavior
Include tests
Explain motivation

Large refactoring requires design discussion.

19. AI Development Support

Future SH-3 AI agents may assist:

Issue Analysis

↓

Design Proposal

↓

Code Generation

↓

Test Generation

↓

Review Support

AI output must follow the same workflow.

20. Production Development Standard

A change is accepted only when:

Implementation

+

Tests

+

Documentation

+

Review

=

Approved Change
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
012-release-process.md       ✅
013-development-workflow.md  ✅
