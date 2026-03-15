"""Global Brainpack settings helpers."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SETTINGS_VERSION = 1


def _recommended_transcription_backend() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "mlx-whisper"
    return "faster-whisper"


@dataclass(eq=True)
class BrainpackSettings:
    version: int = SETTINGS_VERSION
    setup_completed: bool = False
    preferred_mode: str = "agent"
    audio_enabled_by_default: bool = True
    preferred_transcription_backend: str = _recommended_transcription_backend()
    preferred_whisper_model: str = "small"
    preferred_local_provider: str = "ollama"


def settings_path() -> Path:
    """Return the machine-level settings file path."""
    return Path.home() / ".brainpacks" / "settings.json"


def _default_settings() -> BrainpackSettings:
    return BrainpackSettings()


def _merge_settings(raw: dict[str, Any]) -> BrainpackSettings:
    defaults = asdict(_default_settings())
    for key in defaults:
        if key in raw:
            defaults[key] = raw[key]
    return BrainpackSettings(**defaults)


def load_settings() -> BrainpackSettings:
    """Load settings.json, merging missing fields onto the current defaults."""
    path = settings_path()
    if not path.exists():
        return _default_settings()

    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return _default_settings()

    if not isinstance(raw, dict):
        return _default_settings()

    return _merge_settings(raw)


def save_settings(settings: BrainpackSettings) -> None:
    """Persist the versioned settings document with atomic replacement."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.stem}-",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    payload = json.dumps(asdict(settings), indent=2, sort_keys=True) + "\n"

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def needs_initial_setup() -> bool:
    """Return True when Brainpack should consider the first-run setup path."""
    return not load_settings().setup_completed

