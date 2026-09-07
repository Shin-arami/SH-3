# SH-3 DevKit Plugin System Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Extension Architecture


---

# 1. Purpose

This document defines the Plugin System architecture of SH-3 DevKit.

The Plugin System provides a controlled extension mechanism without modifying the SH-3 DevKit core.

Plugins may extend:

- Commands
- Generators
- Validators
- Integrations
- Development tools


---

# 2. Design Goals


The Plugin System provides:


## Extensibility

External developers can add functionality.


## Isolation

Plugins must not modify core components directly.


## Compatibility

Plugins must declare supported DevKit versions.


## Replaceability

Plugin components follow official protocols.


---

# 3. Architecture Position


Plugin System belongs to the Registry Layer.



Plugin Package

↓

Plugin Loader

↓

Plugin Registry

↓

SH-3 DevKit Runtime



---

# 4. Plugin Principles


## Core Independence


The DevKit core must operate without plugins.


Required:



Core Installation

=

Working System



---

## Explicit Loading


Plugins are loaded through a controlled mechanism.


Forbidden:


- Hidden imports
- Runtime code injection
- Direct monkey patching


---

## Protocol Based Extension


Plugins extend official interfaces.


Examples:


``` id="x7n7ym"
CommandProtocol

GeneratorProtocol

ValidatorProtocol
5. Plugin Directory Structure

Recommended external plugin:

sh3dev_plugin_example/

├── pyproject.toml

├── sh3dev_plugin/

│   ├── __init__.py

│   ├── manifest.py

│   ├── commands/

│   ├── generators/

│   └── validators/
``` id="t1i0yr"


---

# 6. Plugin Manifest


Every plugin requires metadata.


Example:


```python
@dataclass(
    frozen=True,
    slots=True,
)
class PluginManifest:

    name: str

    version: str

    sh3devkit_version: str
7. Required Metadata

Plugin manifest contains:

Name

Unique plugin identifier.

Example:

sh3dev-rfc-tools
Version

Plugin version.

Format:

MAJOR.MINOR.PATCH
Compatibility

Supported SH-3 DevKit version.

Example:

>=1.0.0
8. Plugin Lifecycle

Lifecycle:

Discovery

↓

Validation

↓

Loading

↓

Registration

↓

Runtime

↓

Unload
``` id="w3lq7f"


---

# 9. Plugin Loader


Location:



registry/plugin_loader.py



Responsibilities:


- Discover plugins
- Validate manifests
- Register components


---

# 10. Plugin Registration


Example:


```python
plugin.register(
    registry
)

Registration may add:

Command

Generator

Validator

Integration
11. Plugin Interface

Plugin base:

class PluginProtocol(Protocol):

    manifest: PluginManifest


    def register(
        self,
        registry: RegistryProtocol,
    ) -> None:
        ...
12. Plugin Dependency Rules

Plugins may depend on:

SH-3 DevKit Public API

Plugins must not depend on:

Private Core Implementation
13. Version Compatibility

Compatibility check:

Plugin Version

+

DevKit Version

↓

Compatible / Rejected

Incompatible plugins must not load.

14. Security Rules

Plugins must:

Declare capabilities
Avoid unauthorized filesystem access
Use provided interfaces
15. Plugin Capabilities

Future manifest support:

capabilities:

- command

- generator

- validator

- github
16. Testing Requirements

Plugin tests:

tests/

└── plugin/

Required:

Manifest validation
Loading test
Registration test
Compatibility test
17. Example Plugin Flow

Example:

Developer

↓

Create Plugin

↓

Install Package

↓

Plugin Loader

↓

Registry

↓

New Command Available
18. AI Extension Support

Future SH-3 AI features may provide:

AI Plugin Generator

↓

PluginProtocol

↓

Registry

↓

DevKit Extension

AI plugins must follow the same validation rules.

19. Future Expansion

Plugin System supports:

Plugin marketplace
Organization plugins
Enterprise extensions
AI development agents
Remote tool providers
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
008-filesystem-layer.md      ✅
009-plugin-system.md         ✅
