"""Pack configuration loading from pack.yaml."""
from dataclasses import dataclass, field
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
    name: str
    description: str
    llm: str  # "ollama" | "openai" | "anthropic"
    sources: List[SourceEntry]
    embedding_model: str = "all-MiniLM-L6-v2"
    whisper_model: str = "small"
    whisper_model_explicit: bool = True
    episode_limit: Optional[int] = 20


def config_to_raw(config: PackConfig) -> dict:
    """Serialize PackConfig into the canonical pack.yaml structure."""
    return {
        "name": config.name,
        "description": config.description,
        "llm": config.llm,
        "embedding_model": config.embedding_model,
        "whisper_model": config.whisper_model,
        "episode_limit": config.episode_limit,
        "sources": [
            {
                **{"url": source.url},
                **({"limit": source.limit} if source.limit is not None else {}),
            }
            for source in config.sources
        ],
    }


def write_config(config: PackConfig, destination: Path) -> Path:
    """Write PackConfig to destination using the canonical pack.yaml schema."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = config_to_raw(config)
    with open(destination, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False)
    return destination


def _parse_config_from_raw(raw: dict) -> PackConfig:
    """Parse a raw YAML dict into a PackConfig. Shared by load_config and _load_config_from_file."""
    raw_sources = raw.get("sources", [])
    sources = []
    for s in raw_sources:
        if isinstance(s, str):
            sources.append(SourceEntry(url=s))
        elif isinstance(s, dict):
            sources.append(SourceEntry(url=s["url"], limit=s.get("limit")))

    episode_limit_raw = raw.get("episode_limit", 20)

    return PackConfig(
        name=raw["name"],
        description=raw.get("description", ""),
        llm=raw.get("llm", "ollama"),
        sources=sources,
        embedding_model=raw.get("embedding_model", "all-MiniLM-L6-v2"),
        whisper_model=raw.get("whisper_model", "small"),
        whisper_model_explicit="whisper_model" in raw,
        episode_limit=episode_limit_raw,
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
    """Load and validate pack.yaml from an arbitrary file path (not a pack directory).

    Used by the install command to validate a pack.yaml before copying it.
    Raises FileNotFoundError if path does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"pack.yaml not found at {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    return _parse_config_from_raw(raw)
