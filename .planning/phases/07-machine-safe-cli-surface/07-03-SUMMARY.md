---
phase: 07-machine-safe-cli-surface
plan: 03
subsystem: cli
tags: [typer, cli, json, query, chat, automation]
requires:
  - phase: 07-01
    provides: "shared machine envelope helpers, exit taxonomy, and machine command wrapper"
provides:
  - "stable `brainpack query <pack> <question> --json` responses with shared retrieval payloads"
  - "stable one-shot `brainpack chat <pack> <question> --json` responses aligned to the query payload shape"
  - "structured retrieval-side failures for missing packs, runtime blockers, and unsupported interactive JSON chat"
affects: [machine-safe-cli-surface, cli, json, query, chat]
tech-stack:
  added: []
  patterns:
    - "Covered retrieval commands should build one shared machine payload before rendering human or JSON output."
    - "Interactive chat stays human-only; machine-safe chat is limited to one-shot requests."
key-files:
  created: []
  modified:
    - brainpack/cli.py
    - tests/test_cli_json.py
key-decisions:
  - "Query and one-shot chat machine responses expose explicit public source fields instead of raw retrieval metadata."
  - "Interactive `chat --json` is rejected with a usage envelope rather than creating a session protocol."
patterns-established:
  - "Use `_build_retrieval_payload()` plus `_serialize_query_source()` so query and one-shot chat stay schema-aligned."
  - "Route query/chat `--json` through `run_machine_command()` so readiness and usage failures remain stdout-only JSON."
requirements-completed: [AUT-01, AUT-02]
duration: 6min
completed: 2026-03-13
---

# Phase 07 Plan 03: Retrieval JSON Summary

**`brainpack query --json` and one-shot `brainpack chat --json` now share one retrieval schema and return structured machine-safe failures instead of human readiness prose.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-13T14:04:00Z
- **Completed:** 2026-03-13T14:10:23Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added RED contract tests for query/chat JSON success, missing-pack failures, runtime-blocked query failures, blocked chat failures, and unsupported interactive JSON chat.
- Added `--json` handling to `query` and `chat` without changing the existing human-facing output paths.
- Normalized retrieval responses through one shared payload builder so query and one-shot chat expose the same answer/source shape.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED tests for query/chat JSON flows** - `d254557` (test)
2. **Task 2: Implement query/chat JSON output and structured runtime failures** - `85f3291` (feat)

## Files Created/Modified
- `brainpack/cli.py` - Adds retrieval payload serialization plus machine-safe `--json` handling for query and one-shot chat.
- `tests/test_cli_json.py` - Extends the machine contract suite with retrieval success, failure, and unsupported interactive-mode coverage.
- `.planning/STATE.md` - Records completion of `07-03` and the retrieval JSON contract decisions for later Phase 7 work.

## Decisions Made

- Query and one-shot chat machine responses now serialize sources explicitly as public `url`, `title`, and optional timestamp fields instead of passing through raw retrieval metadata.
- `chat --json` requires a question and returns `interactive_json_not_supported` with exit code `2` when invoked without one.
- Chat readiness failures collapse multi-line blocker prose to the first machine-stable line before entering `error.details`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The initial GREEN run used default OpenAI success fixtures without an API key, so the test fixtures were updated to provide a ready runtime instead of failing on unrelated preconditions.
- Chat blocker details initially carried full multi-line readiness prose; the implementation was tightened to normalize blocker text to one stable line for the machine contract.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 7 now has machine-safe inventory and retrieval surfaces on the primary read commands.
`07-04` can focus on hardening stdout purity, additive stability, and exit-code regressions across the whole machine contract.

## Self-Check: PASSED

- Verified `.planning/phases/07-machine-safe-cli-surface/07-03-SUMMARY.md` exists on disk.
- Verified task commits `d254557` and `85f3291` exist in git history.
