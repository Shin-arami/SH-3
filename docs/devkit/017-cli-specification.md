# SH-3 DevKit CLI Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
User Interface Architecture


---

# 1. Purpose

This document defines the command line interface architecture of SH-3 DevKit.

The CLI provides:

- User interaction
- Command execution entry point
- Automation interface
- Development workflow access


---

# 2. CLI Philosophy


SH-3 DevKit CLI follows:



Simple Interface

Predictable Behavior

Machine Friendly Output



The CLI is an interface layer only.


---

# 3. CLI Position


CLI belongs to the Presentation Layer.



User

↓

CLI

↓

Command Layer

↓

Service Layer

↓

Infrastructure



CLI must not contain business logic.


---

# 4. Entry Points


SH-3 DevKit supports:


## Installed Command


```bash
sh3dev
Python Module
python -m sh3dev

Both must provide identical behavior.

5. CLI Structure

Directory:

sh3dev/

├── cli.py

├── __main__.py

├── commands/

└── parser/
6. Main Entry

Entry function:

def main() -> int:
    ...

Requirements:

Return exit code
Handle CLI exceptions
Initialize runtime
7. Command Architecture

Command flow:

Input

↓

Parser

↓

Command Resolver

↓

Command Execution

↓

Result

↓

Output
8. Command Protocol

Commands implement:

class CommandProtocol(Protocol):

    name: str

    description: str


    def execute(
        self,
        args: object,
    ) -> CommandResult:
        ...
9. Built-in Commands

SH-3 DevKit v1.0 provides:

info

version

list

init

create

rfc

validate

build

template
10. Command Responsibilities

Commands may:

Receive arguments
Call services
Return results

Commands must not:

Access filesystem directly
Parse configuration directly
Implement generation logic
11. Argument Parsing

CLI parser responsibilities:

Parse arguments
Validate syntax
Display help

Example:

sh3dev init MyProject

Parsed:

{
    "command": "init",
    "name": "MyProject"
}
12. Help System

Required:

sh3dev --help

Command help:

sh3dev init --help

Output must include:

Description
Arguments
Options
Examples
13. Output Format

CLI supports:

Human Output

Default:

Project created successfully
Machine Output

Future:

sh3dev init Test --json

Example:

{
  "status": "success",
  "project": "Test"
}
14. Exit Code Specification

Standard codes:

0

Success
1

General Error
2

Invalid Arguments
3

Configuration Error
4

Validation Error
5

Generation Error
15. Error Handling

CLI catches application errors.

Example:

Command

↓

Service Error

↓

CLI Error Handler

↓

User Message

Internal stack traces are hidden by default.

16. Logging Mode

CLI supports:

Normal:

sh3dev build

Verbose:

sh3dev build --verbose

Debug:

sh3dev build --debug
17. Configuration Options

Global options:

--version

--help

--verbose

--debug

--config
18. Automation Support

CLI must support:

CI execution
Script usage
Agent control

Requirements:

Stable exit codes
Predictable output
No interactive dependency
19. Command Registration

Commands are loaded through:

CommandRegistry

↓

CommandLoader

↓

CLI Dispatcher
20. Circular Import Prevention

CLI architecture must avoid:

CLI

↓

Commands

↓

Registry

↓

Commands

Correct:

CLI

↓

Registry Interface

↓

Command Loader

↓

Commands
21. Testing Requirements

CLI tests:

tests/cli/

├── test_parser.py

├── test_commands.py

└── test_execution.py

Required:

Command discovery
Argument parsing
Exit codes
Error handling
22. AI Agent Support

Future:

AI Agent

↓

CLI/API Interface

↓

SH-3 Runtime

CLI must remain deterministic for automation.

23. Production CLI Criteria

CLI is production ready when:

Commands Stable

+

Errors Controlled

+

Tests PASS

+

Documentation Complete
End of Document

---

## 完成状態

```text
docs/devkit/

000-overview.md                ✅
001-directory-layout.md        ✅
002-layer-architecture.md      ✅
003-command-framework.md       ✅
004-service-layer.md           ✅
005-configuration-layer.md     ✅
006-generator-layer.md         ✅
007-registry-layer.md          ✅
008-filesystem-layer.md        ✅
009-plugin-system.md           ✅
010-testing-strategy.md        ✅
011-packaging.md               ✅
012-release-process.md         ✅
013-development-workflow.md    ✅
014-security-model.md          ✅
015-performance-guidelines.md  ✅
016-api-design.md              ✅
017-cli-specification.md       ✅
