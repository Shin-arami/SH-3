# Part 11-25 — Persistent Application Runtime Integration & Recovery Verification

## Purpose

Add an application-layer composition root that places the typed cognition contract path in front of `SH3Kernel.learning_feedback_loop`. This is the coordinator path wired to persistent closed-loop evidence and replay claims.

The existing `AutonomyCore.run()` uses its older `LearningLoop` sequence. It must not be treated as evidence that the Part 11 replay-claim path has been exercised. The DevKit command dispatcher (`python -m sh3dev`) also remains a separate development-tool CLI.

## API

```python
from autonomy.persistent_runtime import create_persistent_application_runtime
from runtime.execution_engine import RuntimeExecutionEngine

runtime = create_persistent_application_runtime()
backend = runtime.kernel.cognition.execution_boundary.backend
if not isinstance(backend, RuntimeExecutionEngine):
    raise RuntimeError("unexpected cognition execution backend")
backend.register_operation("release.prepare", your_application_handler)

application_run = runtime.execute_contract(
    "prepare release",
    operation="release.prepare",
    payload={"release": "2.2"},
)
print(application_run.closed_loop_report.status)
```

`your_application_handler` is application-specific and must be a real, typed execution function. The framework intentionally does not invent a generic external side effect or placeholder operation. Register required operations before calling `execute_contract()`. If an operation is unregistered, the runtime returns a typed cognition failure result and the result is still passed through the closed-loop recovery/evidence path.

For a cognition result produced by another application-owned step, use `runtime.process_result(cognitive_result)` to pass it to the persistent closed-loop coordinator. The same exact `CognitiveResult` can be replayed after runtime reconstruction to recover a persisted terminal report.

## Configuration and fail-closed startup

The factory uses `SH3_PERSISTENT_REPLAY_DATABASE` unless `database_path` is supplied explicitly. Explicit paths take precedence. The default path requires an existing valid database; startup does not silently create a new empty database or fall back to in-memory stores.

```powershell
$env:SH3_PERSISTENT_REPLAY_DATABASE = 'C:\SH-3\data\evidence.sqlite3'
py -3.12 -m infrastructure.security.persistent_replay_ops check --database "$env:SH3_PERSISTENT_REPLAY_DATABASE"
```

The repository does not currently establish a single production application's `main()` or an actual production database path. This patch therefore adds a reusable application-level integration API, but does not add an executable that guesses which business operation should run. The owning application should call this API after it registers its own execution operations.

## Deliberate first-time provisioning

Provision only after confirming the path and parent directory, and confirming the target does not exist:

```powershell
$database = 'C:\SH-3\data\evidence.sqlite3'
if (Test-Path -LiteralPath $database) {
    throw "Refusing to provision an existing database: $database"
}
py -3.12 -c "from infrastructure.security.persistent_replay_runtime import create_persistent_replay_stores; print(create_persistent_replay_stores(r'$database', create_if_missing=True).database_path)"
py -3.12 -m infrastructure.security.persistent_replay_ops check --database $database
```

Normal runtime startup must omit `create_if_missing=True`. Provisioning does not create missing parent directories.

## Backup and recovery acceptance

Use the operational tooling against the exact configured database. Backup and restore destinations must not already exist:

```powershell
py -3.12 -m infrastructure.security.persistent_replay_ops backup `
  --database "$env:SH3_PERSISTENT_REPLAY_DATABASE" `
  --destination 'C:\SH-3\backups\evidence-before-change.sqlite3'

py -3.12 -m infrastructure.security.persistent_replay_ops check `
  --database 'C:\SH-3\backups\evidence-before-change.sqlite3'

py -3.12 -m infrastructure.security.persistent_replay_ops restore `
  --backup 'C:\SH-3\backups\evidence-before-change.sqlite3' `
  --destination 'C:\SH-3\recovery\evidence-restored.sqlite3'

py -3.12 -m infrastructure.security.persistent_replay_ops check `
  --database 'C:\SH-3\recovery\evidence-restored.sqlite3'
```

The new integration acceptance test uses disposable temporary SQLite files. It registers an explicit test-only execution operation, executes a typed closed loop, backs up and restores the DB to distinct paths, creates a fresh runtime against the restored DB, and replays the same `CognitiveResult`. It verifies terminal report identity/status and evidence/replay-claim counts.

This verifies the software recovery path; it does not claim a live host database has been identified or recovered. Preserve any real source database and backup until actual operational verification is complete. Do not switch production traffic to a restored path until schema integrity, evidence integrity, claim state, and counts have been reviewed.

## Acceptance checklist

1. Evidence and replay claims use the same canonical SQLite path.
2. Runtime startup fails closed if configuration is missing or DB does not exist/is invalid.
3. Application-owned execution operations are registered before contract execution.
4. A typed cognition result flows through `kernel.learning_feedback_loop.run()`.
5. Completed evidence/report/claim state survive DB backup, restore, and runtime reconstruction.
6. Existing `SH3Kernel()` and `sh3dev` CLI defaults remain unchanged.
7. Live DB identification and production recovery remain separate operational sign-offs.
