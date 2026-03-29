"""Canonical source identity helpers."""
import hashlib
import re
from collections.abc import Mapping
from typing import Any, Optional
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")
_SIMPLE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _youtube_video_id(url: str) -> Optional[str]:
    """Extract a stable YouTube video ID from a URL when possible."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host not in _YOUTUBE_HOSTS:
        return None
    if host == "youtu.be":
        return parsed.path.lstrip("/").split("/")[0] or None
    if parsed.path == "/watch":
        return parse_qs(parsed.query).get("v", [None])[0]
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] in {"embed", "live", "shorts", "v"}:
        return parts[1]
    return parts[-1] if parts else None


def _coerce_source(source: Any) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    return {"url": str(source)}


def _provider_token(value: str) -> str:
    """Keep simple provider IDs readable; hash noisy GUID or URL-style identifiers."""
    text = value.strip()
    if _SIMPLE_ID_RE.fullmatch(text) and len(text) <= 80:
        return text
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _normalized_url(url: str) -> str:
    """Normalize fallback URLs so fragments and query ordering do not change identity."""
    text = url.strip()
    if not text:
        return ""

    parsed = urlparse(text)
    if not parsed.scheme and not parsed.netloc:
        return text

    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunparse((scheme, netloc, path, "", query, ""))


def canonical_source_id(
    source: Any,
    source_type: Optional[str] = None,
    *,
    guid: Optional[str] = None,
    external_id: Optional[str] = None,
) -> str:
    """
    Return a canonical identity for a source or episode.

    YouTube prefers stable video IDs, podcasts prefer GUID/id values, and
    everything else falls back to a normalized URL hash.
    """
    record = _coerce_source(source)
    if guid and not record.get("guid"):
        record["guid"] = guid
    if external_id and not record.get("id"):
        record["id"] = external_id
    if source_type and not record.get("source_type"):
        record["source_type"] = source_type

    source_type = record.get("source_type") or source_type
    url = str(record.get("url", ""))

    if source_type == "youtube" or _youtube_video_id(url):
        video_id = record.get("id") or _youtube_video_id(url)
        if video_id:
            return f"youtube:{_provider_token(str(video_id))}"

    if source_type == "podcast" or record.get("guid") or record.get("id"):
        episode_id = record.get("guid") or record.get("id")
        if episode_id:
            provider = "podcast" if source_type == "podcast" or record.get("guid") else str(source_type)
            return f"{provider}:{_provider_token(str(episode_id))}"

    normalized_url = _normalized_url(url)
    if normalized_url:
        digest = hashlib.sha1(normalized_url.encode("utf-8")).hexdigest()[:16]
        return f"url:{digest}"

    return f"unknown:{hashlib.sha1(repr(record).encode('utf-8')).hexdigest()[:12]}"


def artifact_stem(source_id: str) -> str:
    """Return a filesystem-safe stem derived from the canonical source ID."""
    digest = hashlib.sha1(source_id.encode("utf-8")).hexdigest()[:12]
    readable = _SAFE_CHARS_RE.sub("-", source_id).strip("-").lower()[:48].strip("-")
    if readable:
        return f"{readable}-{digest}"
    return digest
