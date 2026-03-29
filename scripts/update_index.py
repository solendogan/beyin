"""Regenerate packs/index.json from all YAML files in packs/."""

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
PACKS_DIR = REPO_ROOT / "packs"
INDEX_PATH = PACKS_DIR / "index.json"
RAW_BASE_URL = "https://raw.githubusercontent.com/buralog/beyin/main/packs"


def build_index() -> list[dict]:
    entries = []
    for path in sorted(PACKS_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        entries.append({
            "id": data["id"],
            "name": data["name"],
            "description": data["description"],
            "tags": data.get("tags", []),
            "author": data.get("author", ""),
            "url": f"{RAW_BASE_URL}/{path.name}",
        })
    return entries


def main() -> None:
    index = build_index()
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {INDEX_PATH} with {len(index)} pack(s).")


if __name__ == "__main__":
    main()
