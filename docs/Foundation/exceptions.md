# SH-3 Foundation Exceptions

## Purpose

This document defines the typed exception contract for SH-3 Foundation.

Exceptions represent failures that cannot be handled as ordinary successful control flow.

## Principles

- Exceptions are typed.
- The hierarchy reflects semantic failure categories.
- Exceptions preserve causal information.
- Exceptions contain no hidden mutable global state.
- Messages are deterministic where practical.

## Root Exception

SH-3 should provide a common Foundation exception root for framework-specific failures.

```text
SH3Error
    ├── ConfigurationError
    ├── ValidationError
    ├── StateError
    ├── DependencyError
    ├── ExecutionError
    ├── SerializationError
    └── SecurityError
```

The hierarchy may be extended by higher layers without changing Foundation semantics.

## Exception Chaining

Underlying causes should be preserved using exception chaining where appropriate.

## Determinism

Exception classification must depend on the actual failure condition rather than incidental message text.

## Thread Safety

Foundation exceptions must not contain shared mutable state.

## Public Error Contract

Public APIs expose stable exception classes. Consumers must not parse message strings to determine failure type.

## Logging and Sensitive Information

Exceptions must provide sufficient structured context without exposing credentials, tokens, secrets, private keys, or uncontrolled personal data.

## Anti-Patterns

- Catching every exception and silently continuing
- Using strings as exception types
- Exposing secrets in messages
- Using exceptions as global state
- Circular dependencies through exception modules
- Relying on implementation-specific traceback text

## Completion Criteria

Foundation Exceptions are complete when failure classes are explicit, semantically organized, safe to expose, deterministic in classification, and independently testable.

---

# End of Document
