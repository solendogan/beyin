"""Global beyin settings helpers."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from beyin.paths import settings_path

SETTINGS_VERSION = 1
_SETUP_PATHS = ["recommended", "custom"]
_CAPABILITY_CHOICES = [
    "web",
    "youtube",
    "podcasts",
    "local_files",
    "local_query",
]
_LOCAL_FILE_TYPE_CHOICES = ["pdf", "docx", "pptx", "xlsx", "epub"]
_WHISPER_MODELS = [
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large",
]
DEFAULT_WHISPER_MODEL = "small"
DEFAULT_LLM_MODEL = "llama3.2"
DEFAULT_CAPABILITIES = ["web", "youtube", "podcasts"]


def _recommended_transcription_backend() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "mlx-whisper"
    return "faster-whisper"


@dataclass(eq=True)
class BeyinSettings:
    version: int = SETTINGS_VERSION
    setup_completed: bool = False
    enabled_capabilities: list[str] = field(default_factory=lambda: list(DEFAULT_CAPABILITIES))
    enabled_local_file_types: list[str] = field(default_factory=list)
    preferred_transcription_backend: str = field(
        default_factory=_recommended_transcription_backend
    )
    preferred_whisper_model: str = DEFAULT_WHISPER_MODEL
    preferred_llm_model: str = DEFAULT_LLM_MODEL


def _default_settings() -> BeyinSettings:
    return BeyinSettings()


def available_setup_choices() -> dict[str, Any]:
    """Return the machine-valid high-level setup choices for interactive flows."""
    recommended = _default_settings()
    backends = [recommended.preferred_transcription_backend]
    if recommended.preferred_transcription_backend != "faster-whisper":
        backends.append("faster-whisper")
    return {
        "setup_paths": list(_SETUP_PATHS),
        "capabilities": list(_CAPABILITY_CHOICES),
        "local_file_types": list(_LOCAL_FILE_TYPE_CHOICES),
        "transcription_backends": backends,
        "whisper_models": list(_WHISPER_MODELS),
        "recommended": {
            "enabled_capabilities": list(recommended.enabled_capabilities),
            "enabled_local_file_types": list(recommended.enabled_local_file_types),
            "preferred_transcription_backend": recommended.preferred_transcription_backend,
            "preferred_whisper_model": recommended.preferred_whisper_model,
            "preferred_llm_model": recommended.preferred_llm_model,
        },
    }


def _merge_settings(raw: dict[str, Any]) -> BeyinSettings:
    defaults = asdict(_default_settings())
    for key in defaults:
        if key in raw:
            defaults[key] = raw[key]
    return BeyinSettings(**defaults)


def load_settings() -> BeyinSettings:
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


def save_settings(settings: BeyinSettings) -> None:
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
    """Return True when beyin should consider the first-run setup path."""
    return not load_settings().setup_completed


def resolve_build_defaults(
    *,
    cli_model: str | None,
    cli_language: str | None,
    global_settings: BeyinSettings | None = None,
) -> dict[str, str | None]:
    """Resolve build-time transcription defaults: CLI flag > global setting."""
    settings = global_settings or load_settings()
    resolved_model = cli_model or settings.preferred_whisper_model or DEFAULT_WHISPER_MODEL
    return {
        "model": resolved_model,
        "language": cli_language,
    }


def describe_settings_summary(settings: BeyinSettings) -> str:
    """Return a compact human summary of the active settings."""
    lines = []
    enabled = set(settings.enabled_capabilities or [])
    if settings.enabled_capabilities:
        capability_map = {
            "web": "Web pages",
            "youtube": "Videos",
            "podcasts": "Podcasts",
            "local_files": "Local files",
            "local_query": "Local answers",
        }
        labels = [
            capability_map.get(value, value)
            for value in settings.enabled_capabilities
        ]
        lines.append("Enabled:")
        lines.extend(f"- {label}" for label in labels)
    if settings.enabled_local_file_types:
        lines.append(
            "Local files: "
            + ", ".join(file_type.upper() for file_type in settings.enabled_local_file_types)
        )
    lines.append(
        "Transcription: "
        f"{settings.preferred_transcription_backend} / {settings.preferred_whisper_model}"
    )
    if "local_query" in enabled:
        lines.append(f"Local model: {settings.preferred_llm_model} via Ollama")
    return "\n".join(lines)
