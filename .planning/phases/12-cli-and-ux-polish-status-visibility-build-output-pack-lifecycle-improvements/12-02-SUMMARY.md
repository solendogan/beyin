---
phase: 12-cli-and-ux-polish-status-visibility-build-output-pack-lifecycle-improvements
plan: 02
subsystem: cli
tags: [cli, inventory, status, list, home, ux, tdd]

requires:
  - phase: 12-01
    provides: lifecycle recap helpers and build state persistence for status surfaces

provides:
  - Inventory-first no-arg home routing for TTY sessions with installed packs
  - status command reordered to summary-first layout (pack facts, provenance, blockers before sources)
  - list human output stays compact without coaching blocks
  - list/status --json machine payloads stable and prompt-free

affects:
  - 12-03
  - any future CLI surface that uses home/list/status rendering

tech-stack:
  added: []
  patterns:
    - "Inventory-first TTY routing: check for installed packs before deciding home vs. authoring menu"
    - "Summary-first status: pack facts and provenance appear before detail rows (sources)"

key-files:
  created: []
  modified:
    - brainpack/cli.py
    - tests/test_cli.py

key-decisions:
  - "Inventory-first home: TTY sessions with installed packs route to the home table, not the authoring menu; authoring menu is only shown when inventory is empty"
  - "Status is summary-first: origin/provenance and blockers/warnings render before the Sources section so pack facts scan immediately"
  - "Ready-pack status shows no coaching copy; blocked-pack status surfaces blockers inline without appending the full guidance block"
  - "list/status --json machine payloads unchanged; human output changes are fully contained in the human branch"

requirements-completed: [ONB-01, PCK-04, PCK-05, AUT-01, AUT-02]

duration: 5min
completed: 2026-03-17
---

# Phase 12 Plan 02: Inventory-First Home/List/Status Rendering Summary

**Inventory-first TTY routing and summary-first status layout — pack table shown on no-arg entry when packs exist, provenance and blockers before source rows in status**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-17T15:59:49Z
- **Completed:** 2026-03-17T16:05:21Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- No-arg TTY with installed packs now shows the inventory table directly instead of routing into the authoring menu
- `brainpack status <pack>` renders pack facts, origin/provenance, and blockers/warnings before the Sources section
- `brainpack list` confirmed compact and coaching-free (no "Use with agent" blocks)
- All list/status `--json` machine payloads unchanged and prompt-free

## Task Commits

1. **Task 1: RED tests for inventory-first home/list/status** - `9f0155e` (test)
2. **Task 2: Implement inventory-first rendering** - `a90960c` (feat)

## Files Created/Modified
- `brainpack/cli.py` - main() inventory-first TTY routing; status_command() summary-first layout with provenance before sources
- `tests/test_cli.py` - 8 new tests covering home routing, list compactness, status ordering, coaching suppression, and JSON stability

## Decisions Made
- Inventory-first routing logic: `list_packs()` called once in `main()` to distinguish empty-inventory (authoring menu) from installed-packs (home table)
- Status provenance is taken directly from `summary["origin"]` already present in the inspect_pack dict — no extra load_pack_origin call needed
- Existing test `test_no_arg_interactive_home_routes_to_authoring_menu_after_setup` updated to specify an empty tmp packs dir because the semantics changed (authoring menu now only appears for empty inventories)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing test used real ~/.brainpacks instead of isolated temp dir**
- **Found during:** Task 2 (GREEN implementation)
- **Issue:** `test_no_arg_interactive_home_routes_to_authoring_menu_after_setup` had no `_PACKS_DIR` patch, so it read from `~/.brainpacks` which has packs on this machine, causing it to hit the new inventory-first path instead of the authoring menu
- **Fix:** Added `tmp_path` fixture and patched `_PACKS_DIR` to an empty temp directory to isolate the test
- **Files modified:** tests/test_cli.py
- **Verification:** All 29 home/list/status tests pass; full suite 128 passed, 3 xfailed, 7 xpassed
- **Committed in:** a90960c (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — test isolation)
**Impact on plan:** Necessary correctness fix. No scope creep.

## Issues Encountered
None - implementation was straightforward once the existing test isolation issue was found and fixed.

## Next Phase Readiness
- Inventory-first home and summary-first status are in place
- list/status --json contracts verified stable
- Ready for Phase 12 Plan 03 (build output improvements)

---
*Phase: 12-cli-and-ux-polish-status-visibility-build-output-pack-lifecycle-improvements*
*Completed: 2026-03-17*
