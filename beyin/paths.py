"""Shared path resolution for beyin runtime state."""

from __future__ import annotations

import os
from pathlib import Path


def beyin_home() -> Path:
    """Return the canonical beyin runtime root directory."""
    value = os.environ.get("BEYIN_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".beyin"


def packs_dir() -> Path:
    """Return the canonical installed-packs directory."""
    value = os.environ.get("BEYIN_PACKS_DIR")
    if value:
        return Path(value).expanduser()
    return beyin_home()


def settings_path() -> Path:
    """Return the machine-level settings file path."""
    return beyin_home() / "settings.json"
