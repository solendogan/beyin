"""Pack inventory and shared-pack provenance helpers."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from brainpack.config import PackConfig, _load_config_from_file, load_config
from brainpack.downloader import detect_source_type
from brainpack.pack_state import load_state

_ORIGIN_FILE = "origin.json"
_MARKETPLACE_MAP_FILE = "marketplace-map.json"


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_pack_origin(pack_dir: Path) -> Dict[str, Any]:
    """Load per-pack origin metadata if present."""
    path = pack_dir / _ORIGIN_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_pack_origin(pack_dir: Path, origin: Dict[str, Any]) -> None:
    """Persist per-pack origin metadata."""
    (pack_dir / _ORIGIN_FILE).write_text(json.dumps(origin, indent=2))


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
    is_new = not has_build
    has_error = _has_failed_sources(state)

    if blockers:
        status = "blocked"
        next_action = f"brainpack doctor {config.id}"
    elif has_error:
        status = "error"
        next_action = f"brainpack build {config.id}"
    elif is_new:
        status = "new"
        next_action = f"brainpack build {config.id}"
    elif needs_build:
        status = "needs-build"
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
    origin = summary.get("origin", {})
    summary["origin_type"] = origin.get("type", "none")
    summary["origin_source"] = origin.get("source", "")
    summary["last_build_at"] = summary.get("state", {}).get("last_build_at")
    summary["last_update_at"] = origin.get("last_updated_at") or origin.get("added_at")
    summary["last_update_summary"] = origin.get("last_update_summary", [])
    return summary


def serialize_pack_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Return the stable public machine payload for one pack summary."""
    return {
        "name": summary["name"],
        "status": summary["status"],
        "type": summary["type"],
        "provider": summary["provider"],
        "source_count": summary["source_count"],
        "recent_summary": summary["recent_summary"],
        "next_action": summary["next_action"],
        "blockers": _public_messages(summary.get("blockers")),
        "warnings": _public_messages(summary.get("warnings")),
        "origin": _public_origin(summary.get("origin", {})),
    }


def serialize_pack_detail(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Return the stable public machine payload for one pack detail record."""
    payload = serialize_pack_summary(summary)
    payload.update(
        {
            "last_build_at": summary.get("last_build_at"),
            "last_update_at": summary.get("last_update_at"),
            "last_update_summary": [
                str(item) for item in summary.get("last_update_summary", [])
            ],
        }
    )
    return payload


def human_guidance_command(summary: Dict[str, Any]) -> str:
    """Return the human-facing lifecycle command without mutating machine contracts."""
    name = str(summary.get("name", "<pack>"))
    status = summary.get("status")
    if status == "blocked":
        return f"brainpack doctor {name}"
    if status in {"new", "needs-build", "error"}:
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
