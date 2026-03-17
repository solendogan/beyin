---
phase: 12
plan: 03
subsystem: build-output-polish
tags: [build, progress, summary-table, recap, persistence, tdd]
dependency_graph:
  requires: [12-02, pack_state, build_report]
  provides: [build_report.py, build-output-polish, recap-persistence]
  affects: [cli.py, pack_state.py, tests/test_cli.py, tests/test_inventory.py]
tech_stack:
  added: [brainpack/build_report.py]
  patterns: [BuildReport event accumulator, always-on summary table, verdict rendering, recap persistence]
key_files:
  created:
    - brainpack/build_report.py
  modified:
    - brainpack/cli.py
    - tests/test_cli.py
    - tests/test_inventory.py
    - tests/test_mcp_server.py
decisions:
  - "BuildReport seam accumulates events during build loop; cli.py only appends and calls render"
  - "All builds exit non-zero when any source fails or is blocked (not just blocked audio)"
  - "last_build_result and last_build_summary persisted for every build outcome (success/mixed/blocked)"
  - "Summary table always printed — zero-new runs now show the table with skipped rows"
  - "Issues recap section added after verdict line for failed/blocked sources"
metrics:
  duration: 14 min
  completed_date: "2026-03-17"
  tasks_completed: 2
  files_changed: 5
---

# Phase 12 Plan 03: Build Output Polish Summary

**One-liner:** Normalized BuildReport seam with always-on summary table, explicit mixed-result verdicts, recap persistence, and non-zero exit for all unresolved failures.

## Objective

Polish `brainpack build` into a clear lifecycle surface. Introduced one normalized build-report seam, preserved live progress, always print a compact final summary table, and record mixed-result recaps so the status screen can reflect the last build honestly.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Write failing tests for build output polish | a85a14c | tests/test_cli.py, tests/test_inventory.py |
| 2 (GREEN) | Implement normalized build-report seam and persistent verdicts | 6adcd4a | brainpack/build_report.py, brainpack/cli.py, tests/test_cli.py, tests/test_mcp_server.py |

## What Was Built

### brainpack/build_report.py (new)

Small `BuildReport` dataclass with `BuildEvent` records. Tracks per-source outcomes (done/skipped/failed/blocked) during the build loop and generates:
- `render_table()` — compact Source/Status/New/Skipped table (always rendered)
- `render_verdict()` — single verdict line: "Build complete" or "Build completed with issues"
- `render_issues_recap()` — optional issues recap section listing failed/blocked sources
- `result` property — "success" | "mixed" | "blocked" for state persistence
- `summary_line` property — one-line string for `last_build_summary` persistence

### brainpack/cli.py (modified)

Replaced the ad-hoc `source_results: list[dict]` + `blocked_sources: int` tracking with a single `BuildReport` instance. Key changes:

1. **Always-on summary table** — printed for every build, including zero-new runs
2. **Explicit verdict** — "Build complete" vs "Build completed with issues — N failed, M blocked"
3. **Issues recap** — failed/blocked sources listed after the verdict for quick visibility
4. **Recap persistence** — `last_build_result` and `last_build_summary` written to state for ALL outcomes (not just successful builds)
5. **Consistent exit semantics** — exit code 1 for any unresolved failure (failed + blocked), not just blocked audio sources

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated two existing tests with old exit-code expectations**
- **Found during:** Task 2 GREEN phase
- **Issue:** `test_build_local_path_missing_file_fails_clearly` and `test_build_local_path_unsupported_suffix_fails_clearly` expected exit code 0 for builds with failed sources. The plan's spec ("unresolved failures still return non-zero") made exit=1 correct.
- **Fix:** Updated both tests to assert `exit_code == 1` with an explanatory comment referencing plan 12-03
- **Files modified:** tests/test_cli.py
- **Commit:** 6adcd4a

**2. [Rule 1 - Bug] Updated MCP server build test for new output format**
- **Found during:** Task 2 GREEN verification
- **Issue:** `test_mcp_build_returns_structured_command_result` checked for old "Build complete." and "Total: 3 new chunks indexed." strings that no longer exist
- **Fix:** Updated assertions to match new verdict format ("Build complete" + chunk count in table/verdict)
- **Files modified:** tests/test_mcp_server.py
- **Commit:** 6adcd4a

## Verification Results

```
uv run pytest tests/test_cli.py -k "build" -q
# 39 passed, 1 xfailed, 3 xpassed

uv run pytest tests/test_inventory.py -q
# 4 passed

uv run pytest tests/test_mcp_server.py -k "build" -q
# 3 passed
```

Full suite: 267 passed, 3 xfailed, 7 xpassed — no regressions.

## Self-Check: PASSED

- brainpack/build_report.py: FOUND
- 12-03-SUMMARY.md: FOUND
- Commit a85a14c (RED tests): FOUND
- Commit 6adcd4a (GREEN impl): FOUND
