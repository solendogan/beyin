"""Audio source downloading — YouTube via yt-dlp, podcasts via feedparser + urllib."""
import html
import re
import shutil
import urllib.request
from pathlib import Path
from typing import Optional

import typer

_YOUTUBE_RE = re.compile(
    r"(youtube\.com/(watch|playlist|channel|@|c/|user/)|youtu\.be/)"
)
_RSS_HINTS_RE = re.compile(r"\.(rss|xml)$|/feed/?|/rss/?", re.IGNORECASE)
_PACK_CONFIG_SUFFIXES = {".yaml", ".yml"}
_TEXT_LIKE_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".html",
    ".htm",
}
_LOCAL_AUDIO_SUFFIXES = {
    ".mp3",
    ".m4a",
    ".wav",
    ".aac",
    ".flac",
    ".ogg",
}
_LOCAL_VIDEO_SUFFIXES = {
    ".mp4",
    ".mov",
    ".mkv",
    ".m4v",
    ".webm",
}
_DOCUMENT_SUFFIXES = {
    ".pdf",
    ".docx",
    ".pptx",
    ".epub",
    ".xlsx",
    ".csv",
}
_MIN_PODCAST_TEXT_CHARS = 500

_MIN_AUDIO_BYTES = 10_000  # 10KB minimum for valid audio file


_REMOTE_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac"}


def detect_source_type(url: str) -> str:
    """Return a narrow source classification for build and authoring flows. Never raises."""
    lowered = url.lower()
    if url.startswith(("http://", "https://")):
        if lowered.endswith(tuple(_PACK_CONFIG_SUFFIXES)) or "/pack.yaml" in lowered or "/pack.yml" in lowered:
            return "pack"
        if _YOUTUBE_RE.search(url):
            return "youtube"
        if _RSS_HINTS_RE.search(url):
            return "podcast"
        # Remote audio file (e.g. direct podcast CDN links)
        from urllib.parse import urlparse
        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in _REMOTE_AUDIO_EXTENSIONS):
            return "podcast_audio"
        return "article"

    candidate = Path(url).expanduser()
    suffix = candidate.suffix.lower()
    if candidate.name.lower() in {"pack.yaml", "pack.yml"} or suffix in _PACK_CONFIG_SUFFIXES:
        return "pack"
    if suffix in _TEXT_LIKE_SUFFIXES:
        return "local_text"
    if suffix in _DOCUMENT_SUFFIXES:
        return "local_document"
    if suffix in _LOCAL_AUDIO_SUFFIXES:
        return "local_audio"
    if suffix in _LOCAL_VIDEO_SUFFIXES:
        return "local_video"
    if candidate.exists() and candidate.is_file():
        return "local_file"
    if _YOUTUBE_RE.search(url):
        return "youtube"
    if _RSS_HINTS_RE.search(url):
        return "podcast"
    return "article"


def check_deno_available() -> bool:
    """Return True if deno is on PATH."""
    return shutil.which("deno") is not None


def list_youtube_episodes(url: str, limit: Optional[int]) -> tuple[str | None, list[dict]]:
    """
    Return (playlist_title, episodes) without downloading.
    playlist_title is None for single videos or on failure.
    Returns (None, []) on any failure — never raises.
    """
    import yt_dlp  # lazy import — avoids import errors on platforms without yt-dlp
    ydl_opts = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "playlistend": limit,  # None = all episodes
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        is_playlist = "entries" in info
        playlist_title = info.get("title") if is_playlist else None
        entries = info.get("entries", [info])  # single video falls back to [info]
        result = []
        for e in entries:
            if not e:
                continue
            result.append({
                "id": e.get("id", ""),
                "title": e.get("title", "Unknown"),
                "url": e.get("webpage_url") or e.get("url") or "",
            })
        return playlist_title, result
    except Exception:
        return None, []


def download_audio(video_url: str, out_dir: Path, title: str = "", verbose: bool = False) -> Optional[Path]:
    """
    Download audio-only from a YouTube URL to out_dir.
    Checks file size > 10KB (partial download guard).
    Returns Path on success, None on failure. Never raises.
    """
    import yt_dlp  # lazy import
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [_make_progress_hook(title)] if verbose else [],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
        audio_path = out_dir / f"{info['id']}.{info['ext']}"
        if not audio_path.exists() or audio_path.stat().st_size < _MIN_AUDIO_BYTES:
            if audio_path.exists():
                audio_path.unlink()  # discard partial file
            return None
        return audio_path
    except Exception:
        return None


def _make_progress_hook(title: str):
    """Return a yt-dlp progress hook that prints [download] step labels."""
    def _hook(d: dict) -> None:
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "?")
            speed = d.get("_speed_str", "")
            typer.echo(f"  [download] {pct} {speed}".rstrip(), nl=False)
            typer.echo("\r", nl=False)
        elif d["status"] == "finished":
            typer.echo(f"  [download] done — {title or d.get('filename', '')}")
    return _hook


def _strip_markup(value: str) -> str:
    """Collapse HTML-ish content into plain text for transcript-aware RSS ingestion."""
    text = html.unescape(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _podcast_entry_text(entry) -> str:
    """Return the most useful transcript/show-note text exposed by a feed entry."""
    candidates: list[str] = []

    for content in getattr(entry, "content", []) or []:
        if isinstance(content, dict):
            candidates.append(content.get("value", ""))
        else:
            candidates.append(getattr(content, "value", ""))

    summary_detail = getattr(entry, "summary_detail", None)
    if isinstance(summary_detail, dict):
        candidates.append(summary_detail.get("value", ""))
    else:
        candidates.append(getattr(summary_detail, "value", ""))

    candidates.extend(
        [
            entry.get("summary", ""),
            entry.get("description", ""),
            entry.get("subtitle", ""),
        ]
    )

    normalized = [_strip_markup(candidate) for candidate in candidates if candidate]
    normalized = [text for text in normalized if text]
    if not normalized:
        return ""
    return max(normalized, key=len)


def list_podcast_episodes(feed_url: str, limit: Optional[int]) -> list[dict]:
    """
    Parse RSS/Atom feed and return episode list.

    Podcast feeds (entries with audio enclosures): returns audio episodes.
    Text feeds (blogs, news — no audio enclosures): returns article entries
    with mode="article" so the build pipeline fetches them as articles.

    Returns [] on failure. Never raises.
    """
    import feedparser  # lazy import
    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries
        if limit is not None:
            entries = entries[:limit]

        # First pass: collect audio episodes (standard podcast behavior)
        episodes = []
        any_audio = False
        for entry in entries:
            transcript_text = _podcast_entry_text(entry)
            enclosures = getattr(entry, "enclosures", [])
            audio_encs = [e for e in enclosures if e.get("type", "").startswith("audio/")]
            if not audio_encs:
                # Fallback: check entry.links for rel="enclosure"
                links = getattr(entry, "links", [])
                audio_encs = [
                    lnk for lnk in links
                    if lnk.get("rel") == "enclosure" and lnk.get("type", "").startswith("audio/")
                ]
            if audio_encs:
                any_audio = True
            if not audio_encs and len(transcript_text) < _MIN_PODCAST_TEXT_CHARS:
                continue
            entry_url = entry.get("link") or entry.get("id") or (
                audio_encs[0].href if audio_encs else feed_url
            )
            episodes.append({
                "url": audio_encs[0].href if audio_encs else entry_url,
                "entry_url": entry_url,
                "title": entry.get("title", entry.get("id", "Unknown")),
                "guid": entry.get("id", entry_url),
                **({"transcript_text": transcript_text} if len(transcript_text) >= _MIN_PODCAST_TEXT_CHARS else {}),
            })

        if episodes:
            return episodes

        # No audio found — treat as a text RSS feed (blog, news, etc.)
        # Return article entries for the build pipeline to fetch as articles.
        if not any_audio:
            text_entries = []
            for entry in entries:
                entry_url = entry.get("link") or entry.get("id") or ""
                title = entry.get("title", entry.get("id", "Unknown"))
                if not entry_url:
                    continue
                text_entries.append({
                    "url": entry_url,
                    "entry_url": entry_url,
                    "title": title,
                    "guid": entry.get("id", entry_url),
                    "mode": "article",
                })
            return text_entries

        return []
    except Exception:
        return []


def download_podcast_audio(audio_url: str, out_dir: Path, title: str = "") -> Optional[Path]:
    """
    Download podcast audio file via urllib (direct CDN URL — no yt-dlp needed).
    Returns Path on success, None on failure. Never raises.
    Checks file size > 10KB to guard against partial downloads.
    """
    filename = audio_url.split("?")[0].split("/")[-1] or "episode.mp3"
    out_path = out_dir / filename
    try:
        typer.echo(f"  [download] {title or audio_url}")
        urllib.request.urlretrieve(audio_url, out_path)
        if not out_path.exists() or out_path.stat().st_size < _MIN_AUDIO_BYTES:
            if out_path.exists():
                out_path.unlink()
            return None
        typer.echo(f"  [download] done — {filename}")
        return out_path
    except Exception:
        if out_path.exists():
            out_path.unlink()
        return None


def expand_playlist_sources(url: str) -> list[dict] | None:
    """
    If url is a YouTube playlist or RSS feed, fetch its items and return
    a list of {"url": ..., "title": ...} dicts for individual sources.

    Returns None for non-expandable URLs (single video, article, etc.).
    Never raises.
    """
    source_type = detect_source_type(url)

    if source_type == "youtube":
        try:
            playlist_title, episodes = list_youtube_episodes(url, limit=None)
        except Exception:
            return None
        if not playlist_title or not episodes:
            return None  # single video — don't expand
        return [{"url": ep["url"], "title": ep["title"], "parent_title": playlist_title} for ep in episodes if ep.get("url")]

    if source_type == "podcast":
        try:
            episodes = list_podcast_episodes(url, limit=None)
        except Exception:
            return None
        if not episodes:
            return None
        result = []
        for ep in episodes:
            if ep.get("mode") == "article" or ep.get("transcript_text"):
                result.append({"url": ep.get("entry_url") or ep["url"], "title": ep["title"]})
            else:
                result.append({"url": ep["url"], "title": ep["title"]})
        return result or None

    return None
