# Requirements: Brainpack

**Defined:** 2026-03-13
**Core Value:** Turn trusted creators' content into searchable expert memory — so users stop re-watching and start querying.

## v1.1 Requirements

### Onboarding

- [x] **ONB-01**: User can run `brainpack` with no subcommand and receive a useful next-step flow based on local state
- [x] **ONB-02**: User can create a new pack through guided CLI input without manually authoring `pack.yaml`
- [x] **ONB-03**: User can add a shared pack from a local path, URL, or marketplace-ready identifier and Brainpack stores its origin for later updates

### Pack Management

- [x] **PCK-04**: User can list installed packs with status, provider, source count, and last build/update summary
- [x] **PCK-05**: User can inspect one pack and see lifecycle state, readiness blockers, and recommended next action
- [x] **PCK-06**: Local pack state uses canonical source IDs and stable artifact paths so resumable builds do not collide across sources

### Query UX

- [x] **QUX-01**: User can query a pack through `brainpack chat <pack>` in either interactive or one-shot form
- [x] **QUX-02**: Query readiness checks load pack config first and validate only the provider that pack actually uses
- [x] **QUX-03**: Query/build integration preserves timestamp-capable citations where available and surfaces them in results

### Runtime & Automation

- [x] **RUN-01**: `brainpack doctor` reports scoped dependency/runtime readiness using the same checks the real commands use
- [x] **RUN-02**: Build enforces `yt-dlp` minimum version at build time, scopes `ffmpeg` to audio work, and removes Deno from current user-facing readiness checks for now
- [ ] **AUT-01**: Human-facing commands support stable `--json` output for list, status, and query/chat results
- [ ] **AUT-02**: Brainpack exposes a machine-safe command surface with stable JSON envelopes and exit codes for future OpenClaw/MCP wrappers

## vNext Requirements

### Community & Ecosystem

- **COM-01**: Community pack registry and search/install UX
- **COM-02**: Cross-pack querying

### OpenClaw Integration

- **OCL-01**: ClawHub skill for Brainpack command usage
- **OCL-02**: MCP server mode
- **OCL-03**: ContextEngine plugin integration

### UI Layers

- **UI-01**: `textual` terminal UI
- **UI-02**: Web UI

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full `textual` TUI in v1.1 | Command semantics and service boundaries need to stabilize first |
| Web UI in v1.1 | CLI foundation is the current priority |
| Hosted marketplace data | Local-first/legal constraints remain non-negotiable |
| Automatic background sync or daemons | Increases hidden state and user confusion before core UX is stable |
| Cross-pack search/chat in v1.1 | Single-pack onboarding and readiness must be solved first |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ONB-01 | Phase 6 | Complete |
| ONB-02 | Phase 6 | Complete |
| ONB-03 | Phase 5 | Completed |
| PCK-04 | Phase 5 | Completed |
| PCK-05 | Phase 5 | Completed |
| PCK-06 | Phase 4 | Completed |
| QUX-01 | Phase 6 | Complete |
| QUX-02 | Phase 4 | Completed |
| QUX-03 | Phase 4 | Completed |
| RUN-01 | Phase 4 | Completed |
| RUN-02 | Phase 4 | Completed |
| AUT-01 | Phase 7 | Pending |
| AUT-02 | Phase 7 | Pending |

**Coverage:**
- v1.1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-14 after removing deferred gap-closure phases from the active roadmap*
