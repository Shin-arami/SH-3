# SH-3 Style Guide

Version:
1.0.0

Status:
Developer Guide

Category:
Style Guide

---

# 1. Purpose

This document defines the writing and presentation standards used throughout the SH-3 project.

Its objectives are:

- Ensure consistency
- Improve readability
- Reduce ambiguity
- Standardize communication
- Simplify maintenance

This guide applies to source code, documentation, RFCs, ADRs, API descriptions, CLI output, logs, and related project artifacts.

---

# 2. Style Principles

All project content should be:

- Clear
- Consistent
- Concise
- Explicit
- Professional

Prefer simple and precise language over complex wording.

---

# 3. Language

Project documentation should use:

- English for official specifications
- UTF-8 encoding
- LF line endings

Use consistent terminology throughout the project.

---

# 4. Terminology

Use one canonical name for each concept.

Examples:

- Event Bus
- Component Registry
- Runtime Context
- Dependency Injection
- Plugin Manifest

Avoid using multiple names for the same concept.

---

# 5. Naming

Use descriptive names.

Prefer:

```
ConfigurationLoader
```

Instead of:

```
Loader
```

Names should communicate responsibility.

---

# 6. Headings

Use hierarchical headings.

Example:

```text
# Title

## Section

### Subsection
```

Avoid skipping heading levels.

---

# 7. Lists

Use unordered lists for collections.

Use numbered lists for ordered procedures.

Keep list items concise and grammatically consistent.

---

# 8. Tables

Use tables when comparing structured information.

Prefer lists for short enumerations.

Tables should remain readable in plain Markdown.

---

# 9. Code Blocks

Specify the language.

Example:

```text
```python
class Planner:
    ...
```
Code examples should compile or accurately reflect intended syntax.

---

# 10. Examples
```
Examples should:

Be minimal
Be correct
Demonstrate one concept
Avoid unnecessary complexity
```
Prefer realistic names over placeholders when practical.

---

# 11. Documentation Style

Documentation should explain:
```
What
Why
How
```
Complex design decisions should include rationale.

---

# 12. RFC Style

RFCs should include:
```
Purpose
Motivation
Design
Alternatives
Compatibility
References
```
RFC language should be objective and technical.

---

# 13. ADR Style

ADRs should include:
```
Context
Decision
Consequences
Alternatives
```
Record decisions rather than implementation details.

---

# 14. API Documentation

Public APIs should document:
```
Parameters
Return values
Exceptions
Usage notes
Version compatibility
```
Examples are recommended for non-trivial APIs.

---

# 15. CLI Output

CLI messages should be:
```
Short
Actionable
Consistent
```
Example:
```
Validation completed successfully.
```
Error messages should suggest a next step where possible.

---

# 16. Logging Style

Log messages should:
```
Describe what happened
Include relevant identifiers
Avoid unnecessary punctuation
Exclude sensitive information
```
Example:
```
Plugin "storage" registered successfully.
```
---

# 17. Error Messages

Error messages should:
```
State the problem
Identify the affected object
Suggest corrective action when appropriate
```
Avoid vague messages such as:
```
Something went wrong.
```
---

# 18. Formatting

Formatting conventions:
```
UTF-8
LF
Four-space indentation (code)
Consistent spacing
```
Automated formatting tools should be preferred.

---

# 19. Cross References

Reference related documents when appropriate.

Examples:
```
Architecture Specification
Developer Guide
RFC
ADR
```
Cross references should remain valid across versions.

---

# 20. Review Checklist

Verify:
```
Terminology consistency
Grammar
Formatting
Heading structure
Example correctness
Cross-reference accuracy
```
---

# 21. Anti-Patterns

Avoid:
```
Inconsistent terminology
Ambiguous wording
Excessive abbreviations
Broken references
Outdated examples
Inconsistent formatting
```
---

# 22. Compliance Checklist

Project artifacts are compliant when:
```
Terminology is consistent.
Formatting follows the guide.
Examples are accurate.
Cross references are maintained.
Automated formatting passes where applicable.
```
---

# 23. Final Definition

The SH-3 Style Guide establishes a unified writing and presentation standard that ensures every artifact within the SH-3 ecosystem is consistent, readable, maintainable, and professionally presented.

---

# End of Document
