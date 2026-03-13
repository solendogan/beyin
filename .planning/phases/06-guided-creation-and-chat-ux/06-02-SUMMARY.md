---
phase: 06-guided-creation-and-chat-ux
plan: 02
subsystem: cli
tags: [typer, yaml, onboarding, wizard]
requires:
  - phase: 06-01
    provides: no-argument entry screen and onboarding copy patterns
provides:
  - guided `brainpack create` wizard
  - canonical `pack.yaml` writer for managed packs
  - CLI coverage for guided creation flow
affects: [chat-ux, onboarding, pack-management]
tech-stack:
  added: []
  patterns: [source-family-first CLI wizard, shared config serialization]
key-files:
  created: [.planning/phases/06-guided-creation-and-chat-ux/06-02-SUMMARY.md]
  modified: [brainpack/cli.py, brainpack/config.py, tests/test_cli.py]
key-decisions:
  - "Guided creation defaults new packs to `llm: ollama` and writes the full canonical schema explicitly."
  - "The first-pass wizard accepts exactly one source URL and one source family per run to keep onboarding narrow."
patterns-established:
  - "Wizard prompts should ask the highest-level routing question first, then gather only the minimum required fields."
  - "Managed pack creation writes canonical YAML through shared config serialization instead of ad hoc string building."
requirements-completed: [ONB-02]
duration: 3min
completed: 2026-03-13
---

# Phase 6 Plan 02: Guided Pack Creation Summary

**Source-family-first `brainpack create` wizard that writes canonical pack.yaml and hands users directly to `brainpack build`**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-13T01:38:55Z
- **Completed:** 2026-03-13T01:42:38Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added RED coverage for guided creation prompt order, canonical YAML output, and post-create guidance.
- Implemented `brainpack create` as a narrow interactive wizard that asks source type first and writes one-source-family pack configs.
- Added shared config serialization so managed pack creation emits the same canonical schema the rest of the app already loads.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED tests for guided creation** - `c87b154` (test)
2. **Task 2: Implement question-based pack creation** - `bb3a571` (feat)

## Files Created/Modified
- `tests/test_cli.py` - Adds create wizard RED tests for prompt order, canonical YAML, and build guidance.
- `brainpack/cli.py` - Adds the `create` command and its source-family-first wizard flow.
- `brainpack/config.py` - Adds canonical config serialization and file writing helpers.

## Decisions Made
- Defaulted the guided flow to `llm: ollama` so the first-run path stays narrow and compatible with existing defaults.
- Wrote canonical `sources` entries as explicit `{"url": ...}` mappings to keep managed pack output stable.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Guided pack creation is now available and tested. Phase 06-03 can build on this onboarding flow to add the user-facing `chat` surface.

## Self-Check

PASSED

---
*Phase: 06-guided-creation-and-chat-ux*
*Completed: 2026-03-13*
