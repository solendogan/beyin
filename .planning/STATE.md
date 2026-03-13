---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: milestone
current_phase: 7
current_phase_name: machine-safe-cli-surface
current_plan: 3
status: in_progress
stopped_at: Completed 07-03-PLAN.md
last_updated: "2026-03-13T14:10:23Z"
last_activity: 2026-03-13
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 16
  completed_plans: 15
  percent: 94
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-13)

**Core value:** Turn trusted creators' content into searchable expert memory — so users stop re-watching and start querying.
**Current focus:** Phase 7 execution — machine-safe CLI surface

## Current Position

Phase: 7 (4 of 4 planned in v1.1)
Plan: 3 of 4 in current phase
Status: Phase in progress — 07-03 completed
Last activity: 2026-03-13 — Completed 07-03 retrieval JSON surfaces

**Current Phase:** 7
**Current Phase Name:** machine-safe-cli-surface
**Total Phases:** 4
**Current Plan:** 3
**Total Plans in Phase:** 4
**Status:** Phase in progress — 07-03 completed
**Last Activity:** 2026-03-13
**Last Activity Description:** Completed 07-03 retrieval JSON surfaces
**Progress:** [█████████▍] 94%

Progress: [█████████▍] 94%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 5 min
- Total execution time: 15 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-core-text-pipeline | 1 | 15 min | 15 min |

**Recent Trend:**
- Last 5 plans: 3, 7, 4, 5, 6 min
- Trend: Stable short execution cycles

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

## Accumulated Context

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

### Pending Todos

None yet.

### Blockers/Concerns

- Milestone audit at `.planning/v1.0-MILESTONE-AUDIT.md` found unresolved v1.0 gaps; milestone was not archived before starting v1.1 planning
- Turkish/multilingual retrieval quality: all-MiniLM-L6-v2 accuracy on Turkish is unquantified — needs a manual 5-question retrieval eval against Armagan's channel before Phase 1 is considered done
- Phase 2 (Audio): yt-dlp Deno dependency is new (2025.11.12) and evolving — API-level VAD differences between mlx-whisper and faster-whisper need verification before implementation

## Session Continuity

Last session: 2026-03-13T14:10:23Z
Stopped at: Completed 07-03-PLAN.md
Resume file: None
