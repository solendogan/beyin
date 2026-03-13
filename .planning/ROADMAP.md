# Roadmap: Brainpack

## Overview

Milestone `v1.1` turns Brainpack from a developer-shaped CLI into an onboarding-first product CLI without jumping to a full TUI. The milestone keeps `Typer`, adds a better human-facing command surface, preserves YAML as the interchange format rather than the primary UX, and introduces machine-safe JSON primitives for future OpenClaw and MCP wrappers. Because the `v1.0` audit found correctness gaps that directly undermine UX trust, the first phase closes those inherited blockers before the new flows are layered on top.

## Phases

- [x] **Phase 4: Runtime Correctness Foundation** - Fix provider-aware preflight, canonical source IDs, timestamp citation integrity, and build-time dependency enforcement
- [x] **Phase 5: Pack Inventory and Shared Pack Management** - Add list/status visibility, origin-aware shared pack installation, and pack lifecycle surfaces users can actually understand
- [x] **Phase 6: Guided Creation and Chat UX** - Add default entry routing, guided pack creation, and a `chat`-first query experience
- [x] **Phase 7: Machine-Safe CLI Surface** - Add stable JSON output and machine-oriented command primitives for future OpenClaw/MCP wrappers
- [ ] **Phase 8: Readiness Contract Recovery** - Re-align scoped readiness truth across doctor, inventory, status, query, and chat so query-ready packs are not misreported as blocked
- [ ] **Phase 9: Inventory and Entry Guidance Recovery** - Restore the promised human inventory summary and make the no-arg home screen follow the real next action for installed packs

## Phase Details

### Phase 4: Runtime Correctness Foundation
**Goal**: Close the inherited runtime and state gaps that currently make the CLI misleading or brittle, so later UX work sits on a trustworthy base
**Depends on**: v1.0 implementation snapshot
**Requirements**: PCK-06, QUX-02, QUX-03, RUN-01, RUN-02
**Success Criteria**:
1. Query loads pack configuration before runtime checks and validates only the provider that pack actually uses
2. Audio/transcript artifacts use canonical source identities so resumable builds do not collide across similar URLs
3. Timestamp-capable citations are preserved through build/query integration and appear in results when available
4. `brainpack doctor` uses the same scoped preflight rules as real commands instead of a divergent check path
5. Build enforces `yt-dlp` minimum version at build time, scopes `ffmpeg` to audio work, and removes Deno from current user-facing readiness checks

### Phase 5: Pack Inventory and Shared Pack Management
**Goal**: Make installed packs visible and understandable, and make shared pack installation behave like a product feature instead of a raw file copy
**Depends on**: Phase 4
**Requirements**: ONB-03, PCK-04, PCK-05
**Success Criteria**:
1. User runs `brainpack list` and sees installed packs with status, provider, source count, and recent build/update summary
2. User runs `brainpack status <pack>` and sees lifecycle state, readiness blockers, warnings, and the recommended next action
3. User runs `brainpack add <path-or-url-or-id>` and Brainpack stores the pack origin so future updates do not require manual YAML management

### Phase 6: Guided Creation and Chat UX
**Goal**: Make the default human experience obvious: start Brainpack, create a pack, build it, and chat with it without reading internal docs
**Depends on**: Phase 5
**Requirements**: ONB-01, ONB-02, QUX-01
**Success Criteria**:
1. Running `brainpack` with no subcommand routes the user to a useful next step based on local pack state
2. User can create a new pack through guided CLI input and Brainpack writes the canonical `pack.yaml` for them
3. User can query through `brainpack chat <pack>` in one-shot mode and interactive mode without losing the scriptable one-command path
4. When a pack is unbuilt or blocked, the chat/create flow gives actionable guidance instead of a dead end

### Phase 7: Machine-Safe CLI Surface
**Goal**: Preserve the nicer human UX while also creating stable machine-friendly primitives for future automation and agent integration
**Depends on**: Phase 6
**Requirements**: AUT-01, AUT-02
**Success Criteria**:
1. Human-facing commands support stable `--json` output for list, status, and query/chat results
2. Brainpack exposes a machine-safe command surface with deterministic JSON envelopes and non-ambiguous exit codes
3. Machine-safe commands do not emit human prose or interactive prompts on standard output

### Phase 8: Readiness Contract Recovery
**Goal**: Re-align shared readiness and lifecycle state so build-only blockers do not incorrectly block query-ready packs across doctor, inventory, status, query, and chat
**Depends on**: Phase 7
**Requirements**: RUN-01, PCK-05, QUX-01
**Gap Closure**: Closes v1.1 audit readiness integration and built-audio query-flow gaps
**Success Criteria**:
1. `brainpack doctor` remains the source of operation-scoped readiness truth and shared helpers preserve that distinction for downstream surfaces
2. Inventory and `brainpack status <pack>` stop promoting build-only blockers into generic blocked state for already-built query-ready packs
3. `brainpack chat <pack>` gates on the corrected readiness contract so query-ready packs no longer dead-end behind inventory misclassification
4. The built audio-pack flow stays consistent across `doctor --operation query`, `status`, `query`, and `chat`

### Phase 9: Inventory and Entry Guidance Recovery
**Goal**: Restore the missing human inventory summary and make the default CLI entry surface use real pack next-action guidance instead of a fixed recommendation
**Depends on**: Phase 8
**Requirements**: PCK-04, ONB-01
**Gap Closure**: Closes v1.1 audit inventory-scan and no-arg onboarding-flow gaps
**Success Criteria**:
1. `brainpack list` once again shows the recent build/update summary promised by `PCK-04` while staying compact and scannable
2. The no-arg `brainpack` home screen uses inventory next-action truth for installed packs instead of always recommending `chat`
3. Installed-but-unbuilt or blocked packs receive the correct first-step command from the entry screen
4. Human inventory scan and onboarding flow remain aligned with the same shared inventory summaries

## Progress

**Execution Order:**
Phases execute in numeric order: 4 → 5 → 6 → 7 → 8 → 9

| Phase | Requirements | Status |
|-------|--------------|--------|
| 4. Runtime Correctness Foundation | PCK-06, QUX-02, QUX-03, RUN-01, RUN-02 | Completed |
| 5. Pack Inventory and Shared Pack Management | ONB-03, PCK-04, PCK-05 | Completed |
| 6. Guided Creation and Chat UX | ONB-01, ONB-02, QUX-01 | Completed |
| 7. Machine-Safe CLI Surface | AUT-01, AUT-02 | Completed |
| 8. Readiness Contract Recovery | RUN-01, PCK-05, QUX-01 | Pending |
| 9. Inventory and Entry Guidance Recovery | PCK-04, ONB-01 | Pending |
