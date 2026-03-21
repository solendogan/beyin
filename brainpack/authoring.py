"""Shared helpers for guided pack authoring flows."""

from __future__ import annotations

from dataclasses import replace

from brainpack.config import PackConfig, SourceEntry
from brainpack.downloader import detect_source_type


def infer_source_intent(source_input: str) -> dict[str, str]:
    """Infer whether a value is content to author from or an existing pack import."""
    source = source_input.strip()
    if not source:
        raise ValueError("Source input cannot be empty.")

    source_type = detect_source_type(source)
    if source_type == "pack":
        return {"kind": "import", "source_type": "pack"}
    if source_type == "local_file":
        raise ValueError(
            "Unsupported local source type. Use a text-like file such as .txt or .md, or a media file such as .mp3 or .mp4."
        )
    normalized_type = "article" if source_type == "local_text" else source_type
    return {"kind": "content", "source_type": normalized_type}


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
        id=name,
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
