"""Whisper transcription — mlx-whisper on Apple Silicon, faster-whisper everywhere else."""
import platform
import sys
from pathlib import Path
from typing import Optional


def _is_apple_silicon() -> bool:
    """Return True on Apple Silicon (arm64 + darwin)."""
    return sys.platform == "darwin" and platform.machine() == "arm64"


def transcribe_audio(
    audio_path: Path,
    model_size: str = "small",
    language: Optional[str] = None,
) -> list[dict]:
    """
    Transcribe audio file. Returns list of segment dicts:
    [{"start": float, "end": float, "text": str}, ...]

    Backend selected automatically: mlx-whisper on arm64+darwin, faster-whisper elsewhere.
    Returns [] on any failure — never raises.
    """
    try:
        if _is_apple_silicon():
            return _transcribe_mlx(audio_path, model_size, language)
        return _transcribe_faster(audio_path, model_size, language)
    except Exception:
        return []


def _transcribe_faster(
    audio_path: Path,
    model_size: str,
    language: Optional[str],
) -> list[dict]:
    raise NotImplementedError


def _transcribe_mlx(
    audio_path: Path,
    model_size: str,
    language: Optional[str],
) -> list[dict]:
    raise NotImplementedError
