# SH-3 DevKit Troubleshooting Guide Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Operations Support Documentation


---

# 1. Purpose

This document defines troubleshooting procedures for SH-3 DevKit.

The guide provides solutions for:

- Installation problems
- Import errors
- CLI failures
- Registry issues
- Generator problems
- Runtime failures


---

# 2. Troubleshooting Philosophy


SH-3 DevKit follows:



Detect

↓

Analyze

↓

Fix

↓

Validate



All fixes must preserve architecture rules.


---

# 3. Basic Diagnostic Flow


When an error occurs:



Check Python Version

↓

Check Installation

↓

Check Project Structure

↓

Check Configuration

↓

Run Validation

↓

Analyze Error



---

# 4. Environment Verification


Required:


```bash
python --version

Expected:

Python 3.12+
5. Package Installation Check

Verify:

python -m pip show sh3dev

If missing:

pip install -e .
6. CLI Not Found
Problem

Example:

sh3dev: command not found
Solution

Check:

python -m sh3dev --version

If working:

Problem:

PATH configuration
7. Module Not Found Error
Problem

Example:

No module named sh3dev
Cause

Possible:

Wrong Environment

↓

Package Not Installed

↓

Wrong Directory
Solution

Activate environment:

.venv\Scripts\activate

Install:

pip install -e .
8. Circular Import Error
Problem

Example:

ImportError:
cannot import name xxx
from partially initialized module
9. Circular Import Cause

Typical pattern:

commands

↓

registry

↓

commands

or:

service

↓

kernel

↓

service
10. Circular Import Solution

Apply:

Move Shared Interface

↓

Use Protocol

↓

Use Lazy Import

↓

Separate Initialization
11. Recommended Architecture

Bad:

Command

↓

Registry

↓

Command

Good:

Command

↓

Registry Interface

↓

Loader

↓

Command
12. Registry Loading Error
Problem

Commands are missing.

Example:

list command unavailable
13. Registry Debug

Check:

Registry

↓

Loader

↓

Registration

↓

Command Discovery
14. Registry Validation

Run:

sh3dev list

Expected:

info

version

list

create

rfc

validate

build

template
15. Configuration Error
Problem

Invalid configuration.

Check:

File Exists

↓

Schema Valid

↓

Version Compatible
16. Generator Error
Problem

Generated files are incorrect.

Check:

Template

↓

Generator

↓

Configuration

↓

Output Path
17. Filesystem Error

Common causes:

Invalid Path

Permission Error

Existing File Conflict
18. Safe Recovery

Recommended:

Backup

↓

Remove Generated Output

↓

Run Generator Again

↓

Validate
19. Validation Failure

Run:

sh3dev validate

Review:

Missing Files

Missing Directories

Invalid Documents

Configuration Errors
20. Runtime Startup Failure

Debug flow:

Bootstrap

↓

Container

↓

Registry

↓

Service Initialization
21. Runtime Debug Mode

Use:

sh3dev command --debug

Output:

Initialization State

Component Loading

Execution Trace
22. Build Failure

Check:

Dependencies

↓

Packaging Configuration

↓

Build Environment
23. Test Failure

Run:

pytest -v

Analyze:

Failed Test

↓

Component

↓

Root Cause
24. Performance Issue

Check:

Startup Time

Import Cost

Filesystem Scan

Registry Loading
25. Logging Strategy

Debug information should include:

Component

Operation

Result

Error

Avoid:

Secrets

Tokens

Credentials
26. Recovery Checklist
[ ] Python Version Checked

[ ] Environment Checked

[ ] Package Installed

[ ] Validation Executed

[ ] Error Reproduced

[ ] Root Cause Identified

[ ] Fix Verified
27. Production Incident Flow

For production:

Detect

↓

Collect Logs

↓

Stop Impact

↓

Fix

↓

Validate

↓

Release Patch
28. AI Assisted Debugging

Future support:

Error Report

↓

AI Analyzer

↓

Solution Proposal

↓

Validation

AI suggestions require verification.

29. Support Information

When reporting issues include:

SH-3 Version

Python Version

OS

Command

Error Log

Expected Result
30. Final Troubleshooting Criteria

Problem is resolved when:

Error Fixed

+

Validation PASS

+

Tests PASS

+

Architecture Maintained
End of Document

---

## 完成状態

```text
docs/devkit/

000-overview.md                  ✅
001-directory-layout.md          ✅
002-layer-architecture.md        ✅
003-command-framework.md         ✅
004-service-layer.md             ✅
005-configuration-layer.md       ✅
006-generator-layer.md            ✅
007-registry-layer.md             ✅
008-filesystem-layer.md           ✅
009-plugin-system.md              ✅
010-testing-strategy.md           ✅
011-packaging.md                  ✅
012-release-process.md            ✅
013-development-workflow.md       ✅
014-security-model.md             ✅
015-performance-guidelines.md     ✅
016-api-design.md                 ✅
017-cli-specification.md          ✅
018-validation-system.md          ✅
019-runtime-integration.md        ✅
020-architecture-conformance.md   ✅
021-ai-extension-framework.md      ✅
022-devkit-roadmap.md             ✅
023-contribution-guide.md          ✅
024-faq.md                         ✅
025-troubleshooting-guide.md       ✅
