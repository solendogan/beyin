"""Pack and runtime readiness checks for build and query operations."""
from __future__ import annotations

import os
import shutil
from typing import Optional

from beyin.install_hints import ollama_install_hint, yt_dlp_install_hint

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


def _check_ffmpeg_available() -> bool:
    """Return True when ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def _youtube_build_issue() -> Optional[str]:
    """Return a user-facing yt-dlp issue message when YouTube ingest is blocked."""
    ok, version = _ytdlp_version_ok()
    if ok:
        return None
    if version == "unknown":
        return f"yt-dlp is not installed. Install or upgrade with: {yt_dlp_install_hint()}"
    return (
        f"yt-dlp is outdated ({version} < {_YTDLP_MIN_VERSION}). "
        f"Upgrade with: {yt_dlp_install_hint()}"
    )


def _has_audio_sources(config) -> bool:
    from beyin.downloader import detect_source_type
    return any(
        detect_source_type(source.url) in {"youtube", "podcast", "local_audio", "local_video"}
        for source in config.sources
    )


def _has_youtube_sources(config) -> bool:
    from beyin.downloader import detect_source_type
    return any(detect_source_type(source.url) == "youtube" for source in config.sources)


def _query_provider_error(provider: str) -> Optional[str]:
    """Return a user-facing readiness error for the selected query provider."""
    if provider == "ollama":
        if _check_ollama_reachable():
            return None
        if shutil.which("ollama"):
            return "Error: Ollama is not running.\nStart it with: ollama serve"
        return f"Error: Ollama is not installed.\nInstall it with: {ollama_install_hint()}"
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
