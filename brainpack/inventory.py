"""Pack inventory and shared-pack provenance helpers."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from brainpack.config import PackConfig, _load_config_from_file, load_config
from brainpack.downloader import detect_source_type
from brainpack.pack_state import load_state
from brainpack.source_ids import canonical_source_id

_ORIGIN_FILE = "origin.json"
_MARKETPLACE_MAP_FILE = "marketplace-map.json"
_ORIGIN_SCHEMA_VERSION = 2
_READY_RATIO_RE = re.compile(r"^(\d+)/(\d+) ready(?:, \d+ failed)?(?:, \d+ empty)?$")


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_pack_origin(pack_dir: Path) -> Dict[str, Any]:
    """Load per-pack origin metadata if present."""
    path = pack_dir / _ORIGIN_FILE
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        return {}
    origin = dict(raw)
    origin["schema_version"] = _ORIGIN_SCHEMA_VERSION
    if origin.get("last_update_summary") is None:
        origin["last_update_summary"] = []
    elif not isinstance(origin.get("last_update_summary"), list):
        origin["last_update_summary"] = [str(origin["last_update_summary"])]
    return origin


def save_pack_origin(pack_dir: Path, origin: Dict[str, Any]) -> None:
    """Persist per-pack origin metadata."""
    payload = dict(origin)
    payload["schema_version"] = _ORIGIN_SCHEMA_VERSION
    if payload.get("last_update_summary") is None:
        payload["last_update_summary"] = []
    (pack_dir / _ORIGIN_FILE).write_text(json.dumps(payload, indent=2))


def marketplace_mapping_path(packs_dir: Path) -> Path:
    """Return the lightweight local alias mapping file location."""
    return packs_dir / _MARKETPLACE_MAP_FILE


def load_marketplace_mapping(packs_dir: Path) -> Dict[str, str]:
    """Load marketplace-style ID aliases from the local mapping file."""
    path = marketplace_mapping_path(packs_dir)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    if isinstance(raw, dict) and isinstance(raw.get("aliases"), dict):
        return {str(k): str(v) for k, v in raw["aliases"].items()}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {}


def resolve_pack_origin(source: str, packs_dir: Path) -> Dict[str, str]:
    """Resolve a file path, URL, or marketplace-style ID into a concrete YAML source."""
    if source.startswith(("http://", "https://")):
        return {"type": "url", "source": source, "resolved": source}

    candidate = Path(source).expanduser()
    if candidate.exists():
        return {
            "type": "file",
            "source": str(candidate.resolve()),
            "resolved": str(candidate.resolve()),
        }

    aliases = load_marketplace_mapping(packs_dir)
    if not aliases:
        raise FileNotFoundError(
            f"No marketplace mapping file found at {marketplace_mapping_path(packs_dir)}."
        )
    if source not in aliases:
        raise KeyError(
            f"Marketplace pack id '{source}' not found in {marketplace_mapping_path(packs_dir)}."
        )
    return {"type": "id", "source": source, "resolved": aliases[source]}


def pack_config_hash(pack_dir: Path) -> str:
    """Hash the installed pack.yaml contents for stale/build tracking."""
    raw = (pack_dir / "pack.yaml").read_text()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def pack_file_hash(path: Path) -> str:
    """Hash an arbitrary pack.yaml file for sync tracking."""
    raw = path.read_text()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def summarize_pack_changes(current: PackConfig, incoming: PackConfig) -> list[str]:
    """Return a compact before/after summary for shared-pack updates."""
    changes: list[str] = []
    if current.llm != incoming.llm:
        changes.append(f"provider: {current.llm} -> {incoming.llm}")
    current_sources = [source.url for source in current.sources]
    incoming_sources = [source.url for source in incoming.sources]
    if len(current_sources) != len(incoming_sources):
        changes.append(f"sources: {len(current_sources)} -> {len(incoming_sources)}")
    added = [url for url in incoming_sources if url not in current_sources]
    removed = [url for url in current_sources if url not in incoming_sources]
    if added:
        changes.append(f"added: {', '.join(added[:2])}")
    if removed:
        changes.append(f"removed: {', '.join(removed[:2])}")
    if current.embedding_model != incoming.embedding_model:
        changes.append(
            f"embedding_model: {current.embedding_model} -> {incoming.embedding_model}"
        )
    return changes


def _has_successful_build(state: Dict[str, Any]) -> bool:
    if state.get("last_build_at"):
        return True
    processed = state.get("processed", {})
    if any(item.get("status") == "done" for item in processed.values()):
        return True
    audio_steps = state.get("audio_steps", {})
    return any(step.get("stages", {}).get("embedded") for step in audio_steps.values())


def _has_failed_sources(state: Dict[str, Any]) -> bool:
    return any(item.get("status") == "failed" for item in state.get("processed", {}).values())


def _has_nonready_sources(state: Dict[str, Any]) -> bool:
    return any(
        item.get("status") in {"failed", "empty"}
        for item in state.get("processed", {}).values()
    )


def _source_nonready_entries(processed: Dict[str, Any], url: str) -> list[dict]:
    """Return non-ready processed entries that belong to a specific configured source."""
    direct_sid = canonical_source_id(url)
    direct = processed.get(direct_sid)
    entries: list[dict] = []
    if isinstance(direct, dict) and direct.get("status") in {"failed", "empty"}:
        entries.append(direct)
    owned = [
        entry
        for sid, entry in processed.items()
        if sid != direct_sid
        and isinstance(entry, dict)
        and entry.get("status") in {"failed", "empty"}
        and entry.get("parent_source_url") == url
    ]
    entries.extend(sorted(owned, key=lambda e: e.get("title") or e.get("url") or ""))
    return entries


def _pack_source_progress(config: PackConfig, state: Dict[str, Any]) -> Dict[str, int]:
    """Summarize source-level readiness for one configured pack."""
    rows = serialize_pack_sources(config, state)
    ready = 0
    failed = 0

    for row in rows:
        status = str(row.get("status") or "")
        if status == "ready":
            ready += 1
            continue
        if status in {"failed", "empty"}:
            failed += 1
            continue
        match = _READY_RATIO_RE.match(status)
        if match:
            completed, total = int(match.group(1)), int(match.group(2))
            if "failed" in status or "empty" in status:
                failed += 1
            elif total > 0 and completed == total:
                ready += 1

    return {
        "total": len(rows),
        "ready": ready,
        "failed": failed,
    }


def _format_when(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return value[:10]
    except Exception:
        return value


def _public_origin(origin: Dict[str, Any]) -> Dict[str, str]:
    """Return the stable public origin shape for machine-safe payloads."""
    return {
        "type": str(origin.get("type", "none")),
        "source": str(origin.get("source", "")),
    }


def pack_diverged_from_origin(pack_dir: Path, origin: Dict[str, Any] | None = None) -> bool:
    """Return True when local pack.yaml changed since the last synced origin snapshot."""
    origin = origin or load_pack_origin(pack_dir)
    last_synced_pack_hash = origin.get("last_synced_pack_hash")
    if not origin.get("source") or not last_synced_pack_hash:
        return False
    try:
        return pack_config_hash(pack_dir) != last_synced_pack_hash
    except Exception:
        return False


def _source_family(config: PackConfig) -> str:
    """Return the compact user-facing source family label for a pack."""
    families = {
        "text" if detect_source_type(source.url) == "article" else detect_source_type(source.url)
        for source in config.sources
    }
    if not families:
        return "text"
    if len(families) == 1:
        return next(iter(families))
    return "mixed"


def _public_messages(values: Any) -> list[str]:
    """Normalize human-oriented multi-line messages into stable public strings."""
    messages: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if not text:
            continue
        messages.append(text.splitlines()[0].strip())
    return messages


def summarize_pack(
    pack_dir: Path,
    readiness_fn: Callable[[PackConfig], Dict[str, list[str]]],
) -> Dict[str, Any]:
    """Derive one compact lifecycle summary for an installed pack."""
    origin = load_pack_origin(pack_dir)
    try:
        config = load_config(pack_dir)
    except Exception as exc:
        return {
            "name": pack_dir.name,
            "status": "error",
            "provider": "unknown",
            "source_count": 0,
            "recent_summary": "invalid-pack",
            "next_action": f"brainpack add {pack_dir / 'pack.yaml'}",
            "blockers": [f"Invalid pack.yaml: {exc}"],
            "warnings": [],
            "origin": origin,
        }

    state = load_state(pack_dir)
    readiness = readiness_fn(config)
    blockers = list(readiness.get("blockers", []))
    warnings = list(readiness.get("warnings", []))
    has_build = _has_successful_build(state)
    current_hash = pack_config_hash(pack_dir)
    last_build_hash = state.get("last_built_pack_hash")
    needs_build = bool(has_build and last_build_hash and last_build_hash != current_hash)
    partial_selection = (
        state.get("last_build_result") == "partial-selection"
        and last_build_hash != current_hash
    )
    is_new = not has_build
    has_error = _has_nonready_sources(state)
    observed_source_state = bool(state.get("processed") or state.get("audio_steps"))
    source_progress = _pack_source_progress(config, state) if observed_source_state else {
        "total": len(config.sources),
        "ready": 0,
        "failed": 0,
    }
    all_sources_ready = (
        observed_source_state
        and source_progress["total"] > 0
        and source_progress["ready"] == source_progress["total"]
        and source_progress["failed"] == 0
    )
    some_sources_ready = source_progress["ready"] > 0
    if pack_diverged_from_origin(pack_dir, origin):
        warnings.append("Local pack differs from the last synced origin.")

    if blockers:
        status = "blocked"
        next_action = f"brainpack status {config.id}"
    elif has_error and has_build:
        status = "partially-ready"
        next_action = f"brainpack build {config.id}"
    elif has_error:
        status = "error"
        next_action = f"brainpack build {config.id}"
    elif (partial_selection or needs_build) and some_sources_ready and not all_sources_ready:
        status = "partially-ready"
        next_action = f"brainpack build {config.id}"
    elif partial_selection:
        status = "needs-build"
        next_action = f"brainpack build {config.id}"
    elif is_new:
        status = "new"
        next_action = f"brainpack build {config.id}"
    elif needs_build:
        status = "needs-build"
        next_action = f"brainpack build {config.id}"
    elif some_sources_ready and not all_sources_ready:
        status = "partially-ready"
        next_action = f"brainpack build {config.id}"
    else:
        status = "ready"
        next_action = f'brainpack query {config.id} "question"'

    build_date = _format_when(state.get("last_build_at"))
    update_date = _format_when(origin.get("last_updated_at") or origin.get("added_at"))
    if update_date and build_date:
        recent_summary = f"build {build_date} / upd {update_date}"
    elif build_date:
        recent_summary = f"build {build_date}"
    elif update_date:
        recent_summary = f"upd {update_date}"
    else:
        recent_summary = "never-built"

    return {
        "id": config.id,
        "name": config.name,
        "description": config.description,
        "status": status,
        "type": _source_family(config),
        "provider": config.llm,
        "source_count": len(config.sources),
        "recent_summary": recent_summary,
        "next_action": next_action,
        "blockers": blockers,
        "warnings": warnings,
        "origin": origin,
        "state": state,
        "config": config,
    }


def inspect_pack(
    pack_dir: Path,
    readiness_fn: Callable[[PackConfig], Dict[str, list[str]]],
) -> Dict[str, Any]:
    """Return a detailed pack inspection record."""
    summary = summarize_pack(pack_dir, readiness_fn)
    state = summary.get("state", {})
    origin = summary.get("origin", {})
    summary["origin_type"] = origin.get("type", "none")
    summary["origin_source"] = origin.get("source", "")
    summary["last_build_at"] = state.get("last_build_at")
    summary["last_build_result"] = state.get("last_build_result")
    summary["last_build_summary"] = state.get("last_build_summary")
    summary["last_update_at"] = origin.get("last_updated_at") or origin.get("added_at")
    summary["last_update_summary"] = origin.get("last_update_summary", [])
    summary["last_sync_at"] = origin.get("last_sync_at")
    summary["last_sync_status"] = origin.get("last_sync_status")
    return summary


def serialize_pack_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Return the stable public machine payload for one pack summary."""
    return {
        "id": summary["id"],
        "name": summary["name"],
        "status": summary["status"],
        "provider": summary["provider"],
        "source_count": summary["source_count"],
        "recent_summary": summary["recent_summary"],
        "next_action": summary["next_action"],
        "blockers": _public_messages(summary.get("blockers")),
        "warnings": _public_messages(summary.get("warnings")),
        "origin": _public_origin(summary.get("origin", {})),
    }


def serialize_pack_sources(config: Any, state: Dict[str, Any]) -> list:
    """Build a detailed sources list from config and build state."""
    processed = state.get("processed", {})
    audio_steps = state.get("audio_steps", {})
    playlist_titles = state.get("playlist_titles", {})

    def _source_audio_entries(url: str, source_type: str) -> list[dict]:
        direct_sid = canonical_source_id(url)
        if direct_sid in audio_steps:
            return [audio_steps[direct_sid]]
        owned = [
            entry for entry in audio_steps.values()
            if entry.get("parent_source_url") == url
        ]
        if owned:
            return sorted(owned, key=lambda e: e.get("title") or e.get("url") or "")
        if source_type not in {"youtube", "podcast"}:
            return []
        return []

    result = []
    for source_index, source in enumerate(config.sources, start=1):
        url = source.url
        sid = canonical_source_id(url)
        source_type = detect_source_type(url)
        source_audio_entries = _source_audio_entries(url, source_type)
        source_nonready = _source_nonready_entries(processed, url)

        if sid in processed:
            entry = processed[sid]
            entry_status = entry.get("status")
            result.append({
                "index": source_index,
                "source": url,
                "url": url,
                "title": entry.get("title") or source.title or url,
                "status": (
                    "ready"
                    if entry_status == "done"
                    else "empty"
                    if entry_status == "empty"
                    else "failed"
                ),
                "type": source_type,
            })
        elif source_audio_entries and sid in audio_steps:
            entry = source_audio_entries[0]
            stages = entry.get("stages", {})
            if stages.get("embedded"):
                status = "ready"
            elif stages.get("transcribed") or stages.get("downloaded"):
                status = "partial"
            else:
                status = "pending"
            result.append({
                "index": source_index,
                "source": url,
                "url": url,
                "title": entry.get("title") or source.title or url,
                "status": status,
                "type": source_type,
            })
        elif source_type in {"youtube", "podcast"} and (source_audio_entries or source_nonready):
            embedded = sum(1 for e in source_audio_entries if e.get("stages", {}).get("embedded"))
            total = len(source_audio_entries) + len(source_nonready)
            failed = sum(1 for ep in source_nonready if ep.get("status") == "failed")
            empty = sum(1 for ep in source_nonready if ep.get("status") == "empty")
            episodes = [
                {
                    "url": ep.get("url", ""),
                    "title": ep.get("title", ""),
                    "status": "ready" if ep.get("stages", {}).get("embedded") else "partial" if ep.get("stages", {}).get("transcribed") or ep.get("stages", {}).get("downloaded") else "pending",
                }
                for ep in source_audio_entries
            ] + [
                {
                    "url": ep.get("url", ""),
                    "title": ep.get("title") or ep.get("url", ""),
                    "status": "empty" if ep.get("status") == "empty" else "failed",
                }
                for ep in source_nonready
            ]
            episodes = sorted(episodes, key=lambda ep: ep.get("title") or ep.get("url") or "")
            status = f"{embedded}/{total} ready"
            if failed:
                status += f", {failed} failed"
            if empty:
                status += f", {empty} empty"
            result.append({
                "index": source_index,
                "source": url,
                "url": url,
                "title": source.title or playlist_titles.get(url) or url,
                "status": status,
                "type": source_type,
                "episodes": episodes,
            })
        else:
            result.append({
                "index": source_index,
                "source": url,
                "url": url,
                "title": source.title or url,
                "status": "pending",
                "type": source_type,
            })
    return result


def serialize_pack_detail(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Return the stable public machine payload for one pack detail record."""
    payload = serialize_pack_summary(summary)
    config = summary.get("config")
    state = summary.get("state", {})
    payload.update(
        {
            "version": config.version if config else None,
            "description": config.description if config else None,
            "tags": list(config.tags) if config and config.tags else [],
            "contributors": list(config.contributors) if config and config.contributors else [],
            "last_build_at": summary.get("last_build_at"),
            "last_update_at": summary.get("last_update_at"),
            "last_update_summary": [
                str(item) for item in summary.get("last_update_summary", [])
            ],
            "sources": serialize_pack_sources(config, state) if config else [],
        }
    )
    return payload


def human_guidance_command(summary: Dict[str, Any]) -> str:
    """Return the human-facing lifecycle command without mutating machine contracts."""
    name = str(summary.get("name", "<pack>"))
    status = summary.get("status")
    if status == "blocked":
        return f"brainpack status {name}"
    if status in {"new", "needs-build", "partially-ready", "error"}:
        return f"brainpack build {name}"
    return "brainpack mcp-server"


def next_action_reason(summary: Dict[str, Any]) -> str:
    """Explain why the recommended next command is the best next step."""
    status = summary.get("status")
    if status == "blocked":
        return "Resolve the blocker so this pack is ready for agent or local-model use."
    if status == "new":
        return "Build this pack before Brainpack can serve it to an agent or local model."
    if status == "needs-build":
        return "Rebuild this pack so agent and local-mode retrieval use the latest indexed changes."
    if status == "partially-ready":
        return "Build the remaining sources before using this pack so retrieval covers the full configured set."
    if status == "error":
        return "Rebuild this pack after the last indexing failure before using it again."
    if status == "ready":
        return "Connect an agent for the recommended path, or query the pack directly in local mode."
    return "Re-add or repair the pack definition before continuing."


def list_packs(
    packs_dir: Path,
    readiness_fn: Callable[[PackConfig], Dict[str, list[str]]],
) -> list[Dict[str, Any]]:
    """Return alphabetical compact summaries for all installed packs."""
    if not packs_dir.exists():
        return []
    pack_dirs = [path for path in packs_dir.iterdir() if path.is_dir() and (path / "pack.yaml").exists()]
    return [
        summarize_pack(pack_dir, readiness_fn)
        for pack_dir in sorted(pack_dirs, key=lambda item: item.name.lower())
    ]


def load_config_from_source_path(path: str) -> PackConfig:
    """Load a PackConfig from a resolved file path."""
    return _load_config_from_file(Path(path))
