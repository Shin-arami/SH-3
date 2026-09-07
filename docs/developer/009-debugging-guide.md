# SH-3 Debugging Guide

Version:
1.0.0

Status:
Developer Guide

Category:
Debugging Guide

---

# 1. Purpose

This document defines the recommended debugging and diagnostic practices for SH-3.

The objectives are:

- Reduce troubleshooting time
- Improve observability
- Standardize diagnostics
- Support production incident analysis

---

# 2. Debugging Philosophy

Debugging should be:

- Reproducible
- Evidence-based
- Non-invasive
- Traceable

Avoid modifying production behavior solely for debugging.

---

# 3. Diagnostic Workflow

Recommended workflow:

```
Detect

↓

Collect Evidence

↓

Reproduce

↓

Isolate

↓

Identify Root Cause

↓

Fix

↓

Verify

↓

Prevent Regression
```

---

# 4. Logging

Use the SH-3 logging abstraction.

Recommended levels:

- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

Logs should include sufficient context without exposing sensitive data.

---

# 5. Correlation IDs

All related operations should share a Correlation ID.

Use Correlation IDs to:

- Trace workflows
- Connect distributed events
- Analyze failures

---

# 6. Event Inspection

When debugging event-driven behavior, verify:

- Event creation
- Publication
- Routing
- Subscription
- Handler execution
- Completion

Unexpected event sequences should be documented.

---

# 7. Registry Diagnostics

Verify:

- Registered components
- Duplicate registrations
- Missing registrations
- Version compatibility
- Dependency resolution

The registry should expose diagnostic information for inspection.

---

# 8. Runtime Diagnostics

Inspect:

- Lifecycle state
- Active tasks
- Scheduler status
- Queue depth
- Worker health

Unexpected state transitions should be logged.

---

# 9. Service Diagnostics

Check:

- Initialization status
- Dependency availability
- Health status
- Configuration
- Resource usage

Services should expose diagnostic endpoints or interfaces where appropriate.

---

# 10. Persistence Diagnostics

Verify:

- Storage connectivity
- Read/write operations
- Serialization
- Snapshot integrity
- Recovery state

Avoid modifying production data during diagnostics.

---

# 11. Plugin Diagnostics

Confirm:

- Manifest validity
- Registration
- Compatibility
- Lifecycle state
- Configuration loading

Plugins should report initialization failures clearly.

---

# 12. Configuration Diagnostics

Inspect:

- Loaded configuration
- Active environment
- Overrides
- Validation errors
- Schema version

Configuration differences should be easy to identify.

---

# 13. Thread Diagnostics

Investigate:

- Deadlocks
- Starvation
- Long-running tasks
- Synchronization issues

Document concurrency assumptions for each component.

---

# 14. Memory Diagnostics

Monitor:

- Heap usage
- Object growth
- Cache size
- Resource retention

Investigate unexpected memory growth before optimizing.

---

# 15. Performance Profiling

Measure:

- Startup time
- Handler latency
- Queue delays
- CPU utilization
- Memory allocation

Profile representative workloads.

---

# 16. Failure Analysis

Capture:

- Exception type
- Stack trace
- Correlation ID
- Input context
- Environment information

Root-cause analysis should focus on reproducible evidence.

---

# 17. Static Analysis

Before runtime debugging, verify:

```bash
ruff check .
ruff format --check
mypy .
```

Static analysis often identifies issues before execution.

---

# 18. Automated Diagnostics

The DevKit should provide commands such as:

```bash
sh3dev diagnose
```

```bash
sh3dev health
```

```bash
sh3dev registry
```

```bash
sh3dev events
```

These commands should gather diagnostics without modifying application state.

---

# 19. Incident Documentation

Every significant issue should record:

- Summary
- Impact
- Timeline
- Root cause
- Resolution
- Preventive actions

Link relevant RFCs or ADRs when architectural changes are involved.

---

# 20. Review Checklist

During debugging, verify:

- Logs reviewed
- Correlation IDs traced
- Reproduction achieved
- Root cause confirmed
- Regression tests added
- Documentation updated

---

# 21. Anti-Patterns

Avoid:

- Debugging with production-only changes
- Ignoring logs
- Disabling validation
- Catching exceptions without recording context
- Guessing the cause without evidence
- Leaving temporary debug code in the codebase

---

# 22. Compliance Checklist

Debugging practices are compliant when:

- Diagnostic workflow is followed.
- Logs are structured.
- Correlation IDs are used.
- Root causes are documented.
- Regression tests accompany fixes.
- Temporary debugging artifacts are removed.

---

# 23. Final Definition

The SH-3 Debugging Guide defines a consistent, evidence-based approach to diagnosing, analyzing, and resolving issues across the SH-3 AI Operating Framework while preserving reliability, maintainability, and production readiness.

---

# End of Document
