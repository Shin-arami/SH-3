# SH-3 Contributing Guide

Version:
1.0.0

Status:
Developer Guide

Category:
Contributing

---

# 1. Purpose

This document defines the contribution workflow for SH-3.

Its objectives are:

- Maintain project quality
- Standardize collaboration
- Simplify code review
- Preserve architectural consistency
- Enable traceable decision making

All contributors should follow this guide.

---

# 2. Contribution Principles

Every contribution should be:

- Small
- Reviewable
- Tested
- Documented
- Traceable

Large changes should be divided into incremental pull requests where practical.

---

# 3. Before Contributing

Before writing code:

- Read the Architecture Specification
- Review relevant RFCs
- Review applicable ADRs
- Read the Developer Guide
- Search for existing issues

Understanding the existing design reduces rework.

---

# 4. Branch Strategy

Recommended branch names:

```text
feature/<name>
bugfix/<name>
hotfix/<name>
release/<version>
docs/<topic>
refactor/<topic>
```

Branch names should be descriptive and concise.

---

# 5. Issue Workflow

For non-trivial work:

1. Create or identify an issue.
2. Confirm scope.
3. Link implementation work to the issue.
4. Update status as work progresses.

Issues should describe the problem before proposing a solution.

---

# 6. RFC Workflow

An RFC is recommended for:

- New architectural features
- Breaking changes
- Public API additions
- Cross-layer changes

Implementation should begin only after the RFC process is complete when required.

---

# 7. ADR Workflow

Create an ADR when:

- A significant architectural decision is made.
- Multiple alternatives are evaluated.
- Long-term rationale should be preserved.

ADRs document decisions, not implementation details.

---

# 8. Development Workflow

Recommended sequence:

```
Issue

↓

Branch

↓

Implementation

↓

Tests

↓

Documentation

↓

Validation

↓

Pull Request
```

Each step should complete before proceeding to the next.

---

# 9. Commit Messages

Use concise, descriptive commit messages.

Recommended style:

```text
feat: add planner registry

fix: resolve event ordering

docs: update developer guide

refactor: simplify scheduler
```

Each commit should represent one logical change.

---

# 10. Pull Requests

A pull request should include:

- Summary
- Motivation
- Related issue
- Testing performed
- Documentation updates
- Compatibility considerations

Keep pull requests focused on a single objective.

---

# 11. Code Review

Reviewers should verify:

- Architecture compliance
- Readability
- Type safety
- Test coverage
- Documentation
- Security considerations
- Performance impact

Constructive feedback is encouraged.

---

# 12. Quality Gates

Before merge:

- Ruff passes
- MyPy passes
- Tests pass
- Documentation updated
- CI succeeds

Pull requests should not bypass quality gates.

---

# 13. Documentation

Documentation should be updated whenever:

- Public APIs change
- Configuration changes
- Behavior changes
- Architecture changes

Code and documentation should remain synchronized.

---

# 14. Backward Compatibility

Contributors should evaluate:

- Public API compatibility
- Event schema compatibility
- Plugin compatibility
- Configuration compatibility

Breaking changes require clear justification.

---

# 15. Release Integration

Merged contributions should:

- Reference the appropriate release milestone.
- Update release notes where applicable.
- Include migration guidance if required.

---

# 16. Community Conduct

Contributors should:

- Communicate respectfully
- Focus on technical discussion
- Welcome constructive feedback
- Document disagreements through RFCs or ADRs when necessary

Technical decisions should be evidence-based.

---

# 17. Review Checklist

Before requesting review, verify:

- Scope is limited.
- Tests pass.
- Static analysis passes.
- Documentation is updated.
- Commits are organized.
- Merge conflicts are resolved.

---

# 18. Anti-Patterns

Avoid:

- Large unrelated pull requests
- Force-pushing after review without explanation
- Mixing refactoring with feature work
- Skipping documentation
- Ignoring review comments
- Bypassing CI

---

# 19. Compliance Checklist

A contribution is compliant when:

- Linked work items are identified.
- Coding standards are followed.
- Tests and documentation are complete.
- Quality gates pass.
- Review feedback is addressed.

---

# 20. Final Definition

The SH-3 Contributing Guide defines a consistent collaboration workflow that preserves architectural integrity, software quality, and long-term maintainability while enabling efficient contributions from individual developers and larger teams.

---

# End of Document
