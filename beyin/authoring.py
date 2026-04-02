"""Shared helpers for guided pack authoring flows."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
from typing import Any

from beyin.config import PackConfig, SourceEntry
from beyin.downloader import detect_source_type, expand_playlist_sources


def split_source_inputs(source_input: str) -> list[str]:
    """Split one pasted source field into one or more newline-delimited sources."""
    parts = [part.strip() for part in re.split(r"[\r\n]+", source_input) if part.strip()]
    if not parts:
        raise ValueError("Source input cannot be empty.")
    return parts


def infer_source_intent(source_input: str) -> dict[str, str]:
    """Infer whether a value is content to author from or an existing pack import."""
    source = source_input.strip()
    if not source:
        raise ValueError("Source input cannot be empty.")

    _validate_local_source_input(source)

    source_type = detect_source_type(source)
    if source_type == "pack":
        return {"kind": "import", "source_type": "pack"}
    if source_type == "local_file":
        raise ValueError(
            "Unsupported local source type. Use a text-like file such as .txt or .md, or a media file such as .mp3 or .mp4."
        )
    normalized_type = "article" if source_type == "local_text" else source_type
    return {"kind": "content", "source_type": normalized_type}


def _looks_like_local_path(source: str) -> bool:
    candidate = Path(source).expanduser()
    if candidate.is_absolute() or source.startswith(("~/", "./", "../")):
        return True
    if "/" in source or "\\" in source:
        return True
    suffix = candidate.suffix.lower()
    return bool(suffix)


def _validate_local_source_input(source: str) -> None:
    if source.startswith(("http://", "https://")):
        return
    if not _looks_like_local_path(source):
        return

    candidate = Path(source).expanduser()
    source_type = detect_source_type(source)
    if source_type not in {"local_text", "local_document", "local_audio", "local_video", "local_file"}:
        return
    if candidate.exists() and candidate.is_file():
        return

    raise ValueError(
        f"Local path not found: {source}. Check the path and try again."
    )


def build_new_pack_config(
    *,
    name: str,
    description: str,
    source_input: str,
    llm: str = "ollama",
) -> PackConfig:
    """Build a new pack config from one or more authored sources."""
    sources = _normalize_authored_sources(source_input) if source_input.strip() else []
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
    existing_urls = {e.url for e in config.sources}
    new_entries = _normalize_authored_sources(source_input, existing_urls=existing_urls)
    if not new_entries:
        return config
    return replace(config, sources=[*config.sources, *new_entries])


def validate_authored_sources(source_input: str) -> None:
    """Validate authored sources early without needing pack metadata yet."""
    for source in split_source_inputs(source_input):
        intent = infer_source_intent(source)
        if intent["kind"] != "content":
            raise ValueError(
                "Existing pack imports belong on `beyin add <path-or-url-or-id>`, not `beyin create`."
            )


def _normalize_authored_sources(
    source_input: str,
    *,
    existing_urls: set[str] | None = None,
) -> list[SourceEntry]:
    """Normalize one or more authored sources, expanding feeds/playlists and deduping URLs."""
    seen_urls = set(existing_urls or set())
    normalized: list[SourceEntry] = []

    for source in split_source_inputs(source_input):
        intent = infer_source_intent(source)
        if intent["kind"] != "content":
            raise ValueError(
                "Existing pack imports belong on `beyin add <path-or-url-or-id>`, not `beyin create`."
            )

        expanded = expand_playlist_sources(source)
        if expanded:
            for ep in expanded:
                url = ep.get("url")
                if not url or url in seen_urls:
                    continue
                normalized.append(
                    SourceEntry(
                        url=url,
                        title=ep.get("title"),
                        parent_url=source,
                        parent_title=ep.get("parent_title"),
                    )
                )
                seen_urls.add(url)
            continue

        if source in seen_urls:
            continue
        normalized.append(SourceEntry(url=source))
        seen_urls.add(source)

    return normalized


def remove_sources_from_pack(
    config: PackConfig,
    selectors: list[str],
    *,
    source_rows: list[dict[str, Any]] | None = None,
) -> tuple[PackConfig, list[dict[str, Any]]]:
    """Remove one or more sources from a pack by current index or text match."""
    rows = source_rows or _default_source_rows(config)
    matched_indexes = resolve_source_indexes(rows, selectors)
    matched_lookup = set(matched_indexes)

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


def resolve_source_indexes(
    rows: list[dict[str, Any]],
    selectors: list[str],
) -> list[int]:
    """Resolve source selectors to unique current indexes while preserving order."""
    if not selectors:
        raise ValueError("Provide at least one source selector.")

    matched_indexes: list[int] = []
    matched_lookup: set[int] = set()
    max_index = len(rows)

    for raw_selector in selectors:
        selector = raw_selector.strip()
        if not selector:
            continue

        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", selector)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start > end:
                raise ValueError(f"Invalid source range '{selector}'. Use ascending ranges like 1-3.")
            if start < 1 or end > max_index:
                raise ValueError(f"Source range {selector} is out of range.")
            for idx in range(start, end + 1):
                if idx not in matched_lookup:
                    matched_indexes.append(idx)
                    matched_lookup.add(idx)
            continue

        row = _match_source_selector(rows, selector)
        row_index = int(row["index"])
        if row_index not in matched_lookup:
            matched_indexes.append(row_index)
            matched_lookup.add(row_index)

    if not matched_indexes:
        raise ValueError("No sources matched the provided selectors.")

    return matched_indexes


def select_sources_from_pack(
    config: PackConfig,
    selectors: list[str],
    *,
    source_rows: list[dict[str, Any]] | None = None,
) -> tuple[PackConfig, list[dict[str, Any]]]:
    """Return a config limited to the selected current sources without mutating the source order."""
    rows = source_rows or _default_source_rows(config)
    matched_indexes = resolve_source_indexes(rows, selectors)
    selected_lookup = set(matched_indexes)
    selected_rows = [row for row in rows if int(row["index"]) in selected_lookup]
    selected_sources = [
        source
        for i, source in enumerate(config.sources, start=1)
        if i in selected_lookup
    ]
    return replace(config, sources=selected_sources), selected_rows


def _default_source_rows(config: PackConfig) -> list[dict[str, Any]]:
    return [
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
