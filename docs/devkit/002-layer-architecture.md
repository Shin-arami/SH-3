# SH-3 DevKit Layer Architecture Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Development Infrastructure Architecture


---

# 1. Purpose

This document defines the layered architecture of SH-3 DevKit.

The architecture provides:

- Clear responsibility boundaries
- Replaceable components
- Controlled dependencies
- Long-term scalability


---

# 2. Architecture Model


SH-3 DevKit follows a layered architecture.



┌─────────────────────────────┐
│ CLI Layer │
├─────────────────────────────┤
│ Command Layer │
├─────────────────────────────┤
│ Service Layer │
├─────────────────────────────┤
│ Application Core Layer │
├─────────────────────────────┤
│ Infrastructure Layer │
├─────────────────────────────┤
│ External System Layer │
└─────────────────────────────┘



---

# 3. Layer Overview


## Layer 1: CLI Layer


Location:


cli.py



Responsibility:

- User interaction
- Argument parsing
- Application startup


Provides:


User Input

↓

Command Request



Must not contain:

- Business logic
- File operations
- Configuration rules


---

# Layer 2: Command Layer


Location:


commands/



Responsibility:

Convert user requests into application actions.


Example:



sh3dev release

↓

ReleaseCommand

↓

ReleaseService



Command contains:

- Name
- Description
- Metadata
- Arguments


Command does not contain:

- Generation logic
- Validation logic


---

# Layer 3: Service Layer


Location:


services/



Responsibility:

Application workflow orchestration.


Examples:



InitService

BuildService

ReleaseService

DoctorService

StatusService



Services coordinate:



Configuration

Registry

Generator

Validator

Filesystem



Service Layer is the center of application behavior.


---

# Layer 4: Application Core Layer


Contains:



config/

registry/

models/

protocols/

exceptions/



Responsibility:

Provide stable internal APIs.


---

## Configuration


Responsible for:

- Project information
- Runtime settings
- Environment data


Interface:


```python
ConfigLoader.load()
Registry

Responsible for:

Component discovery
Registration
Lookup

Examples:

CommandRegistry

TemplateRegistry

PluginRegistry
Models

Responsible for:

Typed data structures
Shared entities

Requirements:

Immutable where possible
Fully typed
Protocols

Responsible for abstraction.

Examples:

GeneratorProtocol

ValidatorProtocol

StorageProtocol

Purpose:

Allow component replacement.

Layer 5: Infrastructure Layer

Location:

filesystem/

utils/

monitoring/

Responsibility:

Provide technical capabilities.

Examples:

File Read

File Write

Path Handling

Logging

Metrics

Infrastructure must not know application rules.

Layer 6: External System Layer

Location:

integrations/

Responsibility:

Communicate with external systems.

Examples:

GitHub API

CI/CD

External Services

External systems must be isolated behind interfaces.

4. Dependency Direction

The only allowed dependency direction:

CLI

 ↓

Commands

 ↓

Services

 ↓

Core

 ↓

Infrastructure

 ↓

External
5. Dependency Restrictions

Forbidden:

Filesystem

    ↓

Command

Reason:

Infrastructure must remain reusable.

Forbidden:

Generator

    ↓

CLI

Reason:

Lower layers cannot depend on user interfaces.

6. Execution Flow

Standard execution:

User

↓

CLI Parser

↓

Command Resolution

↓

Service Execution

↓

Core Components

↓

Infrastructure

↓

Result
7. Replaceability Design

All major components must support replacement.

Example:

Default:

FileSystemWriter

Alternative:

CloudStorageWriter

Both implement:

StorageProtocol
8. Extension Points

Supported extension points:

Commands

New command:

commands/new_command.py

Register:

CommandRegistry
Generators

New generator:

generators/custom.py

Implement:

GeneratorProtocol
Validators

New validator:

validators/custom.py

Implement:

ValidatorProtocol
Plugins

Future:

plugins/

External modules may extend:

Commands
Generators
Validators
9. Thread Safety Requirements

Shared components must be thread safe.

Required:

Immutable configuration
Controlled state mutation
Explicit synchronization
10. Deterministic Execution

Same input must produce the same output.

Requirements:

No hidden global state
No random generation without seed
Explicit dependencies
11. Testing Requirements

Each layer requires testing.

Example:

CLI:

test_cli.py

Command:

test_commands.py

Service:

test_services.py

Infrastructure:

test_filesystem.py
12. Future Expansion

This architecture supports:

AI assisted development
Autonomous project management
Distributed build
Plugin ecosystem
Remote execution

End of Document
