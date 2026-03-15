"""Brainpack CLI — build and query commands."""
import json
import os
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

import typer

from brainpack import __version__
from brainpack.authoring import build_new_pack_config
from brainpack.chunker import chunk_text, count_tokens
from brainpack.config import (
    PackConfig,
    SourceEntry,
    _load_config_from_file,
    load_config,
    write_config,
)
from brainpack.interactive import (
    is_interactive_session,
    load_prompt_backend,
    run_authoring_menu as interactive_run_authoring_menu,
    run_create_flow as interactive_run_create_flow,
    run_initial_setup_flow as interactive_run_initial_setup_flow,
    run_settings_flow as interactive_run_settings_flow,
)
from brainpack.inventory import (
    human_guidance_command,
    inspect_pack,
    list_packs,
    load_config_from_source_path,
    load_pack_origin,
    next_action_reason,
    pack_config_hash,
    resolve_pack_origin,
    save_pack_origin,
    serialize_pack_detail,
    serialize_pack_summary,
    summarize_pack_changes,
    utc_now_iso,
)
from brainpack.pack_state import (
    check_model_provenance,
    get_audio_step,
    is_audio_step_done,
    is_processed,
    load_state,
    mark_audio_step,
    mark_failed,
    mark_processed,
    save_state,
)
from brainpack.machine_output import MachineExit, run_machine_command
from brainpack.source_ids import artifact_stem, canonical_source_id
from brainpack.settings import load_settings, needs_initial_setup, resolve_build_defaults

app = typer.Typer(
    help=(
        "Brainpack — use with an agent for evidence retrieval, or run query/chat in local model mode"
    )
)

_PACKS_DIR = Path.home() / ".brainpacks"
_YTDLP_MIN_VERSION = "2025.11.12"


def detect_source_type(url: str) -> str:
    from brainpack.downloader import detect_source_type as _detect_source_type

    return _detect_source_type(url)


def check_deno_available() -> bool:
    from brainpack.downloader import check_deno_available as _check_deno_available

    return _check_deno_available()


def download_audio(*args, **kwargs):
    from brainpack.downloader import download_audio as _download_audio

    return _download_audio(*args, **kwargs)


def download_podcast_audio(*args, **kwargs):
    from brainpack.downloader import download_podcast_audio as _download_podcast_audio

    return _download_podcast_audio(*args, **kwargs)


def list_podcast_episodes(*args, **kwargs):
    from brainpack.downloader import list_podcast_episodes as _list_podcast_episodes

    return _list_podcast_episodes(*args, **kwargs)


def list_youtube_episodes(*args, **kwargs):
    from brainpack.downloader import list_youtube_episodes as _list_youtube_episodes

    return _list_youtube_episodes(*args, **kwargs)


def load_model(*args, **kwargs):
    from brainpack.embedder import load_model as _load_model

    return _load_model(*args, **kwargs)


def fetch_article(*args, **kwargs):
    from brainpack.ingester import fetch_article as _fetch_article

    return _fetch_article(*args, **kwargs)


def load_text_like_source(*args, **kwargs):
    from brainpack.ingester import load_text_like_source as _load_text_like_source

    return _load_text_like_source(*args, **kwargs)


def run_query(*args, **kwargs):
    from brainpack.query import run_query as _run_query

    return _run_query(*args, **kwargs)


def retrieve_evidence(*args, **kwargs):
    from brainpack.query import retrieve_evidence as _retrieve_evidence

    return _retrieve_evidence(*args, **kwargs)


def _source_label(*args, **kwargs):
    from brainpack.query import _source_label as _query_source_label

    return _query_source_label(*args, **kwargs)


def get_collection(*args, **kwargs):
    from brainpack.store import get_collection as _get_collection

    return _get_collection(*args, **kwargs)


def embed_and_store(*args, **kwargs):
    from brainpack.store import embed_and_store as _embed_and_store

    return _embed_and_store(*args, **kwargs)


def transcribe_audio(*args, **kwargs):
    from brainpack.transcriber import transcribe_audio as _transcribe_audio

    return _transcribe_audio(*args, **kwargs)


def _display_status(status: str) -> str:
    """Map internal lifecycle states to cleaner human-facing labels."""
    if status == "new":
        return "needs-build"
    return status


def _render_pack_table(summaries: list[dict], *, limit: Optional[int] = None) -> None:
    """Render the compact pack table used by list and the home screen."""
    rows = summaries if limit is None else summaries[:limit]
    typer.echo(f"{'Pack':<20} {'Status':<12} {'Type':<8} {'Sources':>7}  {'Provider':<8}")
    typer.echo(f"{'-'*20} {'-'*12} {'-'*8} {'-'*7}  {'-'*8}")
    for summary in rows:
        typer.echo(
            f"{summary['name'][:20]:<20} "
            f"{_display_status(summary['status']):<12} "
            f"{summary['type']:<8} "
            f"{summary['source_count']:>7}  "
            f"{summary['provider']:<8}"
        )


def _pack_label(summary: Optional[dict]) -> str:
    if summary and summary.get("name"):
        return str(summary["name"])
    return "<pack>"


def _render_usage_guidance(summary: Optional[dict] = None, *, err: bool = False) -> None:
    """Render the shared human onboarding guidance across home, status, and errors."""
    preferred_mode = load_settings().preferred_mode
    pack_name = _pack_label(summary)
    status = summary.get("status") if summary else None
    lifecycle_command = human_guidance_command(summary) if summary else None
    build_command = f"brainpack build {pack_name}"
    doctor_command = f"brainpack doctor {pack_name}"
    
    def _render_agent_guidance() -> None:
        heading = "Use with agent"
        if preferred_mode != "local":
            heading += " (recommended)"
        typer.echo(heading, err=err)
        typer.echo(
            "  brainpack finds evidence for agents like Codex, Claude Code, or OpenClaw.",
            err=err,
        )
        typer.echo("  1. Connect agent: brainpack mcp-server", err=err)
        typer.echo("  2. Set up pack: brainpack create", err=err)
        typer.echo("     or brainpack add <path-or-url-or-id>", err=err)
        typer.echo(
            "  3. Build: brainpack build <pack>"
            if summary is None
            else f"  3. Build: {build_command}",
            err=err,
        )
        if summary:
            if status == "blocked":
                typer.echo(f"  Current pack unblock step: {lifecycle_command}", err=err)
            elif status in {"new", "needs-build", "error"}:
                typer.echo(f"  Current pack build step: {lifecycle_command}", err=err)
            else:
                typer.echo(f"  Current pack is ready for agent use: {pack_name}", err=err)

    def _render_local_guidance() -> None:
        heading = "Use with local model"
        if preferred_mode == "local":
            heading += " (recommended)"
        typer.echo(heading, err=err)
        typer.echo("  1. Install local runtime (for example Ollama).", err=err)
        typer.echo(
            "  2. Run doctor: brainpack doctor <pack>"
            if summary is None
            else f"  2. Run doctor: {doctor_command}",
            err=err,
        )
        typer.echo("  3. Set up pack: brainpack create", err=err)
        typer.echo("     or brainpack add <path-or-url-or-id>", err=err)
        typer.echo(
            "  4. Build: brainpack build <pack>"
            if summary is None
            else f"  4. Build: {build_command}",
            err=err,
        )
        if summary and status == "ready":
            typer.echo(f'  5. Ask locally: brainpack query {pack_name} "question"', err=err)
            typer.echo(f'     or brainpack chat {pack_name} "question"', err=err)

    renderers = [_render_agent_guidance, _render_local_guidance]
    if preferred_mode == "local":
        renderers = [_render_local_guidance, _render_agent_guidance]

    for index, render in enumerate(renderers):
        if index:
            typer.echo("", err=err)
        render()


def _render_home_screen() -> None:
    """Show the default introductory screen for no-argument CLI entry."""
    summaries = list_packs(_PACKS_DIR, _pack_readiness_details)

    typer.echo(f"Brainpack v{__version__}")
    typer.echo("Turn your favorite content into local queryable packs.")
    typer.echo("")

    if not summaries:
        typer.echo("No packs installed yet.")
        typer.echo("")
        _render_usage_guidance()
        typer.echo("")
        typer.echo("More commands")
        typer.echo("  brainpack list")
        typer.echo("  brainpack help")
        return

    typer.echo("Installed packs")
    _render_pack_table(summaries, limit=6)

    if len(summaries) > 6:
        typer.echo(f"...and {len(summaries) - 6} more")

    typer.echo("")
    primary = summaries[0]["name"]
    _render_usage_guidance(summaries[0])
    typer.echo("")
    typer.echo("Main commands")
    typer.echo(f'  brainpack chat {primary} "question"')
    typer.echo(f"  brainpack status {primary}")
    typer.echo("  brainpack list")
    typer.echo("  brainpack create")
    typer.echo("  brainpack help")


def _run_initial_setup_flow() -> bool:
    """Run the interactive first-run setup and return True when it handled output."""
    return interactive_run_initial_setup_flow(prompt_backend=load_prompt_backend())


def run_authoring_menu() -> bool:
    """Run the TTY-only create/import/manage chooser for no-arg interactive sessions."""
    return interactive_run_authoring_menu(
        packs_dir=_PACKS_DIR,
        prompt_backend=load_prompt_backend(),
        import_handler=add,
    )


def run_create_flow() -> bool:
    """Run the interactive create flow behind the direct `brainpack create` command."""
    return interactive_run_create_flow(
        packs_dir=_PACKS_DIR,
        prompt_backend=load_prompt_backend(),
    )


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Render the home screen when Brainpack runs without a subcommand."""
    if ctx.invoked_subcommand is None:
        if needs_initial_setup() and is_interactive_session():
            if _run_initial_setup_flow():
                return
        if is_interactive_session():
            if run_authoring_menu():
                return
        _render_home_screen()


@app.command(name="settings")
def settings_command() -> None:
    """Edit the global Brainpack defaults used by interactive setup and guidance."""
    if not is_interactive_session():
        typer.echo("Error: `brainpack settings` requires a TTY session.", err=True)
        typer.echo("Run `brainpack settings` from an interactive terminal.", err=True)
        raise typer.Exit(code=1)

    if not interactive_run_settings_flow(prompt_backend=load_prompt_backend()):
        raise typer.Exit(code=1)


@app.command()
def help(
    ctx: typer.Context,
) -> None:
    """Show top-level help using a friendly command alias."""
    typer.echo(ctx.find_root().get_help())


def _check_ollama_reachable() -> bool:
    """Return True if Ollama is listening on localhost:11434, False otherwise."""
    import socket as _socket
    try:
        sock = _socket.create_connection(("localhost", 11434), timeout=2)
        sock.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def _ytdlp_version_ok() -> tuple:
    """Return (True, version_str) if yt-dlp >= _YTDLP_MIN_VERSION, else (False, version_str)."""
    try:
        import yt_dlp.version as _v
        current = _v.__version__
        current_tuple = tuple(int(x) for x in current.split("."))
        min_tuple = tuple(int(x) for x in _YTDLP_MIN_VERSION.split("."))
        return (current_tuple >= min_tuple, current)
    except Exception:
        return (False, "unknown")


def _query_provider_error(provider: str) -> Optional[str]:
    """Return a user-facing readiness error for the selected query provider."""
    if provider == "ollama":
        if _check_ollama_reachable():
            return None
        if shutil.which("ollama"):
            return "Error: Ollama is not running.\nStart it with: ollama serve"
        return (
            "Error: Ollama is not installed.\n"
            "Install: brew install ollama\n"
            "Or: curl -fsSL https://ollama.com/install.sh | sh"
        )
    if provider == "openai":
        if os.environ.get("OPENAI_API_KEY"):
            return None
        return (
            "Error: OPENAI_API_KEY is not set.\n"
            "Set it in your shell environment, then retry."
        )
    if provider == "anthropic":
        return (
            "Error: Anthropic is not supported in this phase.\n"
            "Update pack.yaml to use llm: ollama or llm: openai."
        )
    return (
        f"Error: Unknown LLM provider '{provider}'.\n"
        "Valid options: ollama, openai, anthropic."
    )


def _check_ffmpeg_available() -> bool:
    """Return True when ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def _youtube_build_issue() -> Optional[str]:
    """Return a user-facing yt-dlp issue message when YouTube ingest is blocked."""
    ok, version = _ytdlp_version_ok()
    if ok:
        return None
    if version == "unknown":
        return "yt-dlp is not installed. Install or upgrade with: pip install --upgrade yt-dlp"
    return (
        f"yt-dlp is outdated ({version} < {_YTDLP_MIN_VERSION}). "
        "Upgrade with: pip install --upgrade yt-dlp"
    )


def _transcript_path(transcripts_dir: Path, source_id: str) -> Path:
    return transcripts_dir / f"{artifact_stem(source_id)}.json"


def _legacy_transcript_path(transcripts_dir: Path, episode_url: str) -> Path:
    return transcripts_dir / f"{episode_url.split('/')[-1].split('?')[0]}.txt"


def _candidate_audio_paths(audio_dir: Path, source_id: str, episode: dict) -> list[Path]:
    stem = artifact_stem(source_id)
    candidates = list(audio_dir.glob(f"{stem}.*"))
    legacy_id = episode.get("id") or episode.get("guid", "")
    if legacy_id:
        candidates.extend(audio_dir.glob(f"{legacy_id}.*"))
    url_tail = episode.get("url", "").split("?")[0].split("/")[-1]
    if url_tail:
        candidates.extend(audio_dir.glob(url_tail))
    deduped = []
    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _canonical_audio_path(audio_dir: Path, source_id: str, audio_path: Path) -> Path:
    destination = audio_dir / f"{artifact_stem(source_id)}{audio_path.suffix}"
    if audio_path == destination:
        return audio_path
    destination.parent.mkdir(exist_ok=True)
    audio_path.replace(destination)
    return destination


def _load_transcript_segments(transcript_path: Path, legacy_path: Path) -> list[dict]:
    if transcript_path.exists():
        raw = json.loads(transcript_path.read_text())
        return [segment for segment in raw if segment.get("text", "").strip()]
    if legacy_path.exists():
        text = legacy_path.read_text().strip()
        if text:
            return [{"text": text}]
    return []


def _save_transcript_segments(transcript_path: Path, segments: list[dict]) -> None:
    transcript_path.write_text(json.dumps(segments, indent=2))


def _chunk_transcript_segments(
    segments: list[dict],
    window: int = 5,
    overlap: int = 2,
    max_tokens: int = 256,
) -> tuple[list[str], list[dict]]:
    """Chunk transcript segments while preserving timestamp ranges when available."""
    filtered = [segment for segment in segments if segment.get("text", "").strip()]
    if not filtered:
        return [], []

    step = max(1, window - overlap)
    chunks: list[str] = []
    metadatas: list[dict] = []
    for start_idx in range(0, len(filtered), step):
        window_segments = filtered[start_idx : start_idx + window]
        text = " ".join(segment["text"].strip() for segment in window_segments).strip()
        while window_segments and count_tokens(text) > max_tokens:
            window_segments = window_segments[:-1]
            text = " ".join(segment["text"].strip() for segment in window_segments).strip()
        if not window_segments or not text:
            continue
        metadata: dict[str, float] = {}
        start = window_segments[0].get("start")
        end = window_segments[-1].get("end")
        if start is not None and end is not None:
            metadata["timestamp_start"] = float(start)
            metadata["timestamp_end"] = float(end)
        chunks.append(text)
        metadatas.append(metadata)
    return chunks, metadatas


def _resolve_pack_dir(
    pack: str,
    *,
    missing_next_step: str = "brainpack add <path-or-url-or-id>",
    missing_note: Optional[str] = None,
    machine_command: Optional[str] = None,
) -> Path:
    """Resolve pack name to directory under ~/.brainpacks/."""
    pack_dir = _PACKS_DIR / pack
    if not pack_dir.exists():
        if machine_command:
            details = {"next_action": missing_next_step}
            if missing_note:
                details["note"] = missing_note
            raise MachineExit.precondition(
                "pack_not_found",
                f"Pack '{pack}' is not installed.",
                pack=pack,
                details=details,
            )
        typer.echo(f"Error: Pack '{pack}' is not installed.", err=True)
        typer.echo(f"Next step: {missing_next_step}", err=True)
        if missing_note:
            typer.echo(missing_note, err=True)
        raise typer.Exit(code=1)
    return pack_dir


def _has_audio_sources(config) -> bool:
    return any(detect_source_type(source.url) in {"youtube", "podcast"} for source in config.sources)


def _has_youtube_sources(config) -> bool:
    return any(detect_source_type(source.url) == "youtube" for source in config.sources)


def _pack_readiness_details(config) -> dict[str, list[str]]:
    """Return scoped blocker/warning details for one installed pack."""
    blockers: list[str] = []
    warnings: list[str] = []

    provider_error = _query_provider_error(config.llm)
    if provider_error is not None:
        blockers.append(provider_error)

    if _has_youtube_sources(config):
        youtube_issue = _youtube_build_issue()
        if youtube_issue is not None:
            blockers.append(youtube_issue)

    if _has_audio_sources(config) and not _check_ffmpeg_available():
        blockers.append(
            "ffmpeg is required for audio builds. Install: brew install ffmpeg"
        )

    return {"blockers": blockers, "warnings": warnings}


def _render_next_step(command: str, reason: str, *, err: bool = False) -> None:
    """Print one explicit next command and why it matters."""
    typer.echo(f"Next step: {command}", err=err)
    typer.echo(reason, err=err)


def _split_machine_message(message: str) -> tuple[str, dict[str, str]]:
    """Split a multi-line human error into a machine message plus details."""
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines:
        return message, {}
    if len(lines) == 1:
        return lines[0], {}
    return lines[0], {"hint": " ".join(lines[1:])}


def _load_query_runtime(
    pack: str,
    *,
    machine_command: Optional[str] = None,
) -> tuple[Path, PackConfig, object, object]:
    """Load pack config and retrieval runtime for query/chat surfaces."""
    pack_dir = _resolve_pack_dir(pack, machine_command=machine_command)
    config = load_config(pack_dir)
    provider_error = _query_provider_error(config.llm)
    if provider_error is not None:
        if machine_command:
            message, details = _split_machine_message(provider_error)
            raise MachineExit.precondition(
                "runtime_blocked",
                message,
                pack=pack,
                details=details,
            )
        typer.echo(provider_error, err=True)
        raise typer.Exit(code=1)
    summary = inspect_pack(pack_dir, _pack_readiness_details)
    status = summary["status"]
    if status == "new":
        _raise_retrieval_precondition(
            pack,
            code="pack_not_built",
            message=f"Pack '{pack}' is not built yet.",
            summary=summary,
            machine_command=machine_command,
        )
    if status == "needs-build":
        _raise_retrieval_precondition(
            pack,
            code="pack_needs_build",
            message=(
                f"Pack '{pack}' changed after its last build and needs a rebuild before query can continue."
            ),
            summary=summary,
            machine_command=machine_command,
        )
    if status == "error":
        _raise_retrieval_precondition(
            pack,
            code="pack_build_failed",
            message=f"Pack '{pack}' needs a successful build before query can continue.",
            summary=summary,
            machine_command=machine_command,
        )
    model = load_model(config.embedding_model)
    collection = get_collection(pack_dir, config.name)
    return pack_dir, config, model, collection


def _has_successful_build(state: dict) -> bool:
    if state.get("last_build_at"):
        return True
    processed = state.get("processed", {})
    if any(item.get("status") == "done" for item in processed.values()):
        return True
    audio_steps = state.get("audio_steps", {})
    return any(step.get("stages", {}).get("embedded") for step in audio_steps.values())


def _has_failed_build(state: dict) -> bool:
    return any(item.get("status") == "failed" for item in state.get("processed", {}).values())


def _retrieval_precondition_summary(status: str, pack: str) -> dict:
    next_action = f"brainpack build {pack}"
    return {
        "status": status,
        "next_action": next_action,
        "blockers": [],
        "warnings": [],
    }


def _load_evidence_runtime(
    pack: str,
    *,
    machine_command: Optional[str] = None,
) -> tuple[Path, PackConfig, object, object]:
    """Load retrieval-only runtime without requiring answer-provider readiness."""
    pack_dir = _resolve_pack_dir(pack, machine_command=machine_command)
    config = load_config(pack_dir)
    state = load_state(pack_dir)
    has_build = _has_successful_build(state)
    current_hash = pack_config_hash(pack_dir)
    last_build_hash = state.get("last_built_pack_hash")
    needs_build = bool(has_build and last_build_hash and last_build_hash != current_hash)
    has_error = _has_failed_build(state)

    if has_error:
        _raise_retrieval_precondition(
            pack,
            code="pack_build_failed",
            message=f"Pack '{pack}' needs a successful build before evidence retrieval can continue.",
            summary=_retrieval_precondition_summary("error", pack),
            machine_command=machine_command,
        )
    if not has_build:
        _raise_retrieval_precondition(
            pack,
            code="pack_not_built",
            message=f"Pack '{pack}' is not built yet.",
            summary=_retrieval_precondition_summary("new", pack),
            machine_command=machine_command,
        )
    if needs_build:
        _raise_retrieval_precondition(
            pack,
            code="pack_needs_build",
            message=(
                f"Pack '{pack}' changed after its last build and needs a rebuild before evidence retrieval can continue."
            ),
            summary=_retrieval_precondition_summary("needs-build", pack),
            machine_command=machine_command,
        )
    model = load_model(config.embedding_model)
    collection = get_collection(pack_dir, config.name)
    return pack_dir, config, model, collection


def _raise_retrieval_precondition(
    pack: str,
    code: str,
    message: str,
    summary: dict,
    *,
    machine_command: Optional[str] = None,
    include_blocker: bool = False,
) -> None:
    """Stop retrieval flows with consistent human and machine precondition guidance."""
    details = {
        "next_action": summary["next_action"],
        "reason": next_action_reason(summary),
    }
    if include_blocker and summary.get("blockers"):
        blocker_message, _ = _split_machine_message(summary["blockers"][0])
        details["blocker"] = blocker_message
    if machine_command:
        raise MachineExit.precondition(
            code,
            message,
            pack=pack,
            details=details,
        )
    typer.echo(message, err=True)
    if include_blocker and summary.get("blockers"):
        typer.echo(f"Why: {summary['blockers'][0]}", err=True)
    typer.echo("", err=True)
    _render_usage_guidance(summary, err=True)
    raise typer.Exit(code=1)


def _load_chat_runtime(
    pack: str,
    *,
    machine_command: Optional[str] = None,
) -> tuple[Path, PackConfig, object, object]:
    """Load chat runtime only when the pack exists and is ready for chat."""
    pack_dir = _resolve_pack_dir(
        pack,
        missing_next_step="brainpack create",
        missing_note="Use `brainpack add <path-or-url-or-id>` if you already have a pack.yaml to import.",
        machine_command=machine_command,
    )
    summary = inspect_pack(pack_dir, _pack_readiness_details)
    status = summary["status"]

    if status == "blocked":
        _raise_retrieval_precondition(
            pack,
            "pack_blocked",
            f"Pack '{pack}' is blocked before chat can start.",
            summary,
            machine_command=machine_command,
            include_blocker=True,
        )

    if status == "new":
        _raise_retrieval_precondition(
            pack,
            "pack_not_built",
            f"Pack '{pack}' is not built yet.",
            summary,
            machine_command=machine_command,
        )

    if status == "needs-build":
        _raise_retrieval_precondition(
            pack,
            "pack_needs_build",
            f"Pack '{pack}' changed after its last build and needs a rebuild before chat can continue.",
            summary,
            machine_command=machine_command,
        )

    if status == "error":
        _raise_retrieval_precondition(
            pack,
            "pack_build_failed",
            f"Pack '{pack}' needs a successful build before chat can continue.",
            summary,
            machine_command=machine_command,
        )

    config = summary["config"]
    model = load_model(config.embedding_model)
    collection = get_collection(pack_dir, config.name)
    return pack_dir, config, model, collection


def _render_query_output(result: dict) -> None:
    """Print the LLM answer followed by visible sources."""
    typer.echo(result["answer"])
    if not result["sources"]:
        return

    typer.echo("\nSources:")
    grouped: dict[tuple[str, str], list[dict]] = {}
    ordered_keys: list[tuple[str, str]] = []
    for source in result["sources"]:
        key = (source.get("title", "Unknown"), source.get("url", ""))
        if key not in grouped:
            ordered_keys.append(key)
            grouped[key] = []
        grouped[key].append(source)

    for index, key in enumerate(ordered_keys, start=1):
        title, url = key
        typer.echo(f"  [{index}] {title} — {url}")
        ranges: list[str] = []
        seen_ranges: set[str] = set()
        for source in grouped[key]:
            start = source.get("timestamp_start")
            end = source.get("timestamp_end")
            if start is None or end is None:
                continue
            label = _source_label(
                {
                    "title": title,
                    "url": url,
                    "timestamp_start": start,
                    "timestamp_end": end,
                }
            )
            range_label = label.split("(")[-1].rstrip(")")
            if range_label in seen_ranges:
                continue
            seen_ranges.add(range_label)
            ranges.append(range_label)
        for range_label in ranges:
            typer.echo(f"      - {range_label}")


def _serialize_query_source(source: dict) -> dict:
    """Return the stable public source payload for retrieval JSON output."""
    payload = {
        "url": source.get("url", ""),
        "title": source.get("title", "Unknown"),
    }
    if source.get("timestamp_start") is not None:
        payload["timestamp_start"] = source["timestamp_start"]
    if source.get("timestamp_end") is not None:
        payload["timestamp_end"] = source["timestamp_end"]
    return payload


def _serialize_evidence_item(item: dict) -> dict:
    """Return the stable public evidence payload item."""
    payload = {
        "text": item.get("text", ""),
        "url": item.get("url", ""),
        "title": item.get("title", "Unknown"),
        "rank": item.get("rank"),
    }
    if item.get("distance") is not None:
        payload["distance"] = item["distance"]
    if item.get("timestamp_start") is not None:
        payload["timestamp_start"] = item["timestamp_start"]
    if item.get("timestamp_end") is not None:
        payload["timestamp_end"] = item["timestamp_end"]
    return payload


def _build_retrieval_payload(question: str, result: dict, *, machine: bool = False) -> dict:
    """Normalize retrieval results for shared query/chat payload construction."""
    if not machine:
        sources = result["sources"]
    else:
        sources = [_serialize_query_source(source) for source in result["sources"]]
    return {
        "question": question,
        "answer": result["answer"],
        "sources": sources,
    }


def _build_evidence_payload(question: str, evidence: list[dict], *, machine: bool = False) -> dict:
    """Normalize retrieval evidence for the agent-first MCP contract."""
    if machine:
        items = [_serialize_evidence_item(item) for item in evidence]
    else:
        items = evidence
    return {
        "question": question,
        "evidence": items,
    }


def _query_payload(
    pack: str,
    question: str,
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable result payload for query."""
    _, config, model, collection = _load_query_runtime(
        pack,
        machine_command="query" if machine else None,
    )
    result = run_query(
        question=question,
        collection=collection,
        model=model,
        llm_provider=config.llm,
    )
    return _build_retrieval_payload(question, result, machine=machine)


def _chat_one_shot_payload(
    pack: str,
    question: str,
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable result payload for one-shot chat."""
    _, config, model, collection = _load_chat_runtime(
        pack,
        machine_command="chat" if machine else None,
    )
    result = run_query(
        question=question,
        collection=collection,
        model=model,
        llm_provider=config.llm,
    )
    return _build_retrieval_payload(question, result, machine=machine)


def _evidence_payload(
    pack: str,
    question: str,
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable evidence-only payload for agent retrieval."""
    _, _, model, collection = _load_evidence_runtime(
        pack,
        machine_command="evidence" if machine else None,
    )
    evidence = retrieve_evidence(question=question, collection=collection, model=model)
    return _build_evidence_payload(question, evidence, machine=machine)


def _list_payload(
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable inventory payload for machine-safe list output."""
    packs = list_packs(_PACKS_DIR, _pack_readiness_details)
    if machine:
        return {"packs": [serialize_pack_summary(summary) for summary in packs]}
    return {"packs": packs}


def _status_payload(
    pack: str,
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable inventory payload for machine-safe status output."""
    pack_dir = _resolve_pack_dir(pack, machine_command="status" if machine else None)
    summary = inspect_pack(pack_dir, _pack_readiness_details)
    if machine:
        return {"pack": serialize_pack_detail(summary)}
    return {"pack": summary}


def _doctor_statuses(
    pack: str,
    operation: str = "all",
    *,
    machine: bool = False,
) -> list[dict[str, str]]:
    """Build the reusable doctor/readiness payload."""
    if operation not in {"query", "build", "all"}:
        if machine:
            raise MachineExit.usage(
                "invalid_operation",
                f"Unsupported doctor operation '{operation}'.",
                pack=pack,
                details={"valid_operations": ["query", "build", "all"]},
            )
        typer.echo(
            f"Error: Unsupported doctor operation '{operation}'. "
            "Use query, build, or all.",
            err=True,
        )
        raise typer.Exit(code=1)

    pack_dir = _resolve_pack_dir(pack, machine_command="doctor" if machine else None)
    config = load_config(pack_dir)
    statuses: list[dict[str, str]] = []
    readiness = _pack_readiness_details(config)

    if operation in {"query", "all"}:
        if not readiness["blockers"] or not any(
            blocker.startswith("Error: OPENAI_API_KEY")
            or blocker.startswith("Error: Ollama")
            or blocker.startswith("Error: Anthropic")
            or blocker.startswith("Error: Unknown LLM provider")
            for blocker in readiness["blockers"]
        ):
            statuses.append({"label": "Query readiness", "value": f"ready (provider={config.llm})"})
        else:
            statuses.append({"label": "Query readiness", "value": f"blocked (provider={config.llm})"})
            for blocker in readiness["blockers"]:
                if blocker.startswith("Error:"):
                    statuses.append({"label": "Query detail", "value": blocker})

    if operation in {"build", "all"}:
        if _has_youtube_sources(config):
            youtube_issue = _youtube_build_issue()
            if youtube_issue is None:
                statuses.append({"label": "Build YouTube", "value": "ready"})
            else:
                statuses.append({"label": "Build YouTube", "value": "blocked"})
                statuses.append({"label": "Build YouTube detail", "value": youtube_issue})
        if _has_audio_sources(config):
            if _check_ffmpeg_available():
                statuses.append({"label": "Build audio", "value": "ready"})
            else:
                statuses.append(
                    {
                        "label": "Build audio",
                        "value": "blocked",
                    }
                )
                statuses.append(
                    {
                        "label": "Build audio detail",
                        "value": "ffmpeg is required for audio builds. Install: brew install ffmpeg",
                    }
                )
        if not _has_audio_sources(config):
            statuses.append({"label": "Build audio", "value": "not-needed"})

    return statuses


def _doctor_payload(
    pack: str,
    operation: str = "all",
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable payload for doctor output."""
    return {
        "pack": pack,
        "operation": operation,
        "statuses": _doctor_statuses(pack, operation, machine=machine),
    }


def _origin_display(origin: dict) -> str:
    origin_type = origin.get("type")
    origin_source = origin.get("source")
    if not origin_type or not origin_source:
        return "none"
    return f"{origin_type}: {origin_source}"


def _prompt_create_config() -> PackConfig:
    """Collect the non-TTY fallback guided creation inputs."""
    source_input = typer.prompt("Source URL or local path").strip()
    name = typer.prompt("Pack name").strip()
    if not re.match(r"^[\w.-]+$", name):
        typer.echo(
            f"Error: Pack name '{name}' contains invalid characters. "
            "Only alphanumerics, hyphens, underscores, and dots are allowed.",
            err=True,
        )
        raise typer.Exit(code=1)

    description = typer.prompt("Short description").strip()
    try:
        return build_new_pack_config(
            name=name,
            description=description,
            source_input=source_input,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)


def _write_pack_yaml_from_source(
    resolved: dict[str, str],
    destination: Path,
) -> tuple[Path, object]:
    """Resolve a validated YAML source and write it into the managed pack dir."""
    is_url = resolved["resolved"].startswith(("http://", "https://"))
    tmp_file = None
    try:
        if is_url:
            fd, tmp_file = tempfile.mkstemp(suffix=".yaml")
            os.close(fd)
            try:
                urllib.request.urlretrieve(resolved["resolved"], tmp_file)
            except Exception as exc:
                typer.echo(
                    f"Error: Failed to download {resolved['resolved']}: {exc}",
                    err=True,
                )
                raise typer.Exit(code=1)
            yaml_path = Path(tmp_file)
        else:
            yaml_path = Path(resolved["resolved"]).expanduser().resolve()
            if not yaml_path.exists():
                typer.echo(f"Error: '{resolved['source']}' not found.", err=True)
                raise typer.Exit(code=1)

        try:
            config = _load_config_from_file(yaml_path)
        except Exception as exc:
            typer.echo(f"Error: Invalid pack.yaml: {exc}", err=True)
            raise typer.Exit(code=1)

        if not re.match(r"^[\w.-]+$", config.name):
            typer.echo(
                f"Error: Pack name '{config.name}' contains invalid characters. "
                "Only alphanumerics, hyphens, underscores, and dots are allowed.",
                err=True,
            )
            raise typer.Exit(code=1)

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(yaml_path, destination)
        return yaml_path, config
    finally:
        if tmp_file is not None:
            Path(tmp_file).unlink(missing_ok=True)


@app.command()
def create() -> None:
    """Guide the user through creating a new pack without hand-editing YAML."""
    if is_interactive_session():
        if not run_create_flow():
            raise typer.Exit(code=1)
        return

    config = _prompt_create_config()
    pack_dir = _PACKS_DIR / config.name
    if pack_dir.exists():
        typer.echo(
            f"Error: Pack '{config.name}' already exists.\n"
            f"Choose a new name or run `brainpack update {config.name}`.",
            err=True,
        )
        raise typer.Exit(code=1)

    write_config(config, pack_dir / "pack.yaml")

    typer.echo(f"Created pack '{config.name}'.")
    typer.echo(f"Source saved: {config.sources[0].url}")
    typer.echo("")
    _render_next_step(
        f"brainpack build {config.name}",
        "Build indexes the source into local expert memory.",
    )


@app.command()
def build(
    pack: str = typer.Argument(..., help="Pack name (directory under ~/.brainpacks/)"),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Whisper model size: tiny/base/small/medium/large",
    ),
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Whisper language code (e.g. 'tr' for Turkish). Default: auto-detect",
    ),
):
    """Build or incrementally update a pack from its pack.yaml sources."""
    pack_dir = _resolve_pack_dir(pack)
    config = load_config(pack_dir)
    state = load_state(pack_dir)
    current_pack_hash = pack_config_hash(pack_dir)
    build_defaults = resolve_build_defaults(
        cli_model=model,
        cli_language=language,
        pack_config=config,
    )

    # SAF-01: enforce model provenance before any ChromaDB write
    check_model_provenance(state, config.embedding_model, pack_name=config.name)
    save_state(pack_dir, state)  # persist model registration on first build

    model_size = build_defaults["model"]
    model_obj = load_model(config.embedding_model)
    collection = get_collection(pack_dir, config.name)

    audio_dir = pack_dir / "audio"
    transcripts_dir = pack_dir / "transcripts"
    audio_dir.mkdir(exist_ok=True)
    transcripts_dir.mkdir(exist_ok=True)

    total_new = 0
    source_results: list[dict] = []
    blocked_sources = 0
    youtube_issue = _youtube_build_issue()
    ffmpeg_available = _check_ffmpeg_available()
    for source in config.sources:
        source_url = source.url
        effective_limit = source.limit if source.limit is not None else config.episode_limit
        source_type = detect_source_type(source_url)

        if source_type in {"article", "local_text", "local_file", "pack"}:
            if is_processed(state, source_url):
                typer.echo(f"  [skip] {source_url}")
                source_results.append({"title": source_url[:40], "status": "skipped", "new": 0, "skipped": 0})
                continue

            failure_reason = ""
            if source_type == "article":
                typer.echo(f"  [fetch] {source_url}")
                result = fetch_article(source_url)
                failure_reason = "trafilatura extraction returned None"
                failure_message = f"Could not extract text from {source_url} — skipping"
            elif source_type == "local_text":
                typer.echo(f"  [load] {source_url}")
                try:
                    result = load_text_like_source(source_url)
                except FileNotFoundError:
                    result = None
                    failure_reason = f"missing local source: {source_url}"
                    failure_message = f"Missing local source: {source_url} — skipping"
                except ValueError as exc:
                    result = None
                    failure_reason = str(exc)
                    failure_message = f"{exc} — skipping"
                else:
                    failure_message = ""
            elif source_type == "pack":
                result = None
                failure_reason = "pack config sources belong on brainpack add"
                failure_message = (
                    "Pack config sources belong on `brainpack add <path-or-url-or-id>`, not build sources."
                )
            else:
                result = None
                failure_reason = f"unsupported local source type: {source_url}"
                failure_message = f"Unsupported local source type: {source_url} — skipping"

            if result is None:
                typer.echo(
                    f"  [warn] {failure_message}",
                    err=True,
                )
                mark_failed(state, source_url, reason=failure_reason)
                save_state(pack_dir, state)
                source_results.append({"title": source_url[:40], "status": "failed", "new": 0, "skipped": 0})
                continue

            text, title = result
            chunks = chunk_text(text)
            metadatas = [{"url": source_url, "title": title} for _ in chunks]
            new_count = embed_and_store(collection, model_obj, chunks, metadatas, url=source_url)
            total_new += new_count
            mark_processed(state, source_url, title)
            save_state(pack_dir, state)
            typer.echo(f"  [embed] {title} — {new_count} chunks")
            source_results.append({"title": title, "status": "done", "new": new_count, "skipped": 0})

        else:  # youtube or podcast
            if source_type == "youtube" and youtube_issue:
                typer.echo(f"  [warn] {youtube_issue}", err=True)
                source_results.append({"title": source_url[:40], "status": "blocked", "new": 0, "skipped": 0})
                blocked_sources += 1
                continue
            if not ffmpeg_available:
                typer.echo(
                    "  [warn] ffmpeg is required for audio builds. "
                    "Install: brew install ffmpeg or visit https://ffmpeg.org/download.html",
                    err=True,
                )
                source_results.append({"title": source_url[:40], "status": "blocked", "new": 0, "skipped": 0})
                blocked_sources += 1
                continue
            if source_type == "youtube":
                episodes = list_youtube_episodes(source_url, effective_limit)
            else:  # podcast
                episodes = list_podcast_episodes(source_url, effective_limit)

            if not episodes:
                typer.echo(f"  [warn] No episodes found for {source_url}", err=True)
                continue

            total = len(episodes)
            for idx, episode in enumerate(episodes, start=1):
                episode_url = episode["url"]
                episode_title = episode.get("title", "Unknown")
                source_id = canonical_source_id(episode, source_type=source_type)

                # Skip if fully embedded already
                if is_audio_step_done(state, episode_url, "embedded", source_id=source_id):
                    typer.echo(f"  [skip] {episode_title}")
                    source_results.append({"title": episode_title, "status": "skipped", "new": 0, "skipped": 1})
                    continue

                # Step 1: download
                audio_path = None
                ep_step = get_audio_step(state, episode_url, source_id=source_id)
                if ep_step.get("stages", {}).get("downloaded"):
                    candidates = _candidate_audio_paths(audio_dir, source_id, episode)
                    if candidates:
                        audio_path = candidates[0]
                    if audio_path is None or not audio_path.exists() or audio_path.stat().st_size < 10_000:
                        audio_path = None  # force re-download

                if audio_path is None:
                    typer.echo(f"  [download] {episode_title}")
                    if source_type == "youtube":
                        audio_path = download_audio(episode_url, audio_dir, episode_title)
                    else:
                        audio_path = download_podcast_audio(episode_url, audio_dir, episode_title)

                    if audio_path is None:
                        # Retry once
                        typer.echo(f"  [download] retrying {episode_title}...")
                        if source_type == "youtube":
                            audio_path = download_audio(episode_url, audio_dir, episode_title)
                        else:
                            audio_path = download_podcast_audio(episode_url, audio_dir, episode_title)

                    if audio_path is None:
                        typer.echo(
                            f"  [warn] Download failed for {episode_title} — skipping",
                            err=True,
                        )
                        mark_failed(state, episode_url, "download failed after retry", source_id=source_id)
                        save_state(pack_dir, state)
                        source_results.append({"title": episode_title, "status": "failed", "new": 0, "skipped": 0})
                        continue

                    audio_path = _canonical_audio_path(audio_dir, source_id, audio_path)
                    mark_audio_step(state, episode_url, "downloaded", episode_title, source_id=source_id)
                    save_state(pack_dir, state)

                # Step 2: transcribe
                transcript_path = _transcript_path(transcripts_dir, source_id)
                legacy_transcript_path = _legacy_transcript_path(transcripts_dir, episode_url)
                if is_audio_step_done(state, episode_url, "transcribed", source_id=source_id):
                    segments = _load_transcript_segments(transcript_path, legacy_transcript_path)
                else:
                    typer.echo(f"  [transcribe] Episode {idx}/{total}: {episode_title}")
                    segments = transcribe_audio(audio_path, model_size=model_size, language=language)
                    if not segments:
                        typer.echo(
                            f"  [warn] Transcription failed for {episode_title} — skipping",
                            err=True,
                        )
                        mark_failed(state, episode_url, "transcription returned empty", source_id=source_id)
                        save_state(pack_dir, state)
                        source_results.append({"title": episode_title, "status": "failed", "new": 0, "skipped": 0})
                        continue
                    _save_transcript_segments(transcript_path, segments)
                    mark_audio_step(state, episode_url, "transcribed", source_id=source_id)
                    save_state(pack_dir, state)

                if not segments:
                    typer.echo(
                        f"  [warn] Stored transcript missing for {episode_title} — re-run build",
                        err=True,
                    )
                    source_results.append({"title": episode_title, "status": "failed", "new": 0, "skipped": 0})
                    continue

                # Step 3: chunk + embed
                chunks, range_metadata = _chunk_transcript_segments(segments)
                metadatas = []
                for chunk_range in range_metadata:
                    metadata = {"url": episode_url, "title": episode_title, "source_id": source_id}
                    metadata.update(chunk_range)
                    metadatas.append(metadata)
                new_count = embed_and_store(collection, model_obj, chunks, metadatas, url=source_id)
                total_new += new_count
                mark_audio_step(state, episode_url, "embedded", source_id=source_id)
                save_state(pack_dir, state)
                typer.echo(f"  [embed] {episode_title} — {new_count} chunks")
                source_results.append({"title": episode_title, "status": "done", "new": new_count, "skipped": 0})

    if blocked_sources and total_new == 0:
        typer.echo("\nBuild complete with blocked sources. 0 new chunks indexed.")
    elif total_new == 0:
        typer.echo("\nBuild complete. 0 new chunks — all sources up to date.")
    else:
        typer.echo("\nBuild complete.")
        typer.echo(f"{'Source':<40} {'Status':<10} {'New':>6} {'Skipped':>8}")
        typer.echo(f"{'-'*40} {'-'*10} {'-'*6} {'-'*8}")
        for r in source_results:
            title_col = r["title"][:40]
            typer.echo(f"{title_col:<40} {r['status']:<10} {r['new']:>6} {r['skipped']:>8}")
        typer.echo(f"\nTotal: {total_new} new chunks indexed.")
    had_failures = any(result["status"] in {"failed", "blocked"} for result in source_results)
    if not had_failures:
        state["last_build_at"] = utc_now_iso()
        state["last_built_pack_hash"] = current_pack_hash
        save_state(pack_dir, state)
    if blocked_sources:
        raise typer.Exit(code=1)


@app.command()
def query(
    pack: str = typer.Argument(..., help="Pack name to query in local mode"),
    question: str = typer.Argument(..., help="Question to answer in local mode"),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-safe JSON output.",
    ),
):
    """Query a pack directly in local model mode and receive a cited LLM answer."""
    if json_mode:
        raise typer.Exit(
            code=run_machine_command(
                command="query",
                pack=pack,
                action=lambda: _query_payload(pack, question, machine=True),
            )
        )
    _render_query_output(_query_payload(pack, question))


@app.command()
def chat(
    pack: str = typer.Argument(..., help="Pack name to chat with in local mode"),
    question: Optional[str] = typer.Argument(
        None,
        help="Optional one-shot local-mode question. Omit for interactive chat.",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-safe JSON output.",
    ),
):
    """Chat with a pack in local model mode, one-shot or interactive."""
    if json_mode:
        def _machine_action() -> dict:
            if question is None:
                raise MachineExit.usage(
                    "interactive_json_not_supported",
                    "brainpack chat --json requires a question argument",
                    pack=pack,
                )
            return _chat_one_shot_payload(pack, question, machine=True)

        raise typer.Exit(
            code=run_machine_command(
                command="chat",
                pack=pack,
                action=_machine_action,
            )
        )

    if question is not None:
        _render_query_output(_chat_one_shot_payload(pack, question))
        return

    _, config, model, collection = _load_chat_runtime(pack)

    def _ask(prompt_text: str, history: list[dict[str, str]] | None = None) -> dict:
        return run_query(
            question=prompt_text,
            collection=collection,
            model=model,
            llm_provider=config.llm,
            history=list(history) if history else None,
        )

    typer.echo(f"Chatting with '{pack}'. Type exit or quit to leave.")
    session_history: list[dict[str, str]] = []
    while True:
        prompt_text = typer.prompt("You").strip()
        if prompt_text.lower() in {"exit", "quit"}:
            typer.echo("Bye.")
            return
        if not prompt_text:
            continue
        result = _ask(prompt_text, history=session_history or None)
        _render_query_output(result)
        session_history.append(
            {"question": prompt_text, "answer": result["answer"]}
        )


@app.command(name="check-deps")
def check_deps() -> None:
    """Check current user-facing dependencies: ffmpeg and yt-dlp."""
    failures = []

    # Check ffmpeg
    if shutil.which("ffmpeg"):
        typer.echo("ffmpeg: found")
    else:
        typer.echo(
            "ffmpeg: NOT FOUND\n"
            "  Install: brew install ffmpeg\n"
            "  Or: https://ffmpeg.org/download.html"
        )
        failures.append("ffmpeg")

    # Check yt-dlp version
    ok, version = _ytdlp_version_ok()
    if ok:
        typer.echo(f"yt-dlp: found ({version})")
    else:
        if version == "unknown":
            typer.echo(
                "yt-dlp: NOT FOUND or version unknown\n"
                "  Install/upgrade: pip install --upgrade yt-dlp"
            )
        else:
            typer.echo(
                f"yt-dlp: OUTDATED ({version} < {_YTDLP_MIN_VERSION})\n"
                "  Upgrade: pip install --upgrade yt-dlp"
            )
        failures.append("yt-dlp")

    if failures:
        raise typer.Exit(code=1)


@app.command()
def doctor(
    pack: str = typer.Argument(..., help="Pack name to inspect"),
    operation: str = typer.Option(
        "all",
        "--operation",
        "-o",
        help="Scope readiness to query, build, or all",
    ),
) -> None:
    """Report operation-scoped runtime readiness for a pack."""
    statuses = _doctor_payload(pack, operation)["statuses"]
    for item in statuses:
        label = item["label"]
        value = item["value"]
        typer.echo(f"{label}: {value}")


@app.command(name="list")
def list_command(
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-safe JSON output.",
    ),
) -> None:
    """List installed packs in a compact inventory view."""
    if json_mode:
        raise typer.Exit(
            code=run_machine_command(
                command="list",
                action=lambda: _list_payload(machine=True),
            )
        )

    summaries = _list_payload()["packs"]
    if not summaries:
        typer.echo("No packs installed.")
        return

    _render_pack_table(summaries)


@app.command(name="status")
def status_command(
    pack: str = typer.Argument(..., help="Pack name to inspect"),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-safe JSON output.",
    ),
) -> None:
    """Inspect one installed pack in detail."""
    if json_mode:
        raise typer.Exit(
            code=run_machine_command(
                command="status",
                pack=pack,
                action=lambda: _status_payload(pack, machine=True),
            )
        )

    summary = _status_payload(pack)["pack"]

    typer.echo(f"Pack: {summary['name']}")
    typer.echo(f"Status: {_display_status(summary['status'])}")
    typer.echo(f"Type: {summary['type']}")
    typer.echo(f"Provider: {summary['provider']}")
    typer.echo(f"Sources: {summary['source_count']}")
    typer.echo(f"Origin: {_origin_display(summary.get('origin', {}))}")
    typer.echo(f"Recent: {summary['recent_summary']}")

    if summary.get("blockers"):
        typer.echo("Blockers:")
        for blocker in summary["blockers"]:
            typer.echo(f"  - {blocker}")

    if summary.get("warnings"):
        typer.echo("Warnings:")
        for warning in summary["warnings"]:
            typer.echo(f"  - {warning}")

    last_update_summary = summary.get("last_update_summary", [])
    if last_update_summary:
        typer.echo("Last update summary:")
        for line in last_update_summary:
            typer.echo(f"  - {line}")

    typer.echo("")
    _render_usage_guidance(summary)


@app.command(name="add")
def add(
    source: str = typer.Argument(..., help="Local path or URL to a pack.yaml file"),
):
    """Add a shared pack from a local path, URL, or marketplace-style id."""
    try:
        resolved = resolve_pack_origin(source, _PACKS_DIR)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    destination_config = Path(tempfile.mkdtemp()) / "probe.yaml"
    _, config = _write_pack_yaml_from_source(resolved, destination_config)
    shutil.rmtree(destination_config.parent, ignore_errors=True)

    dest_dir = _PACKS_DIR / config.name
    if dest_dir.exists():
        typer.echo(
            f"Error: Pack '{config.name}' is already installed.\n"
            f"Use `brainpack update {config.name}` to refresh it.",
            err=True,
        )
        raise typer.Exit(code=1)

    dest_dir.mkdir(parents=True)
    _write_pack_yaml_from_source(resolved, dest_dir / "pack.yaml")
    save_pack_origin(
        dest_dir,
        {
            "type": resolved["type"],
            "source": resolved["source"],
            "resolved": resolved["resolved"],
            "added_at": utc_now_iso(),
            "last_updated_at": utc_now_iso(),
            "last_update_summary": ["initial add"],
        },
    )
    typer.echo(
        f"Pack '{config.name}' added to {dest_dir}/\n"
        f"Run `brainpack build {config.name}` to ingest sources."
    )


@app.command(hidden=True)
def install(
    source: str = typer.Argument(..., help="Local path or URL to a pack.yaml file"),
) -> None:
    """Backward-compatible alias for `brainpack add`."""
    add(source)


@app.command()
def update(
    pack: str = typer.Argument(..., help="Pack name to update"),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Whisper model size: tiny/base/small/medium/large",
    ),
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Whisper language code (e.g. 'tr' for Turkish). Default: auto-detect",
    ),
):
    """Fetch new sources and rebuild a pack incrementally."""
    pack_dir = _PACKS_DIR / pack
    if not pack_dir.exists():
        typer.echo(f"Error: Pack '{pack}' not found.", err=True)
        typer.echo(f"Add it first: brainpack add <path-or-url-or-id>", err=True)
        raise typer.Exit(code=1)

    origin = load_pack_origin(pack_dir)
    if origin.get("source"):
        try:
            resolved = resolve_pack_origin(origin["source"], _PACKS_DIR)
        except (FileNotFoundError, KeyError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1)

        current_config = load_config(pack_dir)
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            tmp_yaml = tmp_dir / "incoming.yaml"
            _, incoming_config = _write_pack_yaml_from_source(resolved, tmp_yaml)
            if incoming_config.name != current_config.name:
                typer.echo(
                    f"Error: Incoming pack name '{incoming_config.name}' does not match installed pack '{current_config.name}'.",
                    err=True,
                )
                raise typer.Exit(code=1)
            changes = summarize_pack_changes(current_config, incoming_config)
            if changes:
                typer.echo("Updating pack definition:")
                for line in changes:
                    typer.echo(f"  - {line}")
                shutil.copy2(tmp_yaml, pack_dir / "pack.yaml")
            origin.update(
                {
                    "type": resolved["type"],
                    "source": resolved["source"],
                    "resolved": resolved["resolved"],
                    "last_updated_at": utc_now_iso(),
                    "last_update_summary": changes or ["no config changes"],
                }
            )
            save_pack_origin(pack_dir, origin)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    build(pack=pack, model=model, language=language)


@app.command(name="mcp-server")
def mcp_server_command() -> None:
    """Run Brainpack as a local stdio server for agents on the same machine."""
    from brainpack.mcp_server import run_stdio_server

    run_stdio_server()


if __name__ == "__main__":
    app()
