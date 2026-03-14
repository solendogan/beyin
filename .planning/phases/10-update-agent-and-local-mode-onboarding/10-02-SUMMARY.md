---
phase: 10-update-agent-and-local-mode-onboarding
plan: 02
subsystem: docs
tags: [docs, onboarding, mcp, local-model, product-positioning]
requires:
  - phase: 10-01
    provides: "Two-mode onboarding language and the recommended agent-first product framing"
  - phase: 09-make-agent-mode-retrieval-first
    provides: "Retrieval-first agent story and evidence-first MCP direction"
provides:
  - "Long-form product overview aligned to the agent and local mode split"
  - "Tech stack narrative aligned to the shipped local stdio MCP server"
  - "Explicit first-run order for both onboarding paths in broader markdown docs"
affects: [onboarding-docs, product-story, mcp-docs, local-mode-docs]
tech-stack:
  added: []
  patterns:
    - "Long-form docs should mirror the exact onboarding order already locked in CLI guidance"
    - "Agent-mode docs describe Brainpack as evidence retrieval for a same-machine agent, not the final-answer writer"
key-files:
  created:
    - ".planning/phases/10-update-agent-and-local-mode-onboarding/10-02-SUMMARY.md"
  modified:
    - "brainpack.md"
    - "brainpack-techstack.md"
key-decisions:
  - "Reframed both long-form docs around the same two-path story used by the CLI: Use with agent and Use with local model."
  - "Pointed the recommended path to the shipped `brainpack mcp-server` command instead of legacy attach-style or future-server concepts."
  - "Kept `query` and `chat` explicitly documented as the standalone local-mode path rather than treating them as deprecated."
patterns-established:
  - "Support docs should repeat the exact first-run sequence for each mode instead of implying it through prose."
  - "Technical docs should describe the current local stdio MCP implementation, not hypothetical remote integration paths."
requirements-completed: [ONB-01, OCL-02]
duration: 2min
completed: 2026-03-14
---

# Phase 10 Plan 02: Long-Form Onboarding Docs Summary

**Agent-first long-form docs with explicit two-path onboarding, shipped `brainpack mcp-server` guidance, and preserved standalone local model commands**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-14T20:46:35Z
- **Completed:** 2026-03-14T20:49:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Rewrote `brainpack.md` so the broader product story now presents `Use with agent` as the recommended path and `Use with local model` as the standalone path.
- Replaced stale query-first, attach-style, and future-server framing in `brainpack-techstack.md` with the shipped same-machine MCP and local-mode story.
- Locked the exact first-run order in both docs so readers see the same onboarding sequence as the CLI surfaces.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite `brainpack.md` around recommended agent usage and standalone local mode** - `77aabfb` (feat)
2. **Task 2: Update `brainpack-techstack.md` to match the shipped local MCP and retrieval-first direction** - `1ed1b2d` (feat)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `brainpack.md` - Reframed the product overview around the two-mode onboarding story and the recommended `brainpack mcp-server` path.
- `brainpack-techstack.md` - Replaced legacy integration roadmap language with current local MCP, local model, and shared build-pipeline guidance.
- `.planning/phases/10-update-agent-and-local-mode-onboarding/10-02-SUMMARY.md` - Recorded plan execution, decisions, and verification results.

## Decisions Made

- Rewrote both docs directly instead of patching isolated sections because the previous narrative was built around a query-first and future-integration story.
- Kept the recommended-path explanation short and command-oriented: Brainpack finds evidence for a same-machine agent, then points readers to `brainpack mcp-server`.
- Documented `query` and `chat` as the valid standalone local path so the new recommendation does not erase the local-answer workflow.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `brainpack.md` and `brainpack-techstack.md` were ignored and untracked in this repository, so each task commit used `git add -f` to stage only the targeted documentation file.
- `requirements mark-complete ONB-01 OCL-02` returned `not_found` because those IDs are not present in the current `REQUIREMENTS.md`; traceability remains recorded in this plan and summary instead of patching a user-dirty planning file out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The broader markdown docs now match the CLI's two-mode onboarding language and no longer pull users back into a query-first mental model.
- Future documentation or packaging work can reuse the same locked first-run order without reintroducing attach-style or remote-MCP guidance.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/10-update-agent-and-local-mode-onboarding/10-02-SUMMARY.md`.
- Task commits `77aabfb` and `1ed1b2d` are present in git history.

---
*Phase: 10-update-agent-and-local-mode-onboarding*
*Completed: 2026-03-14*
