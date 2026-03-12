"""Pack configuration loading from pack.yaml."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml


@dataclass
class PackConfig:
    name: str
    description: str
    llm: str  # "ollama" | "openai" | "anthropic"
    sources: List[str]
    embedding_model: str = "all-MiniLM-L6-v2"


def load_config(pack_dir: Path) -> PackConfig:
    """Load and validate pack.yaml from pack_dir. Raises FileNotFoundError if missing."""
    config_path = pack_dir / "pack.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"pack.yaml not found in {pack_dir}")
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return PackConfig(
        name=raw["name"],
        description=raw.get("description", ""),
        llm=raw.get("llm", "ollama"),
        sources=raw.get("sources", []),
        embedding_model=raw.get("embedding_model", "all-MiniLM-L6-v2"),
    )
