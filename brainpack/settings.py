"""Global Brainpack settings helpers."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SETTINGS_VERSION = 1
_PREFERRED_MODES = ["agent", "local", "both"]
_SETUP_PATHS = ["recommended", "custom"]
_LOCAL_PROVIDERS = ["none", "ollama", "openai"]
_WHISPER_MODELS = ["small", "medium", "large"]
DEFAULT_WHISPER_MODEL = "small"


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
    audio_enabled_by_default: bool = False
    preferred_transcription_backend: str = field(
        default_factory=_recommended_transcription_backend
    )
    preferred_whisper_model: str = DEFAULT_WHISPER_MODEL
    preferred_local_provider: str = "none"


def settings_path() -> Path:
    """Return the machine-level settings file path."""
    return Path.home() / ".brainpacks" / "settings.json"


def _default_settings() -> BrainpackSettings:
    return BrainpackSettings()


def available_setup_choices() -> dict[str, Any]:
    """Return the machine-valid high-level setup choices for interactive flows."""
    recommended = _default_settings()
    backends = [recommended.preferred_transcription_backend]
    if recommended.preferred_transcription_backend != "faster-whisper":
        backends.append("faster-whisper")
    return {
        "setup_paths": list(_SETUP_PATHS),
        "preferred_modes": list(_PREFERRED_MODES),
        "transcription_backends": backends,
        "whisper_models": list(_WHISPER_MODELS),
        "local_providers": list(_LOCAL_PROVIDERS),
        "recommended": {
            "preferred_mode": recommended.preferred_mode,
            "audio_enabled_by_default": recommended.audio_enabled_by_default,
            "preferred_transcription_backend": recommended.preferred_transcription_backend,
            "preferred_whisper_model": recommended.preferred_whisper_model,
            "preferred_local_provider": recommended.preferred_local_provider,
        },
    }


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


def resolve_build_defaults(
    *,
    cli_model: str | None,
    cli_language: str | None,
    pack_config: Any,
    global_settings: BrainpackSettings | None = None,
) -> dict[str, str | None]:
    """Resolve build-time transcription defaults with one precedence order."""
    settings = global_settings or load_settings()
    pack_model = getattr(pack_config, "whisper_model", None)
    pack_model_explicit = getattr(
        pack_config,
        "whisper_model_explicit",
        bool(pack_model),
    )

    resolved_model = cli_model
    if not resolved_model and pack_model_explicit and pack_model:
        resolved_model = pack_model
    if not resolved_model:
        resolved_model = settings.preferred_whisper_model or DEFAULT_WHISPER_MODEL

    return {
        "model": resolved_model,
        "language": cli_language,
    }


def describe_settings_summary(settings: BrainpackSettings) -> str:
    """Return a compact human summary of the active settings."""
    mode_labels = {
        "agent": "Use with agent",
        "local": "Use with local model",
        "both": "Use with agent and local model",
    }
    provider_labels = {
        "none": "skip for now",
        "ollama": "ollama",
        "openai": "openai",
    }
    audio_label = "enabled" if settings.audio_enabled_by_default else "off for now"
    lines = [
        f"Mode: {mode_labels.get(settings.preferred_mode, settings.preferred_mode)}",
    ]
    if settings.preferred_mode in {"agent", "both"}:
        lines.append("Agent mode: ready")
    lines.append(
        f"Audio/video defaults: {audio_label}",
    )
    if settings.audio_enabled_by_default:
        lines.append(
            "Transcription: "
            f"{settings.preferred_transcription_backend} / {settings.preferred_whisper_model}"
        )
    else:
        lines.append("Transcription: configure when you enable audio/video")
    lines.append(
        "Local answers: "
        f"{provider_labels.get(settings.preferred_local_provider, settings.preferred_local_provider)}"
    )
    return "\n".join(lines)
