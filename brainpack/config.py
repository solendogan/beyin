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
    episode_limit: Optional[int] = 20


def load_config(pack_dir: Path) -> PackConfig:
    """Load and validate pack.yaml from pack_dir. Raises FileNotFoundError if missing."""
    config_path = pack_dir / "pack.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"pack.yaml not found in {pack_dir}")
    with open(config_path) as f:
        raw = yaml.safe_load(f)

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
        episode_limit=episode_limit_raw,
    )
