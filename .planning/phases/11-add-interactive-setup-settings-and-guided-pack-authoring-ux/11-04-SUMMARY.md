---
phase: 11-add-interactive-setup-settings-and-guided-pack-authoring-ux
plan: 04
subsystem: cli
tags: [typer, trafilatura, local-files, settings, pytest]
requires:
  - phase: 11-03
    provides: guided create/import/manage seams that can now persist local text-like sources
provides:
  - narrow local text-like build ingestion for authored file paths
  - deterministic whisper-model default resolution across CLI flags, pack config, and global settings
  - phase-local traceability artifact for Phase 11 requirement and scope coverage
affects: [build, settings, authoring, json, mcp]
tech-stack:
  added: []
  patterns:
    - narrow local text-like ingestion through the existing article build branch
    - explicit build-default precedence using pack-config metadata plus global settings
key-files:
  created:
    - .planning/phases/11-add-interactive-setup-settings-and-guided-pack-authoring-ux/11-TRACEABILITY.md
  modified:
    - brainpack/cli.py
    - brainpack/downloader.py
    - brainpack/ingester.py
    - brainpack/settings.py
    - brainpack/config.py
    - brainpack/authoring.py
    - tests/test_ingester.py
    - tests/test_downloader.py
    - tests/test_cli.py
    - tests/test_cli_json.py
key-decisions:
  - "Local file ingestion stays limited to text-like suffixes and reuses the article branch instead of introducing a broader document parser."
  - "Build-time whisper defaults now resolve as CLI flag, then explicit pack.yaml whisper_model, then global settings, then the hardcoded fallback."
  - "pack.yaml-like inputs remain import-only and unsupported local files fail clearly instead of being silently treated as articles."
patterns-established:
  - "Preserve config-key intent with explicit metadata when defaults would otherwise hide whether a pack.yaml field was set."
  - "Keep machine-safe JSON verification in place whenever human-facing authoring/build behavior expands."
requirements-completed: [ONB-02, RUN-01, RUN-02, AUT-01, AUT-02]
duration: 12min
completed: 2026-03-15
---

# Phase 11 Plan 04: Local text-like pack builds with settings-aware whisper defaults Summary

**Local text-like pack sources now build end-to-end through the existing article branch, with deterministic whisper-model precedence and an explicit Phase 11 traceability note**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-15T01:44:00Z
- **Completed:** 2026-03-15T01:56:03Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Added RED coverage for local text-like ingestion, pack-vs-content source classification, whisper default precedence, JSON stability, and the phase traceability artifact.
- Implemented narrow local-file ingestion for supported text-like paths and kept pack imports and unsupported local files on explicit failure paths.
- Resolved the saved-settings versus pack.yaml `whisper_model` mismatch so `build` and `update` compose with Phase 11 settings instead of bypassing them.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED tests for local text-like source builds and default precedence** - `e87c7e5` (test)
2. **Task 2: Implement minimal local text-like ingestion and deterministic build defaults** - `d7e43df` (feat)

**Verification follow-up:** `b3e4c01` (test)

## Files Created/Modified

- `.planning/phases/11-add-interactive-setup-settings-and-guided-pack-authoring-ux/11-TRACEABILITY.md` - Phase-local requirement and scope mapping for the completed Phase 11 work.
- `brainpack/cli.py` - Wires local text-like sources into build, applies resolved whisper defaults, and keeps explicit import boundaries.
- `brainpack/downloader.py` - Distinguishes remote URLs, local text-like files, unsupported local files, and pack imports.
- `brainpack/ingester.py` - Adds the narrow local text-like loader alongside the existing remote article fetch helper.
- `brainpack/settings.py` - Centralizes build-default resolution for whisper model precedence.
- `brainpack/config.py` - Preserves whether `whisper_model` was explicitly set in `pack.yaml`.
- `brainpack/authoring.py` - Rejects unsupported local files earlier while keeping pack imports on the `add` path.
- `tests/test_ingester.py` - Covers successful and failing local text-like loads.
- `tests/test_downloader.py` - Covers local text-like and pack.yaml source classification.
- `tests/test_cli.py` - Covers local-path builds, missing/unsupported local-file failures, precedence resolution, and traceability existence.
- `tests/test_cli_json.py` - Pins machine-safe status JSON for packs authored from local text-like sources.

## Decisions Made

- Used one narrow `load_text_like_source()` helper and the existing article branch instead of designing a new ingestion framework.
- Added `whisper_model_explicit` to parsed config objects so global settings can win only when `pack.yaml` omits the field.
- Kept `build` and `update` option semantics scriptable by making CLI `--model` optional rather than letting Typer’s default hide whether the user actually passed a flag.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Preserved explicit-vs-default pack intent for whisper precedence**
- **Found during:** Task 2 (Implement minimal local text-like ingestion and deterministic build defaults)
- **Issue:** `load_config()` always materialized `whisper_model="small"`, which would have prevented global settings from ever winning when the key was omitted from `pack.yaml`.
- **Fix:** Added `whisper_model_explicit` metadata during config parsing and used it inside the shared build-default resolver.
- **Files modified:** `brainpack/config.py`, `brainpack/settings.py`, `brainpack/cli.py`
- **Verification:** `uv run pytest tests/test_cli.py -k "whisper or build" -q`
- **Committed in:** `d7e43df`

**2. [Rule 3 - Blocking] Updated stale Phase 11 interaction tests to match landed home-flow behavior**
- **Found during:** Plan verification
- **Issue:** Two existing tests still assumed the no-arg interactive path stopped after setup or performed only one TTY check, which no longer matched the Phase 11 authoring-menu route already in the codebase.
- **Fix:** Adjusted the expectations to match the current no-arg setup-plus-authoring control flow so the verification suite could exercise the new build changes without false failures.
- **Files modified:** `tests/test_cli.py`
- **Verification:** `uv run pytest tests/ -q`
- **Committed in:** `b3e4c01`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** Both fixes were required to make the intended precedence and verification story coherent. Scope stayed within Phase 11’s locked boundaries.

## Issues Encountered

- `.planning/` is gitignored, so the new traceability artifact and summary require explicit `git add -f` handling during documentation commits.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 11’s promised setup/settings/authoring path is now complete, including end-to-end local text-like builds.
- Machine-safe JSON and MCP regressions passed after the build-path expansion, so the milestone is ready for closeout or follow-up roadmap work.

## Self-Check

PASSED

- Found `.planning/phases/11-add-interactive-setup-settings-and-guided-pack-authoring-ux/11-04-SUMMARY.md`
- Found `.planning/phases/11-add-interactive-setup-settings-and-guided-pack-authoring-ux/11-TRACEABILITY.md`
- Verified task and verification commits: `e87c7e5`, `d7e43df`, `b3e4c01`

---
*Phase: 11-add-interactive-setup-settings-and-guided-pack-authoring-ux*
*Completed: 2026-03-15*
