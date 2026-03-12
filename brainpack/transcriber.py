"""Whisper transcription — mlx-whisper on Apple Silicon, faster-whisper everywhere else."""
import platform
import sys
from pathlib import Path
from typing import Optional


def _is_apple_silicon() -> bool:
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
    Never raises — returns empty list on failure.
    """
    raise NotImplementedError
