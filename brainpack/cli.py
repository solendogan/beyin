"""Brainpack CLI — build and query commands."""
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

import typer

from brainpack.chunker import chunk_text
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
from brainpack.query import run_query
from brainpack.store import embed_and_store, get_collection
from brainpack.transcriber import transcribe_audio

app = typer.Typer(help="Brainpack — turn creator content into queryable expert memory")

_PACKS_DIR = Path.home() / ".brainpacks"
_YTDLP_MIN_VERSION = "2025.11.12"


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
    for source in config.sources:
        source_url = source.url
        effective_limit = source.limit if source.limit is not None else config.episode_limit
        source_type = detect_source_type(source_url)

        if source_type == "article":
            # Phase 1 path — unchanged
            if is_processed(state, source_url):
                typer.echo(f"  [skip] {source_url}")
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
                continue

            text, title = result
            typer.echo(f"  [chunk] {title}")
            chunks = chunk_text(text)
            metadatas = [{"url": source_url, "title": title} for _ in chunks]
            new_count = embed_and_store(collection, model_obj, chunks, metadatas, url=source_url)
            total_new += new_count
            mark_processed(state, source_url, title)
            save_state(pack_dir, state)
            typer.echo(f"  [done]  {title} — {new_count} new chunks")

        else:  # youtube or podcast
            if source_type == "youtube":
                if not check_deno_available():
                    typer.echo(
                        "  [warn] Deno not found — YouTube format availability may be degraded. "
                        "Install: https://deno.com/manual/getting_started/installation",
                        err=True,
                    )
                episodes = list_youtube_episodes(source_url, effective_limit)
            else:  # podcast
                episodes = list_podcast_episodes(source_url, effective_limit)

            if not episodes:
                typer.echo(f"  [warn] No episodes found for {source_url}", err=True)
                continue

            for episode in episodes:
                episode_url = episode["url"]
                episode_title = episode.get("title", "Unknown")

                # Skip if fully embedded already
                if is_audio_step_done(state, episode_url, "embedded"):
                    typer.echo(f"  [skip] {episode_title}")
                    continue

                # Step 1: download
                audio_path = None
                ep_step = get_audio_step(state, episode_url)
                if ep_step.get("downloaded"):
                    # Find existing audio file by scanning audio_dir
                    ep_id = episode.get("id") or episode.get("guid", "")
                    candidates = list(audio_dir.glob(f"{ep_id}.*")) if ep_id else []
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
                        mark_failed(state, episode_url, "download failed after retry")
                        save_state(pack_dir, state)
                        continue

                    mark_audio_step(state, episode_url, "downloaded", episode_title)
                    save_state(pack_dir, state)

                # Step 2: transcribe
                transcript_path = (
                    transcripts_dir
                    / f"{episode_url.split('/')[-1].split('?')[0]}.txt"
                )
                segments = None

                if is_audio_step_done(state, episode_url, "transcribed") and transcript_path.exists():
                    # Load existing transcript as single segment (no timestamps on reload)
                    text = transcript_path.read_text()
                    segments = [{"start": 0.0, "end": 0.0, "text": text}]
                else:
                    typer.echo(f"  [transcribe] {episode_title}")
                    segments = transcribe_audio(audio_path, model_size=model_size, language=language)
                    if not segments:
                        typer.echo(
                            f"  [warn] Transcription failed for {episode_title} — skipping",
                            err=True,
                        )
                        mark_failed(state, episode_url, "transcription returned empty")
                        save_state(pack_dir, state)
                        continue
                    transcript_path.write_text("\n".join(s["text"] for s in segments))
                    mark_audio_step(state, episode_url, "transcribed")
                    save_state(pack_dir, state)

                # Step 3: chunk + embed
                typer.echo(f"  [chunk] {episode_title}")
                full_text = "\n".join(s["text"] for s in segments)
                chunks = chunk_text(full_text)
                metadatas = [{"url": episode_url, "title": episode_title} for _ in chunks]
                new_count = embed_and_store(collection, model_obj, chunks, metadatas, url=episode_url)
                total_new += new_count
                mark_audio_step(state, episode_url, "embedded")
                save_state(pack_dir, state)
                typer.echo(f"  [done]  {episode_title} — {new_count} new chunks")

    typer.echo(f"\nBuild complete. {total_new} new chunks indexed.")


@app.command()
def query(
    pack: str = typer.Argument(..., help="Pack name to query"),
    question: str = typer.Argument(..., help="Question to answer"),
):
    """Query a pack and receive a cited LLM answer."""
    if not _check_ollama_reachable():
        if shutil.which("ollama"):
            typer.echo("Error: Ollama is not running.", err=True)
            typer.echo("Start it with: ollama serve", err=True)
        else:
            typer.echo("Error: Ollama is not installed.", err=True)
            typer.echo("Install: brew install ollama", err=True)
            typer.echo("Or: curl -fsSL https://ollama.com/install.sh | sh", err=True)
        raise typer.Exit(code=1)
    pack_dir = _resolve_pack_dir(pack)
    config = load_config(pack_dir)
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
        title = source.get("title", "Unknown")
        url = source.get("url", "")
        typer.echo(f"  [{i}] {title} — {url}")


@app.command(name="check-deps")
def check_deps() -> None:
    """Check non-pip dependencies: ffmpeg, deno, yt-dlp."""
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

    # Check deno
    if shutil.which("deno"):
        typer.echo("Deno: found")
    else:
        typer.echo(
            "Deno: NOT FOUND\n"
            "  Install: curl -fsSL https://deno.land/install.sh | sh\n"
            "  Or: brew install deno"
        )
        failures.append("deno")

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
def install(
    source: str = typer.Argument(..., help="Local path or URL to a pack.yaml file"),
):
    """Install a pack from a local or remote pack.yaml."""
    is_url = source.startswith("http://") or source.startswith("https://")
    tmp_file = None

    try:
        if is_url:
            # Download to a temp file first
            fd, tmp_file = tempfile.mkstemp(suffix=".yaml")
            import os
            os.close(fd)
            try:
                urllib.request.urlretrieve(source, tmp_file)
            except Exception as e:
                typer.echo(f"Error: Failed to download {source}: {e}", err=True)
                raise typer.Exit(code=1)
            yaml_path = Path(tmp_file)
        else:
            yaml_path = Path(source).expanduser().resolve()
            if not yaml_path.exists():
                typer.echo(f"Error: '{source}' not found.", err=True)
                raise typer.Exit(code=1)

        # Validate the pack.yaml
        try:
            config = _load_config_from_file(yaml_path)
        except Exception as e:
            typer.echo(f"Error: Invalid pack.yaml: {e}", err=True)
            raise typer.Exit(code=1)

        # Validate pack name
        if not re.match(r'^[\w.-]+$', config.name):
            typer.echo(
                f"Error: Pack name '{config.name}' contains invalid characters. "
                "Only alphanumerics, hyphens, underscores, and dots are allowed.",
                err=True,
            )
            raise typer.Exit(code=1)

        # Check if already installed
        dest_dir = _PACKS_DIR / config.name
        if dest_dir.exists():
            typer.echo(
                f"Error: Pack '{config.name}' is already installed.\n"
                f"Use `brainpack update {config.name}` to update.",
                err=True,
            )
            raise typer.Exit(code=1)

        # Install
        dest_dir.mkdir(parents=True)
        shutil.copy2(yaml_path, dest_dir / "pack.yaml")
        typer.echo(
            f"Pack '{config.name}' installed to {dest_dir}/\n"
            f"Run `brainpack build {config.name}` to ingest sources."
        )

    finally:
        if tmp_file is not None:
            try:
                Path(tmp_file).unlink(missing_ok=True)
            except Exception:
                pass


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
        typer.echo(f"Install it first: brainpack install <path-or-url>", err=True)
        raise typer.Exit(code=1)
    build(pack=pack, model=model, language=language)


if __name__ == "__main__":
    app()
