# SH-3 DevKit Filesystem Layer Specification

Version: 1.0.0

Status:
Architecture Baseline

Category:
Infrastructure Architecture


---

# 1. Purpose

This document defines the Filesystem Layer architecture of SH-3 DevKit.

The Filesystem Layer provides a unified abstraction for all file and directory operations.

The purpose is to isolate:

- Operating system operations
- Path management
- File access
- Directory handling


---

# 2. Position


Filesystem Layer is part of the Infrastructure Layer.



Service

↓

Generator

↓

Filesystem Interface

↓

Filesystem Implementation

↓

Operating System



---

# 3. Design Principles


## Abstraction First


Application components must not directly access the operating system filesystem.


Forbidden:


```python
open("file.txt")

Allowed:

filesystem.write()
Replaceability

Filesystem implementation must be replaceable.

Example:

LocalFilesystem

        |

FilesystemProtocol

        |

RemoteFilesystem
Safety

All filesystem operations must provide:

Validation
Error handling
Controlled overwrite
Atomic operations
4. Directory Structure
sh3dev/filesystem/

├── __init__.py
├── protocol.py
├── reader.py
├── writer.py
├── scanner.py
├── path.py
└── exceptions.py
``` id="rqlx2f"


---

# 5. Filesystem Protocol


All filesystem implementations follow:


```python
class FilesystemProtocol(Protocol):

    def read(
        self,
        path: Path,
    ) -> str:
        ...


    def write(
        self,
        path: Path,
        content: str,
    ) -> None:
        ...


    def exists(
        self,
        path: Path,
    ) -> bool:
        ...
6. File Reader

Location:

filesystem/reader.py

Responsibilities:

Read text files
Encoding handling
Error conversion

Example:

content = reader.read(
    path
)
7. File Writer

Location:

filesystem/writer.py

Responsibilities:

Create files
Update files
Safe writing
8. Atomic Write

File writes must support atomic behavior.

Standard flow:

Create Temporary File

↓

Write Content

↓

Validate

↓

Replace Original

Purpose:

Prevent corrupted files
Protect generated artifacts
9. Overwrite Policy

All writes require explicit policy.

Example:

WriteMode.CREATE

WriteMode.OVERWRITE

WriteMode.FAIL

Default:

FAIL

Silent overwrite is prohibited.

10. Path Management

Location:

filesystem/path.py

Responsibilities:

Normalize paths
Resolve project root
Validate paths

Example:

root / "docs" / "rfc"
11. Path Safety Rules

The following are prohibited:

Outside Root Access

Example:

../../system/file
Invalid Path

Example:

Null path
Empty path
Unsupported location
12. Directory Operations

Supported:

create_directory()

remove_directory()

list_directory()

scan()

All operations return explicit results.

13. Scanner

Location:

filesystem/scanner.py

Responsibilities:

Discover files
Analyze project structure
Support validators

Example:

scanner.scan(
    project_root
)
14. Integration With Generator Layer

Generator flow:

Generator

↓

Filesystem Writer

↓

Artifact Created

Generator does not know:

OS
Path implementation
Storage location
15. Integration With Validator Layer

Validator flow:

Validator

↓

Filesystem Scanner

↓

Validation Result
16. Error Handling

Filesystem errors use dedicated exceptions.

Example:

raise FileSystemError(
    "Cannot write file"
)

Handled cases:

Permission denied
File missing
Invalid path
Write failure
17. Thread Safety

Filesystem operations must consider concurrency.

Requirements:

Atomic writes
Controlled locking
No shared mutable buffers
18. Testing Requirements

Required tests:

tests/filesystem/

├── test_reader.py
├── test_writer.py
├── test_scanner.py
└── test_path.py

Test cases:

Read success
Write success
Atomic replacement
Invalid path
Permission failure
19. Future Expansion

Filesystem Layer supports:

Cloud Storage
Remote Repository
Virtual Filesystem
Distributed Build Storage

Through:

FilesystemProtocol
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
