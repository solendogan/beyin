"""Article text extraction using trafilatura."""
import json
from pathlib import Path
from typing import Optional, Tuple

from trafilatura import extract, fetch_url

_TEXT_LIKE_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".html",
    ".htm",
}
_HTML_SUFFIXES = {".html", ".htm"}


def fetch_article(url: str) -> Optional[Tuple[str, str]]:
    """
    Fetch and extract article text from url.

    Returns (text, title) on success, or None if fetch or extraction fails.
    Never raises — failed URLs should be skipped by the caller, not crash the build.
    """
    downloaded = fetch_url(url)
    if not downloaded:
        return None

    text = extract(downloaded, include_comments=False, include_tables=False)
    if not text:
        return None

    # Extract title from metadata JSON (second extract call with output_format="json")
    title = url  # fallback to URL if metadata unavailable
    meta_raw = extract(
        downloaded,
        output_format="json",
        with_metadata=True,
        include_comments=False,
        include_tables=False,
    )
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
            title = meta.get("title") or url
        except (json.JSONDecodeError, AttributeError):
            pass  # keep URL as fallback title

    return text, title


def load_text_like_source(path_like: str | Path) -> Tuple[str, str]:
    """Load one narrow local text-like source and return extracted text plus title."""
    path = Path(path_like).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Missing local source: {path}")
    if not path.is_file():
        raise ValueError(f"Unsupported local source type: {path}")

    suffix = path.suffix.lower()
    if suffix not in _TEXT_LIKE_SUFFIXES:
        raise ValueError(f"Unsupported local source type: {path}")

    raw_text = path.read_text(encoding="utf-8")
    text = raw_text
    if suffix in _HTML_SUFFIXES:
        text = extract(raw_text, include_comments=False, include_tables=False) or raw_text

    normalized = text.strip()
    if not normalized:
        raise ValueError(f"Local source is empty: {path}")
    return normalized, path.stem
