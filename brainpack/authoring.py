"""Shared helpers for guided pack authoring flows."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from brainpack.config import PackConfig, SourceEntry
from brainpack.downloader import detect_source_type, expand_playlist_sources


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
    source = source_input.strip()
    expanded = expand_playlist_sources(source)
    sources = (
        [SourceEntry(url=ep["url"], title=ep.get("title")) for ep in expanded]
        if expanded
        else [SourceEntry(url=source)]
    )
    return PackConfig(
        id=name,
        name=name,
        description=description,
        llm=llm,
        sources=sources,
    )


def add_source_to_pack(config: PackConfig, source_input: str) -> PackConfig:
    """Append one authored content source to an existing pack config.

    If source_input is a YouTube playlist or RSS feed, expands it into
    individual titled sources instead of storing the playlist URL.
    """
    intent = infer_source_intent(source_input)
    if intent["kind"] != "content":
        raise ValueError(
            "Adding an existing pack belongs on `brainpack add <path-or-url-or-id>`, not manage pack."
        )
    source = source_input.strip()
    existing_urls = {e.url for e in config.sources}

    expanded = expand_playlist_sources(source)
    if expanded:
        new_entries = [
            SourceEntry(url=ep["url"], title=ep.get("title"))
            for ep in expanded
            if ep.get("url") and ep["url"] not in existing_urls
        ]
        if not new_entries:
            return config
        return replace(config, sources=[*config.sources, *new_entries])

    if source in existing_urls:
        return config
    return replace(config, sources=[*config.sources, SourceEntry(url=source)])


def remove_sources_from_pack(
    config: PackConfig,
    selectors: list[str],
    *,
    source_rows: list[dict[str, Any]] | None = None,
) -> tuple[PackConfig, list[dict[str, Any]]]:
    """Remove one or more sources from a pack by current index or text match."""
    rows = source_rows or [
        {
            "index": i,
            "source": source.url,
            "url": source.url,
            "title": source.title or source.url,
            "type": detect_source_type(source.url),
            "status": "pending",
        }
        for i, source in enumerate(config.sources, start=1)
    ]

    if not selectors:
        raise ValueError("Provide at least one source selector to remove.")

    matched_indexes: list[int] = []
    matched_lookup: set[int] = set()

    for raw_selector in selectors:
        selector = raw_selector.strip()
        if not selector:
            continue

        row = _match_source_selector(rows, selector)
        row_index = int(row["index"])
        if row_index not in matched_lookup:
            matched_indexes.append(row_index)
            matched_lookup.add(row_index)

    if not matched_indexes:
        raise ValueError("No sources matched the provided selectors.")

    removed_rows = [row for row in rows if int(row["index"]) in matched_lookup]
    updated_sources = [
        source
        for i, source in enumerate(config.sources, start=1)
        if i not in matched_lookup
    ]
    return replace(config, sources=updated_sources), removed_rows


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


def _match_source_selector(rows: list[dict[str, Any]], selector: str) -> dict[str, Any]:
    if selector.isdigit():
        idx = int(selector)
        for row in rows:
            if int(row["index"]) == idx:
                return row
        raise ValueError(f"Source index {idx} is out of range.")

    selector_cf = selector.casefold()

    def _fields(row: dict[str, Any]) -> list[str]:
        return [
            str(row.get("title") or ""),
            str(row.get("source") or ""),
            str(row.get("url") or ""),
        ]

    exact = [
        row
        for row in rows
        if any(selector_cf == field.casefold() for field in _fields(row) if field)
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(_ambiguous_selector_message(selector, exact))

    partial = [
        row
        for row in rows
        if any(selector_cf in field.casefold() for field in _fields(row) if field)
    ]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise ValueError(_ambiguous_selector_message(selector, partial))
    raise ValueError(f"No source matched selector '{selector}'.")


def _ambiguous_selector_message(selector: str, rows: list[dict[str, Any]]) -> str:
    options = ", ".join(
        f"#{row['index']} {row.get('title') or row.get('source') or row.get('url') or '<unknown>'}"
        for row in rows[:5]
    )
    return f"Selector '{selector}' matched multiple sources: {options}"
