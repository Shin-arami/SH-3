# SH-3 DevKit Service Layer Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Application Architecture


---

# 1. Purpose

This document defines the Service Layer architecture of SH-3 DevKit.

The Service Layer is the central execution layer responsible for application workflows.

The purpose of this layer is to separate:

- User interaction
- Command handling
- Business workflow
- Infrastructure operations


---

# 2. Service Layer Position


The Service Layer exists between Commands and Core Infrastructure.



CLI

↓

Command

↓

Service

↓

Core Components

↓

Infrastructure



The Service Layer coordinates application behavior.


---

# 3. Responsibilities


Service Layer responsibilities:


## Workflow Execution

Services execute complete application workflows.


Example:



InitCommand

↓

InitService

↓

ProjectInitializer

↓

Filesystem



---

## Component Coordination

Services coordinate:


- Configuration
- Registry
- Generators
- Validators
- Filesystem
- External integrations


---

## Business Rules

Application rules belong to Services.


Examples:


- Build sequence
- Release preparation flow
- Validation order
- Initialization process


---

# 4. Non Responsibilities


Services must not:


- Parse CLI arguments
- Print user interface messages
- Directly handle terminal formatting
- Replace infrastructure components


---

# 5. Service Interface


All services should follow a common pattern.


Example:


```python
class ServiceProtocol(Protocol):

    def execute(
        self,
        request: object,
    ) -> object:
        ...

Requirements:

Fully typed
Deterministic
Testable
6. Service Naming Rules

Services use the suffix:

<ServiceName>Service

Examples:

InitService

BuildService

ReleaseService

StatusService

DoctorService

Invalid:

InitManager

BuildHandler

ReleaseWorker
7. Service Structure

Recommended:

services/

├── init_service.py

├── build_service.py

├── release_service.py

├── status_service.py

└── doctor_service.py
8. Execution Context

Services receive explicit dependencies.

Example:

@dataclass(frozen=True)
class ServiceContext:

    config: ProjectConfig

    registry: Registry

    filesystem: FileSystem

Services must avoid:

Global variables
Hidden state
Singleton dependency
9. Dependency Injection

Dependencies must be injected.

Example:

class BuildService:

    def __init__(
        self,
        validator: ValidatorProtocol,
        generator: GeneratorProtocol,
    ):
        self._validator = validator
        self._generator = generator

Benefits:

Replaceability
Testing
Isolation
10. Workflow Design

A Service workflow follows:

Receive Request

↓

Validate Input

↓

Load Configuration

↓

Execute Operation

↓

Generate Result

↓

Return Response
11. Result Model

Services should return typed results.

Example:

@dataclass(frozen=True)
class ServiceResult:

    success: bool

    message: str

    data: object

No uncontrolled dictionaries should be exposed internally.

12. Error Handling

Services use SH-3 DevKit exceptions.

Example:

raise SH3DevKitError(
    "Build failed"
)

Rules:

Explicit failures
Controlled exceptions
Predictable exit behavior
13. Existing Service Mapping

Current commands map as follows:

Command	Service
init	InitService
build	BuildService
release	ReleaseService
status	StatusService
doctor	DoctorService
validate	ValidateService
template	TemplateService
rfc	RFCService
14. Service Lifecycle

Standard lifecycle:

Create

↓

Inject Dependencies

↓

Execute

↓

Collect Result

↓

Dispose Resources

Services should not keep long-lived mutable state.

15. Thread Safety

Services must be thread safe.

Requirements:

Immutable configuration
Local execution state
Controlled resource access
16. Testing Requirements

Each Service requires:

Unit tests:

tests/services/

Required cases:

test_success

test_invalid_input

test_dependency_failure

test_exception_handling
17. Service Layer Extension

New capability example:

AnalyzeCommand

↓

AnalyzeService

↓

Analyzer

↓

Result

The Service becomes the stable entry point.

18. Future Expansion

Service Layer enables:

REST API
Web UI
Automation Agent
AI Developer Assistant
Remote Execution
End of Document
