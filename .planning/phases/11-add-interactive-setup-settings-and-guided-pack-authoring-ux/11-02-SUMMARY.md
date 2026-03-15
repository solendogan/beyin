---
phase: 11-add-interactive-setup-settings-and-guided-pack-authoring-ux
plan: 02
subsystem: ui
tags: [cli, interactive, settings, inquirerpy, onboarding]
requires:
  - phase: 11-01
    provides: global settings storage and the TTY-only interactive seam
provides:
  - one-time first-run setup for interactive no-arg CLI sessions
  - explicit `brainpack settings` editing flow with staged confirmation
  - preference-aware human guidance that leaves machine-safe JSON surfaces unchanged
affects: [phase-11-plan-03, onboarding, guided-authoring, machine-safe-cli]
tech-stack:
  added: []
  patterns:
    - staged interactive answers are persisted only after explicit confirmation
    - saved preferred mode changes human guidance ordering without mutating machine contracts
key-files:
  created: []
  modified:
    - brainpack/cli.py
    - brainpack/interactive.py
    - brainpack/settings.py
    - tests/test_cli.py
    - tests/test_cli_json.py
    - tests/test_settings.py
key-decisions:
  - "Initial setup uses the no-arg interactive path exactly once, then defers later edits to `brainpack settings`."
  - "Setup and settings both end with one applied summary block and one next step: `brainpack create`."
  - "Saved mode preference only reorders human guidance; JSON and MCP paths keep their existing payload contracts."
patterns-established:
  - "Interactive flow pattern: collect answers in memory, confirm once, then persist via the shared atomic settings writer."
  - "Guidance pattern: use saved global preference for prose ordering only, never as readiness truth for machine-safe output."
requirements-completed: [ONB-01, PCK-05, RUN-01, AUT-01, AUT-02]
duration: 5min
completed: 2026-03-15
---

# Phase 11 Plan 02: First-Run Setup and Settings Summary

**One-time interactive setup, explicit global settings editing, and preference-aware home/status guidance on top of the Phase 11 TTY seam**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-15T04:23:19+03:00
- **Completed:** 2026-03-15T04:28:18+03:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added RED coverage for one-time setup, editable settings, cancellation safety, machine-valid choice derivation, and JSON regressions.
- Implemented the interactive setup/settings flow with staged confirmation, atomic persistence, and one consistent applied-summary handoff.
- Reused saved preferred mode to reorder human onboarding guidance while keeping machine-safe commands prompt-free and contract-stable.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED tests for one-time setup and explicit settings editing** - `884aa12` (`test`)
2. **Task 2: Implement first-run setup and the `brainpack settings` flow** - `081e0db` (`feat`)

## Files Created/Modified
- `brainpack/cli.py` - wires the one-time setup gate, adds `brainpack settings`, and reorders human guidance by saved preference
- `brainpack/interactive.py` - implements prompt-driven setup/settings flows with staged confirmation and cancel-safe persistence
- `brainpack/settings.py` - exposes machine-valid setup choices, dynamic defaults, and human-readable settings summaries
- `tests/test_cli.py` - covers first-run setup, explicit settings edits, preference-aware guidance, and cancel behavior
- `tests/test_cli_json.py` - pins that saved human preferences do not leak into `status --json`
- `tests/test_settings.py` - covers valid setup choice derivation and settings summary rendering

## Decisions Made
- Kept the post-setup and post-settings next action narrow: both flows point to `brainpack create` instead of auto-routing into another command.
- Reused the same staged-questionnaire implementation for initial setup and later edits so cancellation semantics stay identical.
- Reflected saved mode preference by changing guidance order instead of inventing separate agent/local copy branches.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed machine-specific transcription defaults being frozen at import time**
- **Found during:** Task 2 (Implement first-run setup and the `brainpack settings` flow)
- **Issue:** `BrainpackSettings.preferred_transcription_backend` evaluated `_recommended_transcription_backend()` at import time, which could make machine-valid setup choices stale or incorrect.
- **Fix:** Switched the dataclass field to `default_factory=_recommended_transcription_backend` so defaults and choice derivation stay runtime-aware.
- **Files modified:** `brainpack/settings.py`
- **Verification:** `uv run pytest tests/test_settings.py -q`
- **Committed in:** `081e0db`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix was required for correct machine-specific setup choices and stayed within the planned Phase 11 scope.

## Issues Encountered
- Parallel `git add` calls briefly contended on `.git/index.lock`; resolved by restaging sequentially because the conflict came from concurrent index writes, not repo damage.
- `requirements mark-complete` returned a no-op because `ONB-01`, `PCK-05`, `RUN-01`, `AUT-01`, and `AUT-02` were already marked complete in the current `REQUIREMENTS.md`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 11 now has a real first-run setup path and explicit settings editor for future guided authoring work.
- Human guidance can react to saved mode preference without weakening machine-safe CLI and MCP contracts.
- No known blockers for `11-03`; the next plan can build guided pack authoring on the stable prompt and settings seams added here.

## Self-Check: PASSED

- Found `.planning/phases/11-add-interactive-setup-settings-and-guided-pack-authoring-ux/11-02-SUMMARY.md`
- Found task commit `884aa12`
- Found task commit `081e0db`
