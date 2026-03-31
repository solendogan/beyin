"""Pack and runtime readiness checks for build and query operations."""
from __future__ import annotations

import os
import shutil
from typing import Optional

from beyin.install_hints import (
    nltk_punkt_tab_install_hint,
    ollama_install_hint,
    yt_dlp_install_hint,
)

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


def _check_nltk_punkt_tab_available() -> bool:
    """Return True when the NLTK punkt_tab tokenizer data is available."""
    try:
        import nltk
    except Exception:
        return False

    try:
        nltk.data.find("tokenizers/punkt_tab/english/")
        return True
    except LookupError:
        return False


def _download_nltk_punkt_tab() -> tuple[bool, str]:
    """Download punkt_tab into the current Python environment if needed."""
    try:
        import nltk
    except Exception as exc:
        return False, f"nltk import failed: {exc}"

    try:
        nltk.data.find("tokenizers/punkt_tab/english/")
        return True, "already installed"
    except LookupError:
        pass

    try:
        downloaded = nltk.download("punkt_tab", quiet=True)
    except Exception as exc:
        return False, str(exc)

    if not downloaded:
        return False, "nltk downloader reported failure"

    try:
        nltk.data.find("tokenizers/punkt_tab/english/")
    except LookupError:
        return False, "punkt_tab still not visible after download"

    return True, "downloaded"


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


def _punkt_tab_build_issue() -> Optional[str]:
    """Return a user-facing punkt_tab issue message when text chunking is blocked."""
    if _check_nltk_punkt_tab_available():
        return None
    return (
        "NLTK sentence tokenizer data 'punkt_tab' is required for builds. "
        f"Install it with: {nltk_punkt_tab_install_hint()}"
    )


def _query_provider_error(provider: str) -> Optional[str]:
    """Return a user-facing readiness error for the selected query provider."""
    if provider == "ollama":
        if _check_ollama_reachable():
            return None
        if shutil.which("ollama"):
            return "Error: Ollama is not running.\nStart it with: ollama serve"
        return f"Error: Ollama is not installed.\nInstall it with: {ollama_install_hint()}"
    if provider == "anthropic":
        return (
            "Error: Anthropic is not supported in this phase.\n"
            "Update pack.yaml to use llm: ollama."
        )
    return (
        f"Error: Unknown LLM provider '{provider}'.\n"
        "Valid option: ollama."
    )
