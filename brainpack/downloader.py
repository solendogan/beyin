"""Audio source downloading — YouTube via yt-dlp, podcasts via feedparser + urllib."""
import re
from pathlib import Path
from typing import Optional

_YOUTUBE_RE = re.compile(
    r"(youtube\.com/(watch|playlist|channel|@|c/|user/)|youtu\.be/)"
)
_RSS_HINTS_RE = re.compile(r"\.(rss|xml)$|/feed/?|/rss/?", re.IGNORECASE)


def detect_source_type(url: str) -> str:
    """Return 'youtube', 'podcast', or 'article'. Never raises."""
    if _YOUTUBE_RE.search(url):
        return "youtube"
    if _RSS_HINTS_RE.search(url):
        return "podcast"
    return "article"


def list_youtube_episodes(url: str, limit: Optional[int]) -> list[dict]:
    """Return list of {id, title, url} dicts without downloading. Never raises."""
    raise NotImplementedError


def download_audio(video_url: str, out_dir: Path, title: str = "") -> Optional[Path]:
    """Download audio-only to out_dir. Returns Path on success, None on failure."""
    raise NotImplementedError


def list_podcast_episodes(feed_url: str, limit: Optional[int]) -> list[dict]:
    """Parse RSS feed, return list of {url, title, guid} dicts. Never raises."""
    raise NotImplementedError


def download_podcast_audio(audio_url: str, out_dir: Path, title: str = "") -> Optional[Path]:
    """Download podcast mp3/m4a directly via urllib. Returns Path on success, None on failure."""
    raise NotImplementedError
