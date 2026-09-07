# GOVERNANCE.md

# SH-3 Governance Model

## Overview

This document defines the governance model for the SH-3 project.

SH-3 is developed as a production-oriented AI Operating System Framework. Long-term stability, transparency, and technical quality are prioritized over short-term implementation speed.

---

# Project Principles

All governance decisions should follow the SH-3 principles:

* Everything Event Driven
* Everything Replaceable
* Everything Typed
* Everything Testable

Technical decisions should prioritize:

* Architecture consistency
* Maintainability
* Security
* Reliability
* Backward compatibility
* Long-term sustainability

---

# Project Roles

## Users

Users:

* Use SH-3.
* Report issues.
* Provide feedback.
* Suggest improvements.

Users do not require approval to participate in discussions.

---

## Contributors

Contributors:

* Submit Issues.
* Create Pull Requests.
* Improve documentation.
* Add tests.
* Review changes.

Contributors should follow:

* CONTRIBUTING.md
* CODE_OF_CONDUCT.md

---

## Maintainers

Maintainers are responsible for:

* Reviewing Pull Requests.
* Managing Issues.
* Reviewing RFCs.
* Maintaining project quality.
* Preparing releases.
* Protecting project stability.

Maintainers have authority to:

* Request changes.
* Reject unsafe changes.
* Merge approved contributions.
* Manage project milestones.

---

# Decision Making

SH-3 uses a technical consensus model.

Decisions should be based on:

* Technical evidence
* Architecture compatibility
* Testing results
* Long-term impact

Personal preference should not override technical reasoning.

---

# RFC Process

Architecture-level changes require an RFC.

Examples:

* New subsystem
* Kernel redesign
* Runtime architecture changes
* New protocols
* Public API changes

RFC lifecycle:

```text
Draft
  |
  v
Review
  |
  v
Discussion
  |
  v
Accepted
  |
  v
Implementation
```

---

# RFC Status

RFC documents may have these states:

| Status      | Meaning                     |
| ----------- | --------------------------- |
| Draft       | Proposal under development  |
| Review      | Open for technical feedback |
| Accepted    | Approved for implementation |
| Implemented | Code completed              |
| Deprecated  | No longer recommended       |
| Rejected    | Not accepted                |

---

# Breaking Changes

Breaking changes require special review.

A breaking change includes:

* Public API removal
* Data format changes
* Protocol changes
* Configuration incompatibility
* Behavioral changes affecting users

Required actions:

1. Document the reason.
2. Provide migration guidance.
3. Update RFC documentation.
4. Announce release impact.

---

# Release Management

SH-3 follows semantic versioning.

Format:

```text
MAJOR.MINOR.PATCH
```

Example:

```text
2.1.0
```

---

## Major Release

Used for:

* Breaking changes
* Large architecture changes
* Major compatibility changes

---

## Minor Release

Used for:

* New features
* New modules
* Backward-compatible improvements

---

## Patch Release

Used for:

* Bug fixes
* Documentation fixes
* Security fixes

---

# Branch Strategy

Recommended branches:

```text
main

develop

feature/*

bugfix/*

release/*
```

---

# Pull Request Requirements

A Pull Request should include:

* Clear description
* Related Issue
* Tests
* Documentation changes
* Compatibility considerations

Required checks:

* Tests pass
* Ruff passes
* Mypy passes
* CI passes

---

# Architecture Authority

Architecture decisions should be recorded through:

* RFC documents
* ADR documents
* Architecture documentation

Implementation should follow approved architecture.

---

# Repository Management

The project maintains:

* Issues for tasks
* Discussions for proposals
* RFCs for architecture
* Pull Requests for implementation
* Releases for distribution

Each system has a clear purpose.

---

# Security Decisions

Security-related decisions take priority over convenience.

Security issues follow:

```text
Report
  |
  v
Verification
  |
  v
Fix
  |
  v
Release
```

according to SECURITY.md.

---

# AI Development Policy

AI-assisted development is allowed.

However:

* Generated code must be reviewed.
* Generated designs must be validated.
* Tests are required.
* Architecture consistency must be maintained.

AI tools assist development but do not replace engineering responsibility.

---

# Future Maintainer Succession

The project should avoid depending on a single individual.

Future maintainers should be selected based on:

* Technical contribution
* Understanding of architecture
* Responsible communication
* Commitment to project quality

---

# Final Principle

SH-3 should evolve through:

* Clear specifications
* Transparent decisions
* Tested implementations
* Respectful collaboration

The goal is to build a reliable and extensible AI Operating System Framework for the long term.
