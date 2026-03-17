---
phase: 12-cli-and-ux-polish-status-visibility-build-output-pack-lifecycle-improvements
plan: 04
subsystem: cli
tags: [typer, lifecycle, remove, reset, update, pack-management]

# Dependency graph
requires:
  - phase: 12-03
    provides: build-report seam, persistent build verdicts, and lifecycle helpers foundation
provides:
  - first-class brainpack remove command with TTY confirmation and --yes/--force bypass
  - brainpack build --reset flag that clears runtime artifacts before rebuild
  - check_model_provenance remediation message pointing to build --reset
  - update command communicates when no remote origin refresh occurred
  - status command factual lifecycle manage section
  - home screen lifecycle management affordances
affects:
  - MCP server (remove/reset are human-only, not MCP tools)
  - documentation / onboarding (manual deletion guidance replaced)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Lifecycle destructive actions require explicit --yes/--force in non-interactive sessions
    - reset_pack_runtime/remove_installed_pack called from cli.py — lifecycle helpers remain in lifecycle.py
    - Status/home surfaces expose factual manage commands without recommendation-heavy coaching

key-files:
  created:
    - .planning/phases/12-cli-and-ux-polish-status-visibility-build-output-pack-lifecycle-improvements/12-04-SUMMARY.md
  modified:
    - brainpack/cli.py
    - brainpack/pack_state.py
    - tests/test_cli.py

key-decisions:
  - "remove is first-class, requires --yes/--force in non-interactive sessions, prompts in TTY sessions"
  - "build --reset delegates to reset_pack_runtime() then reuses the ordinary build path — no second rebuild implementation"
  - "check_model_provenance remediation now points to `brainpack build <pack> --reset` instead of manual chroma/ deletion"
  - "update communicates rebuild-only when no origin is stored, rather than silently rebuilding"
  - "status manage section is compact and factual — no prescriptive recommendation coaching"

patterns-established:
  - "Destructive CLI flows: interactive prompts require TTY, non-interactive requires explicit --yes/--force"
  - "Recovery path messages in error/mismatch contexts must name the supported command, not a filesystem path"

requirements-completed: [ONB-01, PCK-04, PCK-05, RUN-01]

# Metrics
duration: 8min
completed: 2026-03-17
---

# Phase 12 Plan 04: Pack Lifecycle Management Summary

**First-class remove/reset lifecycle commands with explicit destructive wording, model-mismatch remediation pointing to `build --reset`, and factual manage affordances on status/home surfaces**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-17T16:22:47Z
- **Completed:** 2026-03-17T16:30:12Z
- **Tasks:** 2 (TDD: RED then GREEN)
- **Files modified:** 3

## Accomplishments

- `brainpack remove <pack>` added as a first-class command — confirms interactively in TTY sessions, requires `--yes`/`--force` in non-interactive use, uses explicit destructive wording in output
- `brainpack build <pack> --reset` added — calls `reset_pack_runtime()` to clear chroma/audio/transcripts/meta.json, then reuses the existing build pipeline; `pack.yaml` and `origin.json` survive
- `check_model_provenance` remediation message updated to name `brainpack build <pack> --reset` as the recovery path instead of advising manual `~/.brainpacks/.../chroma/` deletion
- `update` now prints "No remembered origin — rebuilding installed pack without remote refresh" when no origin is stored, making the one-shot behavior explicit
- `status_command` exposes a compact "Manage:" section with `status`, `update`, `build --reset`, and `remove` commands
- Home screen with installed packs adds a manage affordances line

## Task Commits

1. **Task 1: Write RED tests** - `6c3a77a` (test)
2. **Task 2: Implement lifecycle commands and guidance** - `03d39c8` (feat)

## Files Created/Modified

- `brainpack/cli.py` — remove_command, build --reset flag, lifecycle imports, status manage section, home manage line, update clarity message
- `brainpack/pack_state.py` — check_model_provenance remediation now points to `build --reset`
- `tests/test_cli.py` — 11 new tests covering remove/reset/update/manage/status/home lifecycle flows

## Decisions Made

- `remove` uses interactive `_confirm()` from `interactive.py` in TTY sessions, not a new prompt implementation — consistent with existing interactive patterns
- `build --reset` calls `reset_pack_runtime()` before running the unchanged build path — no duplication
- Manage section in `status` is compact `dim()` text, not a bold section, keeping status summary-first
- `update` clarity message is printed only on the no-origin branch, not the origin-found branch

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock_config.id not set in test causing id-mismatch early exit**
- **Found during:** Task 2 (GREEN phase — `test_update_with_remembered_origin_fetches_and_rebuilds` failing)
- **Issue:** `_make_config()` helper sets `cfg.name` but not `cfg.id`; MagicMock returns another MagicMock for `.id`, which compared unequal to `"test-pack"` and caused `update` to exit before calling `build`
- **Fix:** Added `mock_config.id = "test-pack"` after `_make_config()` call in the affected test
- **Files modified:** tests/test_cli.py
- **Verification:** `test_update_with_remembered_origin_fetches_and_rebuilds` passes
- **Committed in:** `03d39c8` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test fixture)
**Impact on plan:** Narrow fix to test helper, no production code change.

## Issues Encountered

None beyond the test fixture bug above.

## Next Phase Readiness

Phase 12 is now complete. All four plans delivered:
- 12-01: lifecycle recap state and reset/remove helper foundations
- 12-02: status visibility improvements (summary-first, origin/provenance)
- 12-03: build output polish and persistent verdicts via BuildReport seam
- 12-04: first-class remove/reset lifecycle commands and supported reset guidance

---
*Phase: 12-cli-and-ux-polish-status-visibility-build-output-pack-lifecycle-improvements*
*Completed: 2026-03-17*
