"""Shared path resolution for Brainpack runtime state."""

from __future__ import annotations

import os
from pathlib import Path


def brainpack_home() -> Path:
    """Return the canonical Brainpack runtime root directory."""
    value = os.environ.get("BRAINPACK_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".brainpacks"


def packs_dir() -> Path:
    """Return the canonical installed-packs directory."""
    value = os.environ.get("BRAINPACK_PACKS_DIR")
    if value:
        return Path(value).expanduser()
    return brainpack_home()


def settings_path() -> Path:
    """Return the machine-level settings file path."""
    return brainpack_home() / "settings.json"
