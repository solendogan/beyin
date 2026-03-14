# Roadmap: Brainpack

## Overview

Milestone `v1.1` turns Brainpack from a developer-shaped CLI into an onboarding-first product CLI without jumping to a full TUI. The milestone keeps `Typer`, adds a better human-facing command surface, preserves YAML as the interchange format rather than the primary UX, and introduces machine-safe JSON primitives for future OpenClaw and MCP wrappers. Because the `v1.0` audit found correctness gaps that directly undermine UX trust, the first phase closes those inherited blockers before the new flows are layered on top. A narrow follow-up Phase 8 then extends those machine-safe seams into a local stdio MCP server for agent clients.

## Phases

- [x] **Phase 4: Runtime Correctness Foundation** - Fix provider-aware preflight, canonical source IDs, timestamp citation integrity, and build-time dependency enforcement
- [x] **Phase 5: Pack Inventory and Shared Pack Management** - Add list/status visibility, origin-aware shared pack installation, and pack lifecycle surfaces users can actually understand
- [x] **Phase 6: Guided Creation and Chat UX** - Add default entry routing, guided pack creation, and a `chat`-first query experience
- [x] **Phase 7: Machine-Safe CLI Surface** - Add stable JSON output and machine-oriented command primitives for future OpenClaw/MCP wrappers
- [x] **Phase 8: MCP Server Mode** - Expose the machine-safe inventory and retrieval surface through a local stdio MCP server for agent clients
- [x] **Phase 9: Make Agent Mode retrieval-first** - Add an evidence-only MCP retrieval path for external agents while keeping the local answer path stable
- [x] **Phase 10: Update agent and local mode onboarding** - Make the two-mode product story visible in first-run CLI/help/docs guidance without breaking machine-safe contracts (completed 2026-03-14)

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

### Phase 8: MCP Server Mode
**Goal**: Expose Brainpack's machine-safe inventory and retrieval surfaces through a local MCP server so agent clients can inspect packs and query them without scraping CLI output
**Depends on**: Phase 7
**Requirements**: OCL-02
**Success Criteria**:
1. Brainpack exposes a local stdio MCP server that agent clients can launch directly from the CLI
2. MCP tools cover the existing high-value lifecycle and retrieval actions: list, status, doctor, add, build, query, and one-shot chat
3. MCP tool responses reuse the machine-safe payload contracts instead of parsing human CLI text
4. MCP tests verify stable tool names, structured success responses, and structured error behavior

### Phase 9: Make Agent Mode retrieval-first
**Goal**: Make Brainpack's agent path retrieval-first by exposing raw evidence over MCP for external synthesis, while keeping the existing local answer path stable
**Depends on**: Phase 8
**Requirements**: OCL-02 (retrieval-first extension)
**Success Criteria**:
1. Brainpack extracts retrieval-only evidence below the current answer path instead of coupling agent retrieval to LLM generation
2. MCP exposes a dedicated `brainpack_evidence` tool that returns question plus evidence items, without a Brainpack-generated answer
3. Evidence retrieval works for built packs without local answer-provider dependencies such as `OPENAI_API_KEY` or Ollama reachability
4. Existing `brainpack_query` and `brainpack_chat` contracts remain stable and regression-tested

### Phase 10: Update agent and local mode onboarding
**Goal**: Align Brainpack's first-run onboarding, CLI help, and supporting docs with the two-mode product story, making `Use with agent` the recommended path while keeping `Use with local model` as the standalone option
**Depends on**: Phase 9
**Requirements**: ONB-01, PCK-05, AUT-01, AUT-02, OCL-02
**Success Criteria**:
1. Running `brainpack` with no subcommand makes the two paths explicit and recommends `Use with agent` for fresh installs
2. Human-facing CLI guidance, including status and retrieval precondition output, uses the same onboarding-aware recommendation seam instead of falling back to query-first or chat-first recovery copy
3. `brainpack --help`, `brainpack help`, `brainpack query --help`, `brainpack chat --help`, and `brainpack mcp-server --help` all reflect the two-mode story consistently
4. Long-form docs match the same mode language and explicit first-run order for both paths
5. Machine-safe list/status/MCP contracts remain stable while human-facing guidance is improved

## Progress

**Execution Order:**
Phases execute in numeric order: 4 → 5 → 6 → 7 → 8 → 9 → 10

| Phase | Requirements | Status |
|-------|--------------|--------|
| 4. Runtime Correctness Foundation | PCK-06, QUX-02, QUX-03, RUN-01, RUN-02 | Completed |
| 5. Pack Inventory and Shared Pack Management | ONB-03, PCK-04, PCK-05 | Completed |
| 6. Guided Creation and Chat UX | ONB-01, ONB-02, QUX-01 | Completed |
| 7. Machine-Safe CLI Surface | AUT-01, AUT-02 | Completed |
| 8. MCP Server Mode | OCL-02 | Completed |
| 9. Make Agent Mode retrieval-first | OCL-02 (retrieval-first extension) | Completed |
| 10. Update agent and local mode onboarding | ONB-01, PCK-05, AUT-01, AUT-02, OCL-02 | Completed |
