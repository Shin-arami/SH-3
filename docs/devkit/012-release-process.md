# SH-3 DevKit Release Process Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Release Engineering Architecture


---

# 1. Purpose

This document defines the official release process of SH-3 DevKit.

The release process ensures:

- Stable version delivery
- Reproducible builds
- Quality verification
- Deployment consistency


---

# 2. Release Philosophy


SH-3 DevKit follows:



Every Release Must Be Verified



A release is valid only after:



Source

Tests

Documentation

Artifact

Validation



---

# 3. Release Types


SH-3 DevKit defines:


## Patch Release


Format:



1.0.x



Purpose:


- Bug fixes
- Documentation fixes


---

## Minor Release


Format:



1.x.0



Purpose:


- New features
- Compatible extensions


---

## Major Release


Format:



x.0.0



Purpose:


- Breaking changes
- Architecture changes


---

# 4. Version Management


Version follows:



MAJOR.MINOR.PATCH



Example:



1.0.0



Version source:



sh3dev/init.py



---

# 5. Release Lifecycle


Official flow:



Development

↓

Feature Complete

↓

Validation

↓

Release Candidate

↓

Final Release

↓

Deployment



---

# 6. Release Preparation


Before release:


Required:



Update Version

↓

Update CHANGELOG

↓

Update Documentation

↓

Run Tests

↓

Run Build



---

# 7. Quality Gate


Release requires:


## Code Quality



ruff PASS



---

## Type Safety



mypy PASS



---

## Tests



pytest PASS



---

## Build



python -m build PASS



---

# 8. Release Candidate


Release Candidate format:



1.0.0-rc.1



Purpose:


- Final verification
- External testing
- Regression detection


---

# 9. CHANGELOG Management


Every release requires:



CHANGELOG.md



Structure:


```markdown
# Version 1.0.0

## Added

## Changed

## Fixed

## Security
10. Git Tag Policy

Release tags:

v1.0.0

Rules:

Immutable tags
Version matching
Release notes attached
11. Release Branch

Recommended:

main

↓

release/x.y.z

↓

tag vx.y.z
12. Build Process

Release build:

Clean Environment

↓

Install Dependencies

↓

Run Validation

↓

Build Package

↓

Verify Artifact
13. Artifact Verification

Verify:

Wheel Installation

↓

CLI Startup

↓

Version Output

↓

Command Listing

↓

Project Generation
14. Publishing

Supported targets:

PyPI
Public Distribution
Private Registry
Enterprise Distribution
Internal Repository
Organization Release
15. CI/CD Release Pipeline

Recommended pipeline:

Push Tag

↓

CI Trigger

↓

Quality Gate

↓

Build Artifact

↓

Publish

↓

Release Notes
16. Rollback Policy

If release failure occurs:

Stop Deployment

↓

Identify Cause

↓

Create Fix

↓

New Patch Release

Existing releases must not be modified.

17. Release Validation

After release:

Verify:

Installation

↓

CLI Execution

↓

Core Commands

↓

Generation Flow

↓

Validation Flow
18. Release Documentation

Every release requires:

Release Notes

CHANGELOG

Migration Notes

API Changes
19. Automated Release Support

Future support:

Automatic version bump
Automated changelog generation
Artifact signing
Deployment automation
20. Production Release Criteria

SH-3 DevKit release is approved when:

Tests PASS

+

Build PASS

+

Documentation PASS

+

Validation PASS

+

Artifact Verified
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
