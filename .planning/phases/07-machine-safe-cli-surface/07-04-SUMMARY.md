---
phase: 07-machine-safe-cli-surface
plan: 04
subsystem: cli
tags: [typer, cli, json, query, chat, regression]
requires:
  - phase: 07-02
    provides: "machine-safe inventory payloads for list/status"
  - phase: 07-03
    provides: "machine-safe retrieval payloads for query/chat"
provides:
  - "final regression coverage for stdout purity, schema stability, and exit-code behavior across covered machine commands"
  - "query readiness gating aligned with chat for unbuilt, stale, and failed packs"
  - "human-mode guardrails that keep list/status/query/chat text-first when `--json` is absent"
affects: [machine-safe-cli-surface, cli, json, query, chat, testing]
tech-stack:
  added: []
  patterns:
    - "Covered machine commands must emit exactly one parseable JSON document with stable top-level keys."
    - "Retrieval commands should fail on pack lifecycle preconditions before model or collection loading."
key-files:
  created:
    - .planning/phases/07-machine-safe-cli-surface/07-04-SUMMARY.md
  modified:
    - brainpack/cli.py
    - tests/test_cli.py
    - tests/test_cli_json.py
key-decisions:
  - "Query now enforces the same build/readiness gates as chat, but preserves the existing provider-blocked machine error contract."
  - "The final contract suite pins both JSON stdout purity and ready-pack human UX so future wrappers can trust the surface."
patterns-established:
  - "Happy-path query fixtures must be marked built once retrieval readiness gates are enforced."
  - "Machine regression helpers should assert one-document stdout and exact top-level keys instead of only parsing payload contents."
requirements-completed: [AUT-01, AUT-02]
duration: 14min
completed: 2026-03-13
---

# Phase 07 Plan 04: Contract Hardening Summary

**The machine-safe CLI surface now has final regression coverage for stdout purity and exit codes, and `query` matches `chat` on pack-readiness preconditions.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-03-13T14:10:23Z
- **Completed:** 2026-03-13T14:24:23Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added final regression coverage for one-document JSON stdout, stable top-level success/error keys, and unbuilt-pack query failures.
- Preserved human `list`, `status`, `query`, and `chat` expectations with ready-pack fixtures and explicit unbuilt-pack query guidance.
- Aligned `query` with `chat` so new, stale, and failed packs stop before runtime loading while machine provider errors keep their existing contract.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add final regression coverage for stdout purity and exit-code stability** - `1631f92` (test)
2. **Task 2: Clean up any remaining contract leaks and run full verification** - `0cf3157` (fix)

## Files Created/Modified
- `brainpack/cli.py` - Gates query on pack lifecycle readiness and reuses one retrieval precondition helper for human and machine flows.
- `tests/test_cli.py` - Adds unbuilt-query human guardrails and marks happy-path query fixtures as built.
- `tests/test_cli_json.py` - Pins single-document stdout, stable envelope keys, and unbuilt-query machine failures.
- `.planning/STATE.md` - Records completion of `07-04` and Phase 7.
- `.planning/ROADMAP.md` - Marks Phase 7 complete.

## Decisions Made

- Query now stops on `new`, `needs-build`, and `error` pack states before loading model or collection objects, matching the existing chat safety model.
- Provider-blocked query failures still use the `runtime_blocked` machine error envelope from `07-03`; the hardening pass only added the missing lifecycle gates.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The new query readiness gate invalidated earlier happy-path tests that were querying unbuilt fixtures; those tests were corrected to mark ready packs explicitly.
- The initial RED pass surfaced that the plan's keyword-based quick verification would not hit the new unbuilt-query JSON regression directly, so targeted checks were run before the planned verification commands.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 7 now closes with contract tests across all covered machine commands and matching retrieval preconditions for both query and chat.
The roadmap is fully executed through Phase 7 and ready for milestone-level wrap-up or next-phase planning.

## Self-Check: PASSED

- Verified `.planning/phases/07-machine-safe-cli-surface/07-04-SUMMARY.md` exists on disk.
- Verified task commits `1631f92` and `0cf3157` exist in git history.
