"""Platform-aware install guidance for external runtime tools."""

from __future__ import annotations

import platform


def _system_name() -> str:
    return platform.system().lower()


def ffmpeg_install_hint() -> str:
    system = _system_name()
    if system == "darwin":
        return "brew install ffmpeg"
    if system == "linux":
        return "sudo apt install ffmpeg"
    if system == "windows":
        return "winget install ffmpeg"
    return "visit https://ffmpeg.org/download.html"


def yt_dlp_install_hint() -> str:
    return "pip install --upgrade yt-dlp"


def ollama_install_hint() -> str:
    system = _system_name()
    if system == "darwin":
        return "brew install ollama"
    if system == "linux":
        return "curl -fsSL https://ollama.com/install.sh | sh"
    return "visit https://ollama.com/download"
