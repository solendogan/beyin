"""Article text extraction using trafilatura."""
import json
from typing import Optional, Tuple

from trafilatura import extract, fetch_url


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
