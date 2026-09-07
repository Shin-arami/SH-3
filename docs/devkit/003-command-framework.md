# SH-3 DevKit Command Framework Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Command Infrastructure Architecture


---

# 1. Purpose

This document defines the command framework architecture of SH-3 DevKit.

The command framework provides:

- User command execution
- Command discovery
- Command registration
- Command lifecycle management


The Command Layer is responsible for translating user requests into application workflows.


---

# 2. Command Architecture


The command execution flow:



User

↓

CLI Parser

↓

Command Resolver

↓

Command Registry

↓

Command Instance

↓

Service Layer

↓

Result



---

# 3. Command Responsibility


Commands are responsible for:

- Command metadata definition
- User argument handling
- Service invocation
- Result formatting request


Commands must not:

- Manage filesystem directly
- Parse configuration directly
- Generate files directly
- Contain business rules


---

# 4. Command Interface


All commands must implement the Command interface.


Example:


```python
class CommandProtocol(Protocol):

    metadata: CommandMetadata

    def execute(
        self,
        args: list[str],
    ) -> object:
        ...

Requirements:

Fully typed
Deterministic
Testable
5. Command Metadata

Each command requires metadata.

Model:

@dataclass(frozen=True, slots=True)
class CommandMetadata:

    name: str

    description: str

    category: str

Example:

CommandMetadata(
    name="release",
    description="Prepare SH-3 release",
    category="release",
)
6. Command Naming Rules

Command names must:

Use lowercase
Use hyphen separation if required
Be unique

Valid:

init

release

validate

architecture

Invalid:

Init

ReleaseCommand

build_project_command
7. Command Registry

Location:

sh3dev/registry/

Responsibility:

Store commands
Discover commands
Resolve commands

Interface:

class CommandRegistry:

    def register(
        self,
        command: CommandProtocol,
    ) -> None:
        ...


    def get(
        self,
        name: str,
    ) -> CommandProtocol | None:
        ...
8. Command Loading

Commands are loaded during application startup.

Flow:

Application Start

↓

Registry Creation

↓

Command Loading

↓

Command Registration

↓

CLI Ready
9. Command Dispatcher

Dispatcher executes commands.

Responsibility:

Command Name

↓

Command Lookup

↓

Execution

↓

Result Return

Example:

dispatcher.dispatch(
    "status"
)

Dispatcher must not know command implementation details.

10. Command Lifecycle

Standard lifecycle:

1. Receive Request

        ↓

2. Resolve Command

        ↓

3. Create Context

        ↓

4. Execute Command

        ↓

5. Return Result

        ↓

6. Format Output
11. Execution Context

Commands receive execution context when required.

Purpose:

Provide shared runtime information.

Example:

@dataclass(frozen=True)
class ExecutionContext:

    root: Path

    config: ProjectConfig

    verbose: bool

Context must be:

Immutable
Explicit
Serializable
12. Error Handling

Commands must use SH-3 DevKit exceptions.

Example:

raise SH3DevKitError(
    "Invalid project"
)

Rules:

No silent errors
No raw exception exposure
Explicit exit codes
13. Circular Import Prevention

Command modules must follow strict dependency rules.

Allowed:

commands

↓

services

↓

core

Forbidden:

commands

↓

registry

↓

commands

Command registration must happen through loader modules.

14. Command Package Structure

Recommended:

commands/

├── __init__.py

├── base.py

├── info.py

├── init.py

├── build.py

├── release.py

└── validate.py
15. Base Command

Optional shared base class:

class BaseCommand:

    metadata: CommandMetadata

    def execute(
        self,
        args: list[str],
    ) -> object:
        raise NotImplementedError

Base classes must remain minimal.

16. Testing Requirements

Each command requires:

Unit Test:

tests/commands/

Required tests:

test_command_metadata

test_execute_success

test_execute_failure

test_invalid_arguments
17. Extension Example

New command:

commands/analyze.py

Implementation:

AnalyzeCommand

↓

AnalyzeService

↓

Result

Registration:

CommandLoader

↓

CommandRegistry
18. Future Extensions

Command Framework supports:

Plugin commands
Remote commands
AI generated commands
Workflow commands
End of Document
