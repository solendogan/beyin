---
phase: 11-add-interactive-setup-settings-and-guided-pack-authoring-ux
plan: 01
subsystem: ui
tags: [typer, inquirerpy, settings, cli, tdd]
requires:
  - phase: 10-update-agent-and-local-mode-onboarding
    provides: shared no-arg onboarding copy and machine-safe command surfaces
provides:
  - versioned global Brainpack settings under ~/.brainpacks/settings.json
  - TTY-only interactive adapter helpers with lazy InquirerPy loading
  - no-subcommand first-run setup gating without changing JSON or MCP behavior
affects: [phase-11-02, settings-flow, guided-authoring]
tech-stack:
  added: [InquirerPy]
  patterns: [atomic settings persistence, lazy interactive adapter, no-subcommand setup gate]
key-files:
  created: [brainpack/settings.py, brainpack/interactive.py, tests/test_settings.py]
  modified: [brainpack/cli.py, pyproject.toml, uv.lock, tests/test_cli.py, tests/test_cli_json.py]
key-decisions:
  - "Global setup state lives in ~/.brainpacks/settings.json and stays separate from pack.yaml, origin.json, and meta.json."
  - "The CLI only considers first-run setup on the no-subcommand path when both stdin and stdout are TTYs."
  - "InquirerPy stays behind load_prompt_backend() and normalize_prompt_abort() so normal imports, JSON, and MCP paths remain prompt-free."
patterns-established:
  - "Settings writes use tempfile plus os.replace so interrupted writes do not leave partial settings.json files behind."
  - "Interactive seams are additive: explicit commands keep their current non-interactive behavior even when setup is incomplete."
requirements-completed: [ONB-01, RUN-01, AUT-02]
duration: 4min
completed: 2026-03-15
---

# Phase 11 Plan 01: Interactive Settings Foundation Summary

**Versioned global settings storage, lazy InquirerPy loading, and a TTY-only first-run setup gate that preserves current machine-safe CLI behavior**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-15T01:08:57Z
- **Completed:** 2026-03-15T01:12:38Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added `brainpack.settings` with default resolution, migration-safe loading, and atomic persistence under `~/.brainpacks/settings.json`.
- Added `brainpack.interactive` with TTY detection, lazy `InquirerPy` loading, and one normalized cancellation path for later setup/settings flows.
- Wired `brainpack.cli` so only the no-subcommand path considers first-run setup, while existing `--json` and MCP-facing surfaces remain non-interactive.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED tests for the global settings seam and TTY-only setup gate** - `f9f2dd5` (`test`)
2. **Task 2: Implement the settings store and lightweight interactive adapter foundation** - `c6a0fc7` (`feat`)
3. **Task 2 follow-up: Sync dependency lockfile for the new interactive dependency** - `5d3d297` (`chore`)

## Files Created/Modified

- `brainpack/settings.py` - versioned settings model, defaults, load/save helpers, and initial setup detection
- `brainpack/interactive.py` - lazy prompt backend loading, TTY detection, and normalized interactive aborts
- `brainpack/cli.py` - no-subcommand setup gate seam ahead of the existing home screen
- `pyproject.toml` - declares the minimal `InquirerPy` dependency for later guided flows
- `uv.lock` - locks `InquirerPy` and transitive prompt dependencies
- `tests/test_settings.py` - RED-to-GREEN coverage for settings defaults, migration, and atomic writes
- `tests/test_cli.py` - TTY-only setup gating and lazy import boundary tests
- `tests/test_cli_json.py` - machine-safe regression coverage proving JSON commands stay prompt-free

## Decisions Made

- Kept the current home screen behavior in place for now and only added the setup-routing seam, because the full questionnaire lands in later Phase 11 plans.
- Treated interactive prompting as an adapter concern rather than a CLI rewrite, so explicit commands and automation surfaces do not inherit prompt state.
- Used JSON for machine-level settings to match Brainpack's other sidecar state files and keep migration logic simple.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Synced `uv.lock` after adding the new prompt dependency**
- **Found during:** Task 2 (Implement the settings store and lightweight interactive adapter foundation)
- **Issue:** Adding `InquirerPy` to `pyproject.toml` left the lockfile out of sync after `uv run` refreshed the environment.
- **Fix:** Committed the generated `uv.lock` updates for `InquirerPy` and its transitive prompt dependencies.
- **Files modified:** `uv.lock`
- **Verification:** `uv run pytest tests/test_settings.py tests/test_cli.py tests/test_cli_json.py tests/test_mcp_server.py -q`
- **Committed in:** `5d3d297`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Lockfile sync was necessary for reproducible installs and did not expand scope beyond the planned dependency addition.

## Issues Encountered

- None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 11 now has the reusable settings and interactive seams needed for actual setup, settings, and guided authoring flows.
- JSON and MCP regression coverage is in place, so later interactive work has a clear guardrail against prompt leakage.

## Self-Check

PASSED
