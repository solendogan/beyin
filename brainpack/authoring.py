"""Shared helpers for guided pack authoring flows."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from brainpack.config import PackConfig, SourceEntry
from brainpack.downloader import detect_source_type

_PACK_CONFIG_SUFFIXES = {".yaml", ".yml"}
_TEXT_LIKE_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".html",
    ".htm",
}


def infer_source_intent(source_input: str) -> dict[str, str]:
    """Infer whether a value is content to author from or an existing pack import."""
    source = source_input.strip()
    if not source:
        raise ValueError("Source input cannot be empty.")

    lowered = source.lower()
    if source.startswith(("http://", "https://")):
        if lowered.endswith(tuple(_PACK_CONFIG_SUFFIXES)) or "/pack.yaml" in lowered or "/pack.yml" in lowered:
            return {"kind": "import", "source_type": "pack"}
        return {"kind": "content", "source_type": detect_source_type(source)}

    candidate = Path(source).expanduser()
    suffix = candidate.suffix.lower()
    if candidate.name.lower() in {"pack.yaml", "pack.yml"} or suffix in _PACK_CONFIG_SUFFIXES:
        return {"kind": "import", "source_type": "pack"}
    if suffix in _TEXT_LIKE_SUFFIXES or (candidate.exists() and candidate.is_file()):
        return {"kind": "content", "source_type": "article"}
    return {"kind": "content", "source_type": detect_source_type(source)}


def build_new_pack_config(
    *,
    name: str,
    description: str,
    source_input: str,
    llm: str = "ollama",
) -> PackConfig:
    """Build a new pack config from one inferred authoring source."""
    intent = infer_source_intent(source_input)
    if intent["kind"] != "content":
        raise ValueError(
            "Existing pack imports belong on `brainpack add <path-or-url-or-id>`, not `brainpack create`."
        )
    return PackConfig(
        name=name,
        description=description,
        llm=llm,
        sources=[SourceEntry(url=source_input.strip())],
    )


def add_source_to_pack(config: PackConfig, source_input: str) -> PackConfig:
    """Append one authored content source to an existing pack config."""
    intent = infer_source_intent(source_input)
    if intent["kind"] != "content":
        raise ValueError(
            "Adding an existing pack belongs on `brainpack add <path-or-url-or-id>`, not manage pack."
        )
    source = source_input.strip()
    if any(existing.url == source for existing in config.sources):
        return config
    return replace(
        config,
        sources=[*config.sources, SourceEntry(url=source)],
    )


def update_pack_metadata(
    config: PackConfig,
    *,
    description: str | None = None,
) -> PackConfig:
    """Return a config copy with updated basic metadata."""
    return replace(
        config,
        description=config.description if description is None else description,
    )
