---
phase: 10-update-agent-and-local-mode-onboarding
plan: 01
subsystem: ui
tags: [cli, typer, onboarding, mcp, inventory, testing]
requires:
  - phase: 08-mcp-server-mode
    provides: "Local stdio MCP server entrypoint for same-machine agent usage"
  - phase: 09-make-agent-mode-retrieval-first
    provides: "Retrieval-first agent positioning and evidence-first MCP flow"
provides:
  - "Two-path onboarding copy for fresh-install and installed-pack home screens"
  - "Shared human-facing guidance seam for status and retrieval precondition output"
  - "Lifecycle reason alignment without changing machine-safe next_action payloads"
affects: [phase-10-02, onboarding-docs, cli-help, mcp-guidance]
tech-stack:
  added: []
  patterns:
    - "Separate human-facing lifecycle guidance from machine-safe next_action contracts"
    - "Reuse one CLI onboarding renderer across home, status, and retrieval errors"
key-files:
  created:
    - ".planning/phases/10-update-agent-and-local-mode-onboarding/10-01-SUMMARY.md"
  modified:
    - "brainpack/cli.py"
    - "brainpack/inventory.py"
    - "tests/test_cli.py"
    - "tests/test_cli_json.py"
key-decisions:
  - "Kept serialized next_action stable for JSON and MCP while introducing a separate human_guidance_command seam for CLI output."
  - "Updated next_action_reason() to describe agent/local-mode lifecycle intent rather than stale chat-first recovery prose."
  - "Treated failed packs as error before new/needs-build so human guidance reflects the real lifecycle state."
patterns-established:
  - "Human CLI recommendations should come from a dedicated seam instead of reusing machine-contract fields directly."
  - "Plan verification selectors must match real test names so command-scoped regression slices stay executable."
requirements-completed: [ONB-01, PCK-05, AUT-01, AUT-02, OCL-02]
duration: 4min
completed: 2026-03-14
---

# Phase 10 Plan 01: Update Agent and Local Mode Onboarding Summary

**Two-mode CLI onboarding with agent-first guidance, shared lifecycle recovery copy, and stable machine-safe pack contracts**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-14T20:37:25Z
- **Completed:** 2026-03-14T20:41:48Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added explicit `Use with agent` and `Use with local model` onboarding guidance to the no-arg home screen and Typer help surfaces.
- Routed status output and human retrieval-precondition failures through one shared onboarding-aware guidance renderer.
- Preserved JSON/MCP `next_action` stability while aligning machine-safe lifecycle reasons and fixing failed-pack lifecycle classification.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add RED CLI coverage for the two-mode onboarding story** - `58329ec` (test)
2. **Task 2: Implement the two-path copy and human-facing guidance seam** - `aa9239c` (feat)
3. **Verification hardening: Keep plan `next_action` selectors executable** - `ee9981f` (test)

**Plan metadata:** pending docs commit

## Files Created/Modified
- `brainpack/cli.py` - Added shared onboarding renderer, updated home/status/precondition output, and reframed help metadata around agent vs local mode.
- `brainpack/inventory.py` - Added human-facing lifecycle command helper, aligned lifecycle reason text, and fixed failed-pack status ordering.
- `tests/test_cli.py` - Locked home-screen, status, help, and human precondition guidance around the two-mode onboarding story.
- `tests/test_cli_json.py` - Locked onboarding-aligned lifecycle reasons while preserving machine-safe `next_action` expectations and verification selectors.

## Decisions Made

- Kept `serialize_pack_summary()` and MCP/list/status machine payloads unchanged for `next_action`; only human CLI output uses the new guidance seam.
- Reused one `_render_usage_guidance()` helper across home, status, and retrieval failures to prevent copy drift between surfaces.
- Promoted failed-pack lifecycle detection ahead of `new` so error states no longer masquerade as initial build guidance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Failed packs were still surfacing as `new`/`needs-build`**
- **Found during:** Task 2
- **Issue:** `summarize_pack()` checked `is_new` before `has_error`, so a pack with failed sources printed the wrong lifecycle state and guidance.
- **Fix:** Reordered lifecycle evaluation so `error` wins before `new` and `needs-build`.
- **Files modified:** `brainpack/inventory.py`
- **Verification:** `uv run pytest tests/test_cli.py tests/test_cli_json.py -k "home_screen or help or status or blocked_pack or unbuilt_pack" -q`
- **Committed in:** `aa9239c`

**2. [Rule 3 - Blocking] Planned `-k "next_action"` verification collected zero tests**
- **Found during:** Post-task verification
- **Issue:** The exact plan verification command returned pytest exit code `5` because no test names in `tests/test_cli_json.py` matched `next_action`.
- **Fix:** Renamed the relevant JSON regression tests to include `next_action`, keeping the planned selector executable without changing assertions.
- **Files modified:** `tests/test_cli_json.py`
- **Verification:** `uv run pytest tests/test_cli_json.py -k "next_action" -q`
- **Committed in:** `ee9981f`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes were required to keep lifecycle guidance correct and to make the plan's own verification commands executable. No scope expansion beyond the onboarding/test seam.

## Issues Encountered

- `git add brainpack/inventory.py` briefly failed on a transient `.git/index.lock`; retry succeeded once the stale lock disappeared, so no repository cleanup was required.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The CLI now consistently presents Agent Mode as the recommended path while keeping Local Mode explicit and intact.
- Future onboarding/docs work can build on `_render_usage_guidance()` and `human_guidance_command()` without touching JSON/MCP payload contracts.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/10-update-agent-and-local-mode-onboarding/10-01-SUMMARY.md`.
- Task and verification commits `58329ec`, `aa9239c`, and `ee9981f` are present in git history.

---
*Phase: 10-update-agent-and-local-mode-onboarding*
*Completed: 2026-03-14*
