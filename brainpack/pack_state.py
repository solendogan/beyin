"""Pack build state management via meta.json."""
import json
from pathlib import Path
from typing import Any, Dict

import typer


def load_state(pack_dir: Path) -> Dict[str, Any]:
    """Load meta.json from pack_dir. Returns default state if file does not exist."""
    state_path = pack_dir / "meta.json"
    if state_path.exists():
        return json.loads(state_path.read_text())
    return {"embedding_model": None, "processed": {}}


def save_state(pack_dir: Path, state: Dict[str, Any]) -> None:
    """Write state to meta.json with human-readable indentation."""
    state_path = pack_dir / "meta.json"
    state_path.write_text(json.dumps(state, indent=2))


def is_processed(state: Dict[str, Any], url: str) -> bool:
    """Return True if url has already been successfully processed."""
    return url in state.get("processed", {})


def mark_processed(state: Dict[str, Any], url: str, title: str) -> None:
    """Record url as successfully processed in state (mutates in-place)."""
    state.setdefault("processed", {})[url] = {"title": title, "status": "done"}


def mark_failed(state: Dict[str, Any], url: str, reason: str) -> None:
    """Record url as failed so it is not retried on every build."""
    state.setdefault("processed", {})[url] = {"status": "failed", "reason": reason}


def check_model_provenance(
    state: Dict[str, Any], current_model: str, pack_name: str
) -> None:
    """
    Enforce embedding model consistency (SAF-01).

    - First build (embedding_model is None): record the model in state and return.
    - Subsequent builds: abort with actionable error if model differs.

    IMPORTANT: Caller must call save_state() after this returns to persist the
    first-build model registration. This function mutates state but does NOT write
    to disk — keeping write-to-disk responsibility in the caller (cli.py).
    """
    recorded = state.get("embedding_model")
    if recorded is None:
        state["embedding_model"] = current_model
        return
    if recorded != current_model:
        raise typer.BadParameter(
            f"Embedding model mismatch: pack '{pack_name}' was built with "
            f"'{recorded}' but pack.yaml now specifies '{current_model}'. "
            f"Delete ~/.brainpacks/{pack_name}/chroma/ to rebuild from scratch, "
            f"or revert pack.yaml to use '{recorded}'."
        )
