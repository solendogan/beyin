"""Pack configuration loading from pack.yaml."""
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class SourceEntry:
    """A normalized source with URL and optional per-source episode limit."""
    url: str
    limit: Optional[int] = None


@dataclass
class PackConfig:
    id: str
    name: str
    description: str
    sources: List[SourceEntry]
    # brainpack-managed fields
    version: str = "1.0.0"
    created: Optional[str] = None
    updated: Optional[str] = None
    # user-provided optional fields
    tags: List[str] = field(default_factory=list)
    contributors: List[str] = field(default_factory=list)
    # runtime/local fields (kept for backward compat, not in registry schema)
    llm: str = "ollama"
    embedding_model: str = "all-MiniLM-L6-v2"
    whisper_model: str = "small"
    whisper_model_explicit: bool = True
    episode_limit: Optional[int] = 20


def _today() -> str:
    return date.today().isoformat()


def _bump_version(version: str, *, minor: bool = False) -> str:
    """Bump patch or minor version. Falls back gracefully on non-semver strings."""
    try:
        parts = version.split(".")
        major, minor_v, patch = int(parts[0]), int(parts[1]), int(parts[2])
        if minor:
            return f"{major}.{minor_v + 1}.0"
        return f"{major}.{minor_v}.{patch + 1}"
    except Exception:
        return version


def config_to_raw(config: PackConfig) -> dict:
    """Serialize PackConfig into the canonical pack.yaml structure."""
    raw: dict = {
        "id": config.id,
        "name": config.name,
        "version": config.version,
        "description": config.description,
    }
    if config.created:
        raw["created"] = config.created
    if config.updated:
        raw["updated"] = config.updated
    if config.tags:
        raw["tags"] = config.tags
    if config.contributors:
        raw["contributors"] = config.contributors
    raw["llm"] = config.llm
    raw["embedding_model"] = config.embedding_model
    raw["whisper_model"] = config.whisper_model
    raw["episode_limit"] = config.episode_limit
    raw["sources"] = [
        s.url if s.limit is None else {"url": s.url, "limit": s.limit}
        for s in config.sources
    ]
    return raw


def write_config(
    config: PackConfig,
    destination: Path,
    *,
    previous: Optional["PackConfig"] = None,
) -> Path:
    """Write PackConfig to destination. Auto-manages created/updated/version."""
    today = _today()

    # Set created on first write
    if not config.created:
        config = _replace(config, created=today)

    # Auto-bump version when previous config is provided
    if previous is not None:
        prev_urls = {s.url for s in previous.sources}
        curr_urls = {s.url for s in config.sources}
        if curr_urls != prev_urls:
            config = _replace(config, version=_bump_version(config.version, minor=True))
        elif _metadata_changed(previous, config):
            config = _replace(config, version=_bump_version(config.version))

    # Always update the updated date
    config = _replace(config, updated=today)

    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = config_to_raw(config)
    with open(destination, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False)
    return destination


def _replace(config: PackConfig, **kwargs) -> PackConfig:
    """Return a copy of config with specified fields replaced."""
    from dataclasses import replace
    return replace(config, **kwargs)


def _metadata_changed(prev: PackConfig, curr: PackConfig) -> bool:
    return (
        prev.description != curr.description
        or prev.tags != curr.tags
        or prev.contributors != curr.contributors
        or prev.name != curr.name
    )


def _parse_config_from_raw(raw: dict) -> PackConfig:
    """Parse a raw YAML dict into a PackConfig."""
    raw_sources = raw.get("sources", [])
    sources = []
    for s in raw_sources:
        if isinstance(s, str):
            sources.append(SourceEntry(url=s))
        elif isinstance(s, dict):
            sources.append(SourceEntry(url=s["url"], limit=s.get("limit")))

    # id falls back to name for backward compat
    name = raw.get("name", "")
    pack_id = raw.get("id") or name

    return PackConfig(
        id=pack_id,
        name=name,
        description=raw.get("description", ""),
        sources=sources,
        version=raw.get("version", "1.0.0"),
        created=raw.get("created"),
        updated=raw.get("updated"),
        tags=raw.get("tags", []),
        contributors=raw.get("contributors", []),
        llm=raw.get("llm", "ollama"),
        embedding_model=raw.get("embedding_model", "all-MiniLM-L6-v2"),
        whisper_model=raw.get("whisper_model", "small"),
        whisper_model_explicit="whisper_model" in raw,
        episode_limit=raw.get("episode_limit", 20),
    )


def load_config(pack_dir: Path) -> PackConfig:
    """Load and validate pack.yaml from pack_dir. Raises FileNotFoundError if missing."""
    config_path = pack_dir / "pack.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"pack.yaml not found in {pack_dir}")
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return _parse_config_from_raw(raw)


def _load_config_from_file(path: Path) -> PackConfig:
    """Load and validate pack.yaml from an arbitrary file path."""
    if not path.exists():
        raise FileNotFoundError(f"pack.yaml not found at {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    return _parse_config_from_raw(raw)
