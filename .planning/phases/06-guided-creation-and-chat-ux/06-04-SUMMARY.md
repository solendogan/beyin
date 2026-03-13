---
phase: 06-guided-creation-and-chat-ux
plan: 04
subsystem: cli
tags: [typer, cli, onboarding, chat, inventory]
requires:
  - phase: 06-01
    provides: "home-screen entry flow and inventory-oriented onboarding copy"
  - phase: 06-02
    provides: "guided create wizard and explicit build handoff"
  - phase: 06-03
    provides: "chat command and shared query rendering"
provides:
  - "chat redirects for missing, unbuilt, and blocked packs"
  - "shared next-step reasons for inventory-driven guidance"
  - "single-command create handoff wording"
affects: [guided-creation-and-chat-ux, cli, inventory, onboarding]
tech-stack:
  added: []
  patterns:
    - "Chat readiness should be checked before loading query runtime objects"
    - "Inventory lifecycle status should supply both the next command and the reason for it"
key-files:
  created: []
  modified:
    - brainpack/cli.py
    - brainpack/inventory.py
    - tests/test_cli.py
key-decisions:
  - "Chat now stops on missing, unbuilt, changed, and blocked pack states before loading model or collection objects."
  - "Inventory summaries expose reusable next-step reasons so home and chat guidance stay aligned."
patterns-established:
  - "User-facing dead-end states should end with exactly one explicit next command."
  - "Happy-path chat tests must mark fixtures as built when chat readiness gates are enforced."
requirements-completed: [ONB-01, ONB-02, QUX-01]
duration: 4min
completed: 2026-03-13
---

# Phase 06 Plan 04: Redirect and Handoff Summary

**Chat now redirects missing, unbuilt, and blocked packs to the right next command while create and home share clearer inventory-backed handoff reasons.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-13T02:00:33Z
- **Completed:** 2026-03-13T02:04:03Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added RED coverage for missing-pack, unbuilt-pack, and blocked-pack chat handoffs plus single-step create guidance.
- Stopped `brainpack chat` before runtime loading when the pack is missing or not ready, with redirects to `create`, `build`, or `doctor` as appropriate.
- Reused inventory lifecycle truth for next-step reasons so home and chat guidance explain why the suggested command is next.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED tests for redirects and handoffs** - `6d7046c` (test)
2. **Task 2: Implement redirects and next-step handoffs** - `5d74a8f` (feat)

## Files Created/Modified
- `brainpack/cli.py` - Adds chat readiness gating, missing-pack onboarding copy, a shared next-step renderer, and home/create handoff copy updates.
- `brainpack/inventory.py` - Adds reusable explanations for inventory-driven next actions.
- `tests/test_cli.py` - Covers missing/unbuilt/blocked chat redirects, single-step create output, and built fixtures for happy-path chat tests.

## Decisions Made
- Chat now treats pack readiness as a prerequisite and exits before model loading when the pack is missing, unbuilt, stale, failed, or blocked.
- The CLI now pairs `next_action` with a shared human-readable reason from inventory status so product copy stays consistent across surfaces.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 6 now has an explicit next-step handoff for home, create, and chat flows, with no remaining dead-end state in the covered paths.
This phase is complete and ready for milestone-level follow-up work.

## Self-Check: PASSED

- Verified summary file exists on disk.
- Verified task commits `6d7046c` and `5d74a8f` exist in git history.
