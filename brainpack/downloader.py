"""Audio source downloading — YouTube via yt-dlp, podcasts via feedparser + urllib."""
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

_MIN_AUDIO_BYTES = 10_000  # 10KB minimum for valid audio file


def detect_source_type(url: str) -> str:
    """Return 'youtube', 'podcast', or 'article'. Never raises."""
    if _YOUTUBE_RE.search(url):
        return "youtube"
    if _RSS_HINTS_RE.search(url):
        return "podcast"
    return "article"


def check_deno_available() -> bool:
    """Return True if deno is on PATH."""
    return shutil.which("deno") is not None


def list_youtube_episodes(url: str, limit: Optional[int]) -> list[dict]:
    """
    Return episode metadata list without downloading.
    Returns [] on any failure — never raises.
    """
    import yt_dlp  # lazy import — avoids import errors on platforms without yt-dlp
    ydl_opts = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
        "playlistend": limit,  # None = all episodes
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
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
        return result
    except Exception:
        return []


def download_audio(video_url: str, out_dir: Path, title: str = "") -> Optional[Path]:
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
        "progress_hooks": [_make_progress_hook(title)],
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


def list_podcast_episodes(feed_url: str, limit: Optional[int]) -> list[dict]:
    """
    Parse RSS/Atom podcast feed and return episode list.
    Skips entries without audio enclosures. Returns [] on failure. Never raises.
    """
    import feedparser  # lazy import
    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries
        if limit is not None:
            entries = entries[:limit]
        episodes = []
        for entry in entries:
            enclosures = getattr(entry, "enclosures", [])
            audio_encs = [e for e in enclosures if e.get("type", "").startswith("audio/")]
            if not audio_encs:
                # Fallback: check entry.links for rel="enclosure"
                links = getattr(entry, "links", [])
                audio_encs = [
                    lnk for lnk in links
                    if lnk.get("rel") == "enclosure" and lnk.get("type", "").startswith("audio/")
                ]
            if not audio_encs:
                continue
            episodes.append({
                "url": audio_encs[0].href,
                "title": entry.get("title", entry.get("id", "Unknown")),
                "guid": entry.get("id", audio_encs[0].href),
            })
        return episodes
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
