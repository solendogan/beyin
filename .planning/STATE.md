---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: milestone
current_phase: 11
current_phase_name: add interactive setup settings and guided pack authoring ux
current_plan: 3
status: executing
stopped_at: Completed 11-02-PLAN.md
last_updated: "2026-03-15T01:30:14.846Z"
last_activity: 2026-03-15
progress:
  total_phases: 8
  completed_phases: 6
  total_plans: 26
  completed_plans: 24
  percent: 95
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-13)

**Core value:** Turn trusted creators' content into searchable expert memory — so users stop re-watching and start querying.
**Current focus:** Phase 11 foundations — global settings storage and the TTY-only interactive seam are in place for later setup, settings, and guided authoring flows

## Current Position

Phase: 11 (8 of 8 tracked phases)
Plan: 2 of 4 in current phase
Status: Ready to execute 11-02
Last activity: 2026-03-15 — Completed Phase 11 Plan 01: global settings seam and TTY-only setup foundation

**Current Phase:** 11
**Current Phase Name:** add interactive setup settings and guided pack authoring ux
**Total Phases:** 8
**Current Plan:** 3
**Total Plans in Phase:** 4
**Status:** Ready to execute
**Last Activity:** 2026-03-15
**Last Activity Description:** Completed Phase 11 Plan 01: global settings seam and TTY-only setup foundation
**Progress:** [██████████] 95%

Progress: [█████████░] 93%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: 7 min
- Total execution time: 29 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-core-text-pipeline | 1 | 15 min | 15 min |

**Recent Trend:**
- Last 5 plans: 4, 5, 4, 6, 14 min
- Trend: Short execution cycles with a longer final hardening pass

*Updated after each plan completion*
| Phase 01-core-text-pipeline P03 | 8 | 1 tasks | 2 files |
| Phase 01-core-text-pipeline P02 | 12 | 2 tasks | 4 files |
| Phase 01-core-text-pipeline P04 | 12 | 2 tasks | 4 files |
| Phase 01-core-text-pipeline P05 | 8 | 1 tasks | 2 files |
| Phase 01-core-text-pipeline P06 | 2 | 1 tasks | 2 files |
| Phase 01-core-text-pipeline P07 | 15 | 2 tasks | 2 files |
| Phase 02-audio-ingestion P01 | 6 | 2 tasks | 5 files |
| Phase 02-audio-ingestion P02 | 3 | 2 tasks | 4 files |
| Phase 02-audio-ingestion P03 | 3 | 2 tasks | 2 files |
| Phase 02-audio-ingestion P04 | 2 | 2 tasks | 2 files |
| Phase 03-production-cli P01 | 8 | 2 tasks | 2 files |
| Phase 03-production-cli P02 | 3 | 2 tasks | 3 files |
| Phase 03-production-cli P03 | 4 | 2 tasks | 2 files |
| Phase 06-guided-creation-and-chat-ux P01 | 2 | 2 tasks | 2 files |
| Phase 06-guided-creation-and-chat-ux P02 | 3 | 2 tasks | 3 files |
| Phase 06-guided-creation-and-chat-ux P03 | 7 | 2 tasks | 4 files |
| Phase 06-guided-creation-and-chat-ux P04 | 4 | 2 tasks | 3 files |
| Phase 07-machine-safe-cli-surface P01 | 5 | 2 tasks | 3 files |
| Phase 07-machine-safe-cli-surface P02 | 4 | 2 tasks | 3 files |
| Phase 07-machine-safe-cli-surface P03 | 6 | 2 tasks | 2 files |
| Phase 07-machine-safe-cli-surface P04 | 14 | 2 tasks | 3 files |
| Phase 10-update-agent-and-local-mode-onboarding P01 | 4 | 2 tasks | 4 files |
| Phase 10-update-agent-and-local-mode-onboarding P02 | 2 | 2 tasks | 2 files |
| Phase 11 P01 | 4 | 2 tasks | 8 files |
| Phase 11-add-interactive-setup-settings-and-guided-pack-authoring-ux P02 | 5 | 2 tasks | 6 files |

## Accumulated Context

### Roadmap Evolution

- Phase 9 added: Make Agent Mode retrieval-first
- Reason: MCP proved useful, but the real product value is retrieval/evidence quality for external agents rather than Brainpack's own local final-answer prose
- Decision: Agent Mode is now the recommended default path; Local Mode remains available as the standalone/privacy-focused option
- Phase 11 added: Add interactive setup, settings, and guided pack authoring UX
- Reason: The current onboarding copy is clearer, but the next product gap is guided setup and pack authoring that actually reduces first-run friction for both agent-first and local users without requiring a full TUI rewrite
- Decision: Use lightweight TTY-only interactive prompts for setup/settings/authoring flows, keep non-interactive and machine-safe CLI paths intact, and defer full terminal-app ambitions

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Architecture: Two independent pipelines share only ChromaDB files on disk — ingestion writes, query reads, never call each other at runtime
- Build order: Pack config → pack state → article source → chunker → embedder → ChromaDB → query pipeline → LLM client → transcription → YouTube/podcast sources → CLI wiring (de-risk retrieval first)
- Phase 1 constraint: Model provenance (embedding model name + dimension) must go into meta.json before first ChromaDB write — cannot defer
- 01-01 Bootstrap: uv not pre-installed, installed via curl script; Python 3.11 installed via uv; all 8 prod deps + pytest installed in .venv; 19 xfail stubs pass
- 01-01 Test pattern: xfail(strict=False) stubs count as passing — downstream plans replace with real assertions
- [Phase 01-core-text-pipeline]: ingester.py: Fetch HTML once with fetch_url, call extract twice (text + JSON metadata) — avoids double network round trip
- [Phase 01-core-text-pipeline]: ingester.py: fetch_article returns None (not exception) on any failure — build loop skips bad URLs without crashing
- [Phase 01-core-text-pipeline]: ingester.py: Title falls back to URL string when trafilatura metadata JSON is None or has no title field
- [Phase 01-core-text-pipeline]: 01-02 check_model_provenance mutates state but does NOT call save_state — write responsibility stays in cli.py
- [Phase 01-core-text-pipeline]: 01-02 typer.BadParameter used for model mismatch error — clean CLI integration with remediation message
- [Phase 01-core-text-pipeline]: 01-04: Token guard enforced in chunker.py (not embedder.py) — single responsibility for 256-token limit
- [Phase 01-core-text-pipeline]: 01-04: Per-test mock models used in test_embedder.py instead of conftest mock_model — conftest returns fixed (1,384) shape causing length assertion failures
- [Phase 01-core-text-pipeline]: 01-05: Incremental dedup via collection.get(ids) before add — avoids ChromaDB duplicate-ID error and returns accurate new-chunk count
- [Phase 01-core-text-pipeline]: 01-05: Chunk IDs are deterministic: '{url}::chunk::{i}' — enables O(n) dedup check per source URL across incremental builds
- [Phase 01-core-text-pipeline]: 01-06: Flatten model.encode output with np.flatten().tolist() before ChromaDB query — handles both real SentenceTransformer (1D) and mock (2D) shapes
- [Phase 01-core-text-pipeline]: 01-06: Token cap uses break-on-exceed strategy (drops entire chunk) — preserves chunk integrity over maximizing context fill
- [Phase 01-core-text-pipeline]: 01-06: anthropic raises NotImplementedError with explanation — Anthropic is not OpenAI-compatible, deferred to Phase 3
- [Phase 01-core-text-pipeline]: 01-07: Module-level imports in cli.py (not inside command functions) — required for unittest.mock.patch to intercept at brainpack.cli.* patch paths
- [Phase 01-core-text-pipeline]: 01-07: CliRunner(mix_stderr=False) not supported in typer 0.24.1 (uses click's CliRunner) — removed mix_stderr argument; stderr merged into output in tests
- [Phase 02-audio-ingestion]: 02-01: mlx-whisper added as darwin-conditional dep (sys_platform == 'darwin') to avoid Linux pip build errors
- [Phase 02-audio-ingestion]: 02-01: Stub functions raise NotImplementedError (not return None) — prevents silent incorrect behavior if called before implementation
- [Phase 02-audio-ingestion]: 02-01: _is_apple_silicon extracted as standalone helper for clean patching in tests
- [Phase 02-audio-ingestion]: SourceEntry.limit Optional[int] — None uses global episode_limit; int = per-source override
- [Phase 02-audio-ingestion]: Audio step functions (get/mark/is_audio_step_done) mutate state but do NOT call save_state — write responsibility stays in cli.py
- [Phase 02-audio-ingestion]: 02-03: Lazy imports (yt_dlp, feedparser) inside function bodies prevent ImportError on platforms missing those libs
- [Phase 02-audio-ingestion]: 02-03: sys.modules patching used in tests for lazy imports — patch.dict(sys.modules) not patch('brainpack.downloader.yt_dlp')
- [Phase 02-audio-ingestion]: 02-03: 10KB minimum file size guard in download_audio and download_podcast_audio discards partial files
- [Phase 02-audio-ingestion]: 02-04: Lazy imports (from faster_whisper import WhisperModel, import mlx_whisper) inside function bodies — platform-specific libs not importable on incompatible systems
- [Phase 02-audio-ingestion]: 02-04: sys.modules patching in tests intercepts lazy imports correctly — module-level patch paths don't work for lazy imports
- [Phase 02-audio-ingestion]: 02-04: transcribe_audio catches all exceptions and returns [] — CLI wiring (02-05) treats empty list as failed transcription
- [Phase 03-production-cli]: 03-01: socket.create_connection for Ollama health check (stdlib, 2s timeout, no HTTP parsing)
- [Phase 03-production-cli]: 03-01: shutil at module level in cli.py — required for patch('brainpack.cli.shutil') test patching
- [Phase 03-production-cli]: 03-01: check-deps accumulates all failures before exit 1 — shows all missing deps in one run
- [Phase 03-production-cli]: 03-02: _parse_config_from_raw() extracted as shared helper — avoids duplicating YAML parsing between load_config and _load_config_from_file
- [Phase 03-production-cli]: 03-02: update() does its own pack_dir.exists() check with custom error — _resolve_pack_dir gives misleading mkdir message inappropriate for update context
- [Phase 03-production-cli]: 03-02: install() uses finally block for temp file cleanup — ensures downloaded temp file deleted even if validation or mkdir raises
- [Phase 03-production-cli]: 03-03: [embed] label replaces [chunk]+[done] pair for both article and audio paths — simpler and matches CONTEXT.md spec
- [Phase 03-production-cli]: 03-03: source_results accumulator appended in ALL exit paths (done/skipped/failed) — complete accounting for final table
- [Phase 03-production-cli]: 03-03: total_new == 0 detection drives short message vs table — avoids printing empty table for fully cached builds
- [Phase 04-runtime-correctness-foundation]: query() now loads pack config before provider checks and scopes runtime validation to the selected LLM provider
- [Phase 04-runtime-correctness-foundation]: canonical source IDs drive pack state and audio/transcript artifact stems; legacy URL-keyed state upgrades during load_state()
- [Phase 04-runtime-correctness-foundation]: audio transcripts persist as structured JSON segments and chunk metadata carries timestamp ranges into query output
- [Phase 04-runtime-correctness-foundation]: doctor/build/query share readiness helpers; yt-dlp is enforced at build time, ffmpeg only blocks audio work, and Deno is removed from current user-facing readiness checks
- [Phase 05-pack-inventory-and-shared-pack-management]: `brainpack add` stores exact origin metadata and marketplace-style IDs resolve through a local alias mapping file
- [Phase 05-pack-inventory-and-shared-pack-management]: `brainpack list` and `brainpack status` consume one shared inventory/origin model instead of inventing separate lifecycle truths
- [Phase 05-pack-inventory-and-shared-pack-management]: successful builds now record `last_build_at` and `last_built_pack_hash`, enabling lifecycle and stale/needs-build derivation in inventory surfaces
- [Phase 06-guided-creation-and-chat-ux]: Guided creation defaults new packs to llm: ollama and writes the full canonical schema explicitly.
- [Phase 06-guided-creation-and-chat-ux]: The first-pass wizard accepts exactly one source URL and one source family per run to keep onboarding narrow.
- [Phase 06-guided-creation-and-chat-ux]: Chat reuses the existing run_query retrieval path instead of creating a second RAG flow.
- [Phase 06-guided-creation-and-chat-ux]: Interactive memory stays process-local by passing prior turns into run_query and never writing history to disk.
- [Phase 06-guided-creation-and-chat-ux]: Chat now stops on missing, unbuilt, changed, and blocked pack states before loading model or collection objects.
- [Phase 06-guided-creation-and-chat-ux]: Inventory summaries now carry reusable next-step reasons so home and chat guidance stay aligned.
- [Phase 07-machine-safe-cli-surface]: Machine-safe responses now use one top-level JSON envelope with `ok`, `meta.schema`, and either `data` or `error`.
- [Phase 07-machine-safe-cli-surface]: Covered machine failures map onto a fixed exit taxonomy: usage `2`, precondition `3`, unexpected `4`.
- [Phase 07-machine-safe-cli-surface]: `query`, one-shot `chat`, `list`, and `status` now build structured payloads before rendering, creating one seam for later `--json` rollout.
- [Phase 07-machine-safe-cli-surface]: `list --json` and `status --json` now serialize explicit public inventory fields, keeping raw `config`, `state`, and provenance internals out of the machine contract.
- [Phase 07-machine-safe-cli-surface]: `query --json` and one-shot `chat --json` now share the same retrieval payload shape: `question`, `answer`, and explicit source objects with optional timestamp ranges.
- [Phase 07-machine-safe-cli-surface]: `chat --json` without a question is a usage error envelope, not the start of an interactive machine session.
- [Phase 07-machine-safe-cli-surface]: Chat readiness errors now normalize blocker details to one stable first-line string before entering the machine contract.
- [Phase 07-machine-safe-cli-surface]: Query now blocks new, stale, and failed packs before runtime loading while preserving the existing `runtime_blocked` provider-error contract for machine callers.
- [Phase 07-machine-safe-cli-surface]: Final contract regressions pin one parseable JSON document plus stable top-level success/error keys across `list`, `status`, `query`, and one-shot `chat`.
- [Phase 08-mcp-server-mode]: MCP ships as a local stdio server first, not HTTP, so Codex/Claude/OpenClaw-style agents on the same machine can launch Brainpack directly without service infrastructure.
- [Phase 08-mcp-server-mode]: MCP tools use explicit `brainpack_*` namespacing and reuse machine-safe payload builders instead of scraping CLI prose.
- Product direction: Agent Mode is now the recommended default path; Brainpack should prioritize retrieval/evidence packaging for external agents while keeping local LLM answering as an optional standalone mode.
- [Phase 09-make-agent-mode-retrieval-first]: `retrieve_evidence()` now sits below `run_query()`, so Brainpack can expose raw retrieval evidence without coupling agent mode to LLM generation.
- [Phase 09-make-agent-mode-retrieval-first]: `brainpack_evidence` is the new MCP contract for external agents; it returns evidence only and does not include a Brainpack-generated answer.
- [Phase 09-make-agent-mode-retrieval-first]: evidence-mode readiness is based on pack/index state, not OpenAI key or Ollama reachability.
- [Phase 10-update-agent-and-local-mode-onboarding]: Kept machine-safe next_action stable and introduced a separate human_guidance_command seam for CLI onboarding output.
- [Phase 10-update-agent-and-local-mode-onboarding]: Failed-pack lifecycle classification now resolves to error before new or needs-build so onboarding guidance matches real pack state.
- [Phase 10-update-agent-and-local-mode-onboarding]: Reframed both long-form docs around the same two-path story used by the CLI: Use with agent and Use with local model.
- [Phase 10-update-agent-and-local-mode-onboarding]: Pointed the recommended path to the shipped brainpack mcp-server command instead of legacy attach-style or future-server concepts.
- [Phase 10-update-agent-and-local-mode-onboarding]: Kept query and chat explicitly documented as the standalone local-mode path rather than treating them as deprecated.
- [Phase 11]: Global setup state lives in ~/.brainpacks/settings.json and stays separate from pack.yaml, origin.json, and meta.json. — One machine-level JSON store keeps first-run settings distinct from pack data and matches Brainpack's existing sidecar-state pattern.
- [Phase 11]: The CLI only considers first-run setup on the no-subcommand path when both stdin and stdout are TTYs. — This keeps explicit commands, JSON output, and MCP usage scriptable while still adding an interactive seam for later onboarding work.
- [Phase 11]: InquirerPy stays behind load_prompt_backend() and normalize_prompt_abort() so normal imports, JSON, and MCP paths remain prompt-free. — Lazy prompt loading and one normalized abort seam let later setup/settings flows reuse the adapter without leaking interactive dependencies into non-interactive surfaces.
- [Phase 11-add-interactive-setup-settings-and-guided-pack-authoring-ux]: Initial setup uses the no-arg interactive path exactly once, then defers later edits to brainpack settings.
- [Phase 11-add-interactive-setup-settings-and-guided-pack-authoring-ux]: Setup and settings both end with one applied summary block and one next step: brainpack create.
- [Phase 11-add-interactive-setup-settings-and-guided-pack-authoring-ux]: Saved mode preference only reorders human guidance; JSON and MCP paths keep their existing payload contracts.

### Pending Todos

- `2026-03-13-improve-retrieval-quality-benchmarking.md` — deferred retrieval-quality work: benchmarking, chunking/reranking improvements, multilingual embedding evaluation, and local model-selection follow-up after MCP/OpenClaw priorities.
- `2026-03-13-improve-build-progress-display.md` — replace noisy build logs with stable progress UI for playlists/multi-source packs, including current title, stage, overall progress, and elapsed time.
- `2026-03-13-simplify-guided-pack-creation.md` — make `create` URL-first with source-type auto-detection, optional description, and follow-up consideration for PDF sources.
- `2026-03-14-define-agent-and-local-modes-roadmap.md` — turn the two-mode product direction into actual onboarding, MCP, and retrieval-first work, with Agent Mode as the recommended default.
- `2026-03-14-add-default-agent-answer-format-guidance.md` — add low-priority default answer-style guidance for agent wrappers so Brainpack evidence answers use a consistent structure without per-prompt instructions.
- `2026-03-14-update-agent-and-local-mode-onboarding.md` — align future onboarding/help/docs around Agent Mode as the recommended path and Local Mode as the standalone option.

### Blockers/Concerns

- Milestone audit at `.planning/v1.0-MILESTONE-AUDIT.md` found unresolved v1.0 gaps; milestone was not archived before starting v1.1 planning
- Turkish/multilingual retrieval quality: all-MiniLM-L6-v2 accuracy on Turkish is unquantified — needs a manual 5-question retrieval eval against Armagan's channel before Phase 1 is considered done
- Phase 2 (Audio): yt-dlp Deno dependency is new (2025.11.12) and evolving — API-level VAD differences between mlx-whisper and faster-whisper need verification before implementation

## Session Continuity

Last session: 2026-03-15T01:30:14.844Z
Stopped at: Completed 11-02-PLAN.md
Resume file: None
