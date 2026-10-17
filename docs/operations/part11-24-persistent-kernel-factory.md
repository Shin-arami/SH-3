# Part 11-24 — Persistent Kernel Factory

## Purpose

Provide an explicit construction path for an `SH3Kernel` that uses SQLite-backed
closed-loop evidence and replay claims. This is a Kernel construction API, not a
change to the `sh3dev` development-tool CLI or to the default `SH3Kernel()` path.

## API

```python
from kernel import create_persistent_sh3_kernel

runtime = create_persistent_sh3_kernel()
kernel = runtime.kernel
print(runtime.database_path)
```

The default database path is resolved from `SH3_PERSISTENT_REPLAY_DATABASE`.
Alternatively, pass a path explicitly:

```python
runtime = create_persistent_sh3_kernel(
    r"C:\SQLite\sh3-persistent-replay.sqlite3",
)
```

The path above is an example configuration, not a database created by this patch.
The directory must already exist, and the database must already be provisioned.

## First-time provisioning

The factory fails closed when the configured database is absent. For deliberate
first-time initialization only, use the explicit opt-in:

```python
runtime = create_persistent_sh3_kernel(
    r"C:\SQLite\sh3-persistent-replay.sqlite3",
    create_if_missing=True,
)
```

Do not use `create_if_missing=True` as a normal startup fallback. A misspelled
path must not silently create an empty database and conceal existing evidence.
Back up and verify any existing database before changing its configured path.

## Configuration precedence

1. An explicit `database_path` argument takes precedence.
2. Otherwise `SH3_PERSISTENT_REPLAY_DATABASE` is required.
3. `:memory:` and directory paths are rejected for persistent replay.
4. Existing databases are checked before store adapters are opened.
5. Evidence and replay-claim stores must point to the same SQLite database.

PowerShell configuration for a future application process:

```powershell
$env:SH3_PERSISTENT_REPLAY_DATABASE = 'C:\SQLite\sh3-persistent-replay.sqlite3'
```

Setting the environment variable alone does not create a database or automatically
wire it into arbitrary `SH3Kernel()` instances. The application entry point must
call `create_persistent_sh3_kernel()` and use `runtime.kernel`.

## Validation boundary

This part adds the explicit Kernel factory and its construction tests. It does not
claim that a production application entry point already invokes the factory. The
current `sh3dev` CLI is a DevKit command dispatcher; it is not wired to start the
SH-3 Kernel. A later integration should connect the factory to the actual runtime
entry point once that entry point and its lifecycle contract are defined.

Operational integrity checks, backup, and restore remain available through
`infrastructure.security.persistent_replay_ops`. Perform those procedures against
the configured database only after its actual path and ownership are established.
