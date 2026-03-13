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

from brainpack.chunker import chunk_text, count_tokens
from brainpack.config import load_config, _load_config_from_file, SourceEntry
from brainpack.downloader import (
    check_deno_available,
    detect_source_type,
    download_audio,
    download_podcast_audio,
    list_podcast_episodes,
    list_youtube_episodes,
)
from brainpack.embedder import load_model
from brainpack.ingester import fetch_article
from brainpack.inventory import (
    inspect_pack,
    list_packs,
    load_config_from_source_path,
    load_pack_origin,
    pack_config_hash,
    resolve_pack_origin,
    save_pack_origin,
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
from brainpack.query import _source_label, run_query
from brainpack.source_ids import artifact_stem, canonical_source_id
from brainpack.store import embed_and_store, get_collection
from brainpack.transcriber import transcribe_audio

app = typer.Typer(help="Brainpack — turn creator content into queryable expert memory")

_PACKS_DIR = Path.home() / ".brainpacks"
_YTDLP_MIN_VERSION = "2025.11.12"


def _render_home_screen() -> None:
    """Show the default introductory screen for no-argument CLI entry."""
    summaries = list_packs(_PACKS_DIR, _pack_readiness_details)

    typer.echo("Brainpack")
    typer.echo("Turn creator content into local expert memory.")
    typer.echo("")

    if not summaries:
        typer.echo("No packs installed yet.")
        typer.echo("Start with one clear next step:")
        typer.echo("  brainpack add <path-or-url-or-id>")
        typer.echo("")
        typer.echo("Then continue with:")
        typer.echo("  brainpack build <pack>")
        typer.echo("  brainpack list")
        typer.echo("  brainpack --help")
        return

    typer.echo("Installed packs:")
    for summary in summaries[:5]:
        typer.echo(
            f"  - {summary['name']} [{summary['status']}] "
            f"{summary['source_count']} src, {summary['provider']}"
        )
        typer.echo(f"    next: {summary['next_action']}")

    if len(summaries) > 5:
        typer.echo(f"  ...and {len(summaries) - 5} more")

    primary = summaries[0]["name"]
    typer.echo("")
    typer.echo("Recommended commands:")
    typer.echo(f"  brainpack status {primary}")
    typer.echo(f"  {summaries[0]['next_action']}")
    typer.echo("  brainpack list")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Render the home screen when Brainpack runs without a subcommand."""
    if ctx.invoked_subcommand is None:
        _render_home_screen()


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


def _resolve_pack_dir(pack: str) -> Path:
    """Resolve pack name to directory under ~/.brainpacks/."""
    pack_dir = _PACKS_DIR / pack
    if not pack_dir.exists():
        typer.echo(f"Error: Pack '{pack}' not found at {pack_dir}", err=True)
        typer.echo(
            f"Create the directory and add a pack.yaml, or run: mkdir -p {pack_dir}",
            err=True,
        )
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


def _origin_display(origin: dict) -> str:
    origin_type = origin.get("type")
    origin_source = origin.get("source")
    if not origin_type or not origin_source:
        return "none"
    return f"{origin_type}: {origin_source}"


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
def build(
    pack: str = typer.Argument(..., help="Pack name (directory under ~/.brainpacks/)"),
    model: str = typer.Option(
        "small",
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

    # SAF-01: enforce model provenance before any ChromaDB write
    check_model_provenance(state, config.embedding_model, pack_name=config.name)
    save_state(pack_dir, state)  # persist model registration on first build

    # Rename to avoid collision with `model` parameter (Whisper model string)
    model_size = model
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

        if source_type == "article":
            # Phase 1 path — unchanged
            if is_processed(state, source_url):
                typer.echo(f"  [skip] {source_url}")
                source_results.append({"title": source_url[:40], "status": "skipped", "new": 0, "skipped": 0})
                continue

            typer.echo(f"  [fetch] {source_url}")
            result = fetch_article(source_url)
            if result is None:
                typer.echo(
                    f"  [warn] Could not extract text from {source_url} — skipping",
                    err=True,
                )
                mark_failed(state, source_url, reason="trafilatura extraction returned None")
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
    pack: str = typer.Argument(..., help="Pack name to query"),
    question: str = typer.Argument(..., help="Question to answer"),
):
    """Query a pack and receive a cited LLM answer."""
    pack_dir = _resolve_pack_dir(pack)
    config = load_config(pack_dir)
    provider_error = _query_provider_error(config.llm)
    if provider_error is not None:
        typer.echo(provider_error, err=True)
        raise typer.Exit(code=1)
    model = load_model(config.embedding_model)
    collection = get_collection(pack_dir, config.name)

    result = run_query(
        question=question,
        collection=collection,
        model=model,
        llm_provider=config.llm,
    )

    typer.echo(result["answer"])
    typer.echo("\nSources:")
    for i, source in enumerate(result["sources"], start=1):
        typer.echo(f"  {_source_label(source, index=i)}")


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
    pack_dir = _resolve_pack_dir(pack)
    config = load_config(pack_dir)
    statuses: list[tuple[str, str]] = []
    readiness = _pack_readiness_details(config)

    if operation in {"query", "all"}:
        if not readiness["blockers"] or not any(
            blocker.startswith("Error: OPENAI_API_KEY")
            or blocker.startswith("Error: Ollama")
            or blocker.startswith("Error: Anthropic")
            or blocker.startswith("Error: Unknown LLM provider")
            for blocker in readiness["blockers"]
        ):
            statuses.append(("Query readiness", f"ready (provider={config.llm})"))
        else:
            statuses.append(("Query readiness", f"blocked (provider={config.llm})"))
            for blocker in readiness["blockers"]:
                if blocker.startswith("Error:"):
                    statuses.append(("Query detail", blocker))

    if operation in {"build", "all"}:
        if _has_youtube_sources(config):
            youtube_issue = _youtube_build_issue()
            if youtube_issue is None:
                statuses.append(("Build YouTube", "ready"))
            else:
                statuses.append(("Build YouTube", "blocked"))
                statuses.append(("Build YouTube detail", youtube_issue))
        if _has_audio_sources(config):
            if _check_ffmpeg_available():
                statuses.append(("Build audio", "ready"))
            else:
                statuses.append(("Build audio", "blocked"))
                statuses.append((
                    "Build audio detail",
                    "ffmpeg is required for audio builds. Install: brew install ffmpeg",
                ))
        if not _has_audio_sources(config):
            statuses.append(("Build audio", "not-needed"))

    for label, value in statuses:
        typer.echo(f"{label}: {value}")


@app.command(name="list")
def list_command() -> None:
    """List installed packs in a compact inventory view."""
    summaries = list_packs(_PACKS_DIR, _pack_readiness_details)
    if not summaries:
        typer.echo("No packs installed.")
        return

    typer.echo(f"{'Pack':<20} {'Status':<12} {'Provider':<10} {'Src':>3}  Summary")
    typer.echo(f"{'-'*20} {'-'*12} {'-'*10} {'-'*3}  {'-'*20}")
    for summary in summaries:
        typer.echo(
            f"{summary['name'][:20]:<20} "
            f"{summary['status']:<12} "
            f"{summary['provider']:<10} "
            f"{summary['source_count']:>3}  "
            f"{summary['recent_summary']}"
        )


@app.command(name="status")
def status_command(
    pack: str = typer.Argument(..., help="Pack name to inspect"),
) -> None:
    """Inspect one installed pack in detail."""
    pack_dir = _resolve_pack_dir(pack)
    summary = inspect_pack(pack_dir, _pack_readiness_details)

    typer.echo(f"Pack: {summary['name']}")
    typer.echo(f"Status: {summary['status']}")
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

    typer.echo(f"Next: {summary['next_action']}")


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
    model: str = typer.Option(
        "small",
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


if __name__ == "__main__":
    app()
