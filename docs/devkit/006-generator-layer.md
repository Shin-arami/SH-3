# SH-3 DevKit Generator Layer Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Generation Infrastructure Architecture


---

# 1. Purpose

This document defines the Generator Layer architecture of SH-3 DevKit.

The Generator Layer provides controlled and deterministic generation capabilities.

The Generator Layer is responsible for creating:

- Source files
- Documentation files
- Configuration files
- Project structures
- Development artifacts


---

# 2. Position


Generator Layer belongs to the application execution infrastructure.



Service

↓

Generator

↓

Template

↓

Filesystem

↓

Generated Artifact



---

# 3. Design Principles


## Deterministic Generation


Same input must always produce the same output.


Example:



Same ProjectConfig

Same Template

↓

Same Generated Files



---

## Stateless Design


Generators must not maintain execution state.


Forbidden:


```python
self.generated_files

Allowed:

generate(request)
Replaceable Design

Generators must implement common interfaces.

Example:

LocalGenerator

        |

GeneratorProtocol

        |

RemoteGenerator
4. Directory Structure
sh3dev/generators/

├── __init__.py
├── base.py
├── project.py
├── architecture.py
├── rfc.py
├── template.py
└── release.py
``` id="z9q5hk"


---

# 5. Generator Protocol


All generators follow:


```python
class GeneratorProtocol(Protocol):

    def generate(
        self,
        request: object,
    ) -> GenerationResult:
        ...

Requirements:

Fully typed
Stateless
Testable
6. Generation Result

Generators return typed results.

Example:

@dataclass(
    frozen=True,
    slots=True,
)
class GenerationResult:

    success: bool

    files: tuple[Path, ...]

    message: str
7. Generator Responsibilities

Generators may:

Load templates
Render templates
Create files
Return generation results

Generators must not:

Parse CLI arguments
Manage workflows
Decide business rules
8. Generator Types
Project Generator

Purpose:

Create new SH-3 projects.

Example:

sh3dev init MyProject

Produces:

foundation/

runtime/

services/

kernel/

docs/

tests/
RFC Generator

Purpose:

Generate RFC documents.

Example:

rfc-0001-foundation.md
Architecture Generator

Purpose:

Generate architecture documentation.

Example:

architecture.md
Template Generator

Purpose:

Manage reusable templates.

Operations:

Create
Copy
Render
Validate
Release Generator

Purpose:

Generate release artifacts.

Examples:

CHANGELOG
Release Notes
Metadata
9. Template Integration

Generator flow:

Request

↓

Template Resolver

↓

Template Loading

↓

Rendering

↓

Filesystem Writer

↓

Result
``` id="bd21um"


---

# 10. Template Rules


Templates must:


- Be version controlled
- Have explicit format
- Be deterministic


Example:



templates/

├── rfc/

├── project/

├── github/

└── release/



---

# 11. Filesystem Dependency


Generators never directly manipulate files.


Forbidden:


```python
open("file.txt")

Allowed:

filesystem.write()

Reason:

Filesystem must remain replaceable.

12. Dependency Injection

Generators receive dependencies explicitly.

Example:

class RFCGenerator:

    def __init__(
        self,
        renderer: TemplateRenderer,
        writer: FileWriter,
    ):
        ...
13. Generator Lifecycle

Standard lifecycle:

Create Generator

↓

Receive Request

↓

Resolve Template

↓

Render Content

↓

Write Files

↓

Return Result
14. Error Handling

Generation failures use explicit exceptions.

Example:

raise GenerationError(
    "Template not found"
)

Required:

Clear message
Failed resource information
No silent recovery
15. Testing Requirements

Required tests:

tests/generators/

├── test_project.py
├── test_rfc.py
├── test_template.py
└── test_release.py

Test cases:

Valid generation
Invalid template
Missing directory
Permission failure
Output verification
16. AI Extension Point

Future SH-3 AI integration may provide:

AI Generator

        |

GeneratorProtocol

        |

Standard Generation Flow

AI generation must still satisfy:

Deterministic mode
Validation
Testability
17. Future Extension

Generator Layer supports:

Custom generators
Plugin generators
AI-assisted generation
Remote artifact generation
End of Document
