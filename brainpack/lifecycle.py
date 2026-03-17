"""Shared helpers for destructive installed-pack lifecycle operations."""
import shutil
from pathlib import Path

_RUNTIME_DIRS = ("chroma", "audio", "transcripts")
_RUNTIME_FILES = ("meta.json",)


def reset_pack_runtime(pack_dir: Path) -> None:
    """Delete generated runtime artifacts while preserving pack definition files."""
    for name in _RUNTIME_DIRS:
        shutil.rmtree(pack_dir / name, ignore_errors=True)
    for name in _RUNTIME_FILES:
        path = pack_dir / name
        if path.exists():
            path.unlink()


def remove_installed_pack(pack_dir: Path) -> None:
    """Delete one installed pack directory."""
    shutil.rmtree(pack_dir, ignore_errors=True)
