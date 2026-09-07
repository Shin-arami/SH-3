# SH-3 DevKit Registry Layer Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Core Infrastructure Architecture


---

# 1. Purpose

This document defines the Registry Layer architecture of SH-3 DevKit.

The Registry Layer provides centralized discovery and management mechanisms for internal components.

Managed components include:

- Commands
- Services
- Generators
- Templates
- Plugins


---

# 2. Position


Registry Layer belongs to the Application Core Layer.



Service

↓

Registry

↓

Component Discovery

↓

Component Instance



The Registry Layer provides lookup capabilities only.


---

# 3. Design Principles


## Single Responsibility


Registry manages:

- Registration
- Lookup
- Discovery


Registry does not:

- Execute workflows
- Generate files
- Validate projects


---

## Explicit Registration


Components must be explicitly registered.


Example:


```python
registry.register(
    command
)

Automatic hidden discovery is prohibited by default.

Type Safety

All registered components must satisfy defined protocols.

Example:

GeneratorProtocol

CommandProtocol

ValidatorProtocol
4. Directory Structure
sh3dev/registry/

├── __init__.py
├── base.py
├── command_registry.py
├── template_registry.py
├── generator_registry.py
├── plugin_registry.py
└── loader.py
``` id="zzh0kh"


---

# 5. Registry Types


SH-3 DevKit provides:


## CommandRegistry


Manages user commands.


Example:



info

init

build

release

validate



---

## TemplateRegistry


Manages generation templates.


Example:



rfc-template

architecture-template

project-template



---

## GeneratorRegistry


Manages generators.


Example:



RFCGenerator

ProjectGenerator

ReleaseGenerator



---

## PluginRegistry


Manages external extensions.


Future support:



External Plugin

↓

PluginRegistry

↓

SH-3 DevKit



---

# 6. Registry Interface


Base protocol:


```python
class RegistryProtocol(Protocol):

    def register(
        self,
        name: str,
        component: object,
    ) -> None:
        ...


    def get(
        self,
        name: str,
    ) -> object | None:
        ...
7. Command Registry Example
registry.register(
    "build",
    BuildCommand(),
)

Lookup:

command = registry.get(
    "build"
)
8. Component Registration Flow

Standard flow:

Application Start

↓

Registry Creation

↓

Loader Execution

↓

Component Registration

↓

Runtime Ready
``` id="5x3yxg"


---

# 9. Registry Loader


Location:



registry/loader.py



Responsibility:


- Initialize registries
- Register built-in components
- Load extensions


Example:


```python
load_commands(
    command_registry
)
10. Circular Import Prevention

Registry architecture must prevent:

commands

↓

registry

↓

commands

Forbidden.

Required dependency direction:
Protocol

↓

Registry

↓

Loader

↓

Components

Components must never import loaders.

11. Import Rule Example

Correct:

commands/info.py

        ↓

protocols/command.py

Incorrect:

commands/info.py

        ↓

registry/loader.py
12. Dependency Injection

Registries are injected.

Example:

class Application:

    def __init__(
        self,
        registry: RegistryProtocol,
    ):
        self._registry = registry

Global registry instances are discouraged.

13. Thread Safety

Registry implementations must be thread safe.

Requirements:

Controlled mutation
Registration lock
Safe lookup

Example:

Register Phase

↓

Read Only Phase
14. Registry Lifecycle

Lifecycle:

Create

↓

Register

↓

Freeze

↓

Lookup

↓

Dispose

Production runtime should freeze registries after startup.

15. Registry Freeze

After initialization:

Registry State:

MUTABLE

        ↓

FROZEN

Frozen registry:

Allows lookup
Rejects modification
16. Error Handling

Registry errors:

Example:

raise RegistryError(
    "Duplicate command"
)

Handled cases:

Duplicate name
Missing component
Invalid component type
17. Testing Requirements

Required tests:

tests/registry/

├── test_command_registry.py
├── test_template_registry.py
├── test_generator_registry.py
└── test_plugin_registry.py

Test cases:

Register success
Duplicate registration
Lookup failure
Freeze behavior
18. Plugin Extension

Future plugin flow:

External Package

↓

Plugin Loader

↓

Plugin Registry

↓

Available Component

Plugins must implement official protocols.

19. Future Expansion

Registry Layer supports:

Plugin ecosystem
AI generated modules
Remote component discovery
Distributed development tools
End of Document

---

## 完成状態

現在:

```text
docs/devkit/

000-overview.md              ✅
001-directory-layout.md      ✅
002-layer-architecture.md    ✅
003-command-framework.md     ✅
004-service-layer.md         ✅
005-configuration-layer.md   ✅
006-generator-layer.md       ✅
007-registry-layer.md        ✅
