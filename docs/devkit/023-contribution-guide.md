# SH-3 DevKit Contribution Guide Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Developer Community Architecture


---

# 1. Purpose

This document defines contribution guidelines for SH-3 DevKit.

The contribution system provides:

- Consistent development process
- High quality contributions
- Clear review standards
- Community collaboration


---

# 2. Contribution Philosophy


SH-3 DevKit follows:



Contribution

Review

Validation

=

Quality Improvement



Every contribution must preserve architecture integrity.


---

# 3. Contributor Types


Supported contributors:



Core Developer

Plugin Developer

Documentation Contributor

Community Developer

AI Development Agent



---

# 4. Contribution Areas


Contributions include:


## Code


- Features
- Bug fixes
- Refactoring


## Documentation


- Architecture documents
- Guides
- Examples


## Testing


- Unit tests
- Integration tests
- Validation rules


## Extensions


- Plugins
- Generators
- Validators


---

# 5. Before Contributing


Contributor should:



Read Architecture

↓

Understand Layer Rules

↓

Check Existing Issues

↓

Create Proposal



---

# 6. Development Environment


Required:



Python >=3.12

Git

Virtual Environment

Ruff

Mypy

Pytest



---

# 7. Repository Setup


Example:


```bash
git clone <repository>

cd sh3dev

python -m venv .venv

pip install -e ".[dev]"
8. Branch Rules

Contributions use branches.

Feature:

feature/<name>

Bug fix:

fix/<name>

Documentation:

docs/<name>
``` id="h5m8az"


---

# 9. Commit Rules


Commits must follow:



type: description



Types:



feat

fix

docs

refactor

test

build

ci

chore



Example:



feat: add plugin validator



---

# 10. Code Style


Code must follow:


- Type annotations
- Ruff rules
- Clear naming
- Minimal complexity


---

# 11. Architecture Rules


Contributions must respect:



Dependency Direction

Protocol Design

Layer Separation

Replaceable Components



---

# 12. Forbidden Changes


Avoid:



Direct Layer Violation

Global State

Hidden Dependencies

Unvalidated External Access



---

# 13. Issue Creation


Issues should contain:



Title

Problem Description

Expected Behavior

Impact

Proposal



---

# 14. Issue Labels


Recommended:



feature

bug

documentation

architecture

security

performance

plugin



---

# 15. Pull Request Requirements


PR must include:



Summary

Implementation Details

Testing Result

Documentation Impact

Related Issue



---

# 16. Pull Request Checklist


Example:


```markdown
- [ ] Tests added
- [ ] Documentation updated
- [ ] Type checking passed
- [ ] Lint passed
- [ ] Architecture validated
``` id="c8t4sy"


---

# 17. Code Review Policy


Review checks:


## Architecture


- Correct layer
- Correct dependency


## Quality


- Readability
- Maintainability
- Test coverage


## Security


- Safe implementation
- Input validation


---

# 18. Review Approval


Required:



CI PASS

Reviewer Approval



---

# 19. Documentation Contribution


Documentation changes require:


- Correct format
- Version information
- Architecture consistency


---

# 20. Plugin Contribution


Plugins require:



Manifest

Protocol Compliance

Tests

Documentation



---

# 21. Security Reporting


Security issues should not be publicly disclosed immediately.


Process:



Report

↓

Review

↓

Fix

↓

Release



---

# 22. AI Assisted Contribution


AI generated changes require:



Human Review

Tests

Validation



AI output follows the same contribution rules.


---

# 23. Community Standards


Contributors should maintain:


- Respectful communication
- Technical discussion
- Constructive reviews


---

# 24. Future Contribution Expansion


Future support:


- Plugin marketplace
- Community packages
- Extension certification
- AI contributor workflow


---

# 25. Contribution Acceptance Criteria


Contribution accepted when:



Implementation PASS

Tests PASS

Review PASS

Documentation PASS



---

# End of Document
