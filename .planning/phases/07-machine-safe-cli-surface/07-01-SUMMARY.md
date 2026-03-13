---
phase: 07-machine-safe-cli-surface
plan: 01
subsystem: cli
tags: [typer, cli, json, automation, contract]
requires:
  - phase: 06-04
    provides: "shared query rendering plus list/status/chat command surfaces ready for machine-safe extraction"
provides:
  - "shared machine-safe JSON envelope helpers with a schema marker"
  - "stable usage, precondition, and unexpected failure exit-code primitives"
  - "structured payload seams for list, status, query, and one-shot chat"
affects: [machine-safe-cli-surface, cli, json, automation]
tech-stack:
  added: []
  patterns:
    - "Covered commands should build structured payloads before choosing human or machine rendering"
    - "Machine-safe failures should normalize through one shared exception and envelope layer"
key-files:
  created:
    - brainpack/machine_output.py
  modified:
    - brainpack/cli.py
    - tests/test_cli_json.py
key-decisions:
  - "The machine contract uses one top-level envelope with `ok`, `meta.schema`, and either `data` or `error`."
  - "Exit codes stay small and stable: 0 for success, 2 for usage, 3 for precondition failures, and 4 for unexpected errors."
patterns-established:
  - "Machine JSON emission should happen in one helper that writes exactly one stdout document."
  - "Missing-pack and readiness checks should be able to raise typed machine errors without changing human CLI prose."
requirements-completed: [AUT-01, AUT-02]
duration: 5min
completed: 2026-03-13
---

# Phase 07 Plan 01: Machine Contract Summary

**Shared machine-output primitives now define Brainpack's base JSON envelope, exit taxonomy, and reusable command payload seams for later `--json` rollout.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-13T13:46:00Z
- **Completed:** 2026-03-13T13:51:03Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added RED contract coverage for the shared envelope, schema marker, JSON emission, exit-code taxonomy, and unexpected-error normalization.
- Created `brainpack.machine_output` with reusable success/error builders, a typed `MachineExit`, centralized JSON emission, and a catch-all wrapper for machine-safe execution.
- Refactored `query`, one-shot `chat`, `list`, and `status` onto structured payload helpers so later plans can add `--json` without duplicating business logic.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED contract tests for the shared machine envelope** - `351a6e0` (test)
2. **Task 2: Implement shared machine-output helpers and CLI integration seam** - `da05b8e` (feat)

## Files Created/Modified
- `brainpack/machine_output.py` - Defines the shared machine-safe envelope, exit taxonomy helpers, JSON emission, and wrapper execution path.
- `brainpack/cli.py` - Adds machine-aware error hooks and reusable payload builders for list, status, query, and one-shot chat while preserving current human output.
- `tests/test_cli_json.py` - Locks the base machine contract with JSON-parsing assertions instead of prose matching.

## Decisions Made
- The schema marker ships from day one as `meta.schema = "brainpack.cli.v1"` so wrappers can pin the contract explicitly.
- Covered CLI surfaces now separate result construction from rendering, letting later plans add machine mode without inventing a second business-logic path.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `MachineExit` needed explicit `Exception.__init__` wiring during verification because dataclass slot initialization on an `Exception` subclass did not behave correctly with `super()`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 7 now has a stable contract foundation and command seams for the next rollout steps.
`07-02` can focus on explicit list/status serializers, and `07-03` can wire query/chat `--json` onto the shared machine helpers without reworking the base contract.

## Self-Check: PASSED

- Verified summary file exists on disk.
- Verified task commits `351a6e0` and `da05b8e` exist in git history.

