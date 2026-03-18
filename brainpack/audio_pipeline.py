"""Audio and transcript file helpers for the Brainpack build pipeline."""
from __future__ import annotations

import json
from pathlib import Path

from brainpack.chunker import count_tokens
from brainpack.source_ids import artifact_stem


def _transcript_path(transcripts_dir: Path, source_id: str) -> Path:
    return transcripts_dir / f"{artifact_stem(source_id)}.json"


def _legacy_transcript_path(transcripts_dir: Path, episode_url: str) -> Path:
    return transcripts_dir / f"{episode_url.split('/')[-1].split('?')[0]}.txt"


def _candidate_audio_paths(audio_dir: Path, source_id: str, episode: dict) -> list[Path]:
    stem = artifact_stem(source_id)
    candidates = list(audio_dir.glob(f"{stem}.*"))
    legacy_id = episode.get("id") or episode.get("guid", "")
    if legacy_id:
        candidates.extend(audio_dir.glob(f"{legacy_id}.*"))
    url_tail = episode.get("url", "").split("?")[0].split("/")[-1]
    if url_tail:
        candidates.extend(audio_dir.glob(url_tail))
    deduped = []
    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _canonical_audio_path(audio_dir: Path, source_id: str, audio_path: Path) -> Path:
    destination = audio_dir / f"{artifact_stem(source_id)}{audio_path.suffix}"
    if audio_path == destination:
        return audio_path
    destination.parent.mkdir(exist_ok=True)
    audio_path.replace(destination)
    return destination


def _load_transcript_segments(transcript_path: Path, legacy_path: Path) -> list[dict]:
    if transcript_path.exists():
        raw = json.loads(transcript_path.read_text())
        return [segment for segment in raw if segment.get("text", "").strip()]
    if legacy_path.exists():
        text = legacy_path.read_text().strip()
        if text:
            return [{"text": text}]
    return []


def _save_transcript_segments(transcript_path: Path, segments: list[dict]) -> None:
    transcript_path.write_text(json.dumps(segments, indent=2))


def _chunk_transcript_segments(
    segments: list[dict],
    window: int = 5,
    overlap: int = 2,
    max_tokens: int = 256,
) -> tuple[list[str], list[dict]]:
    """Chunk transcript segments while preserving timestamp ranges when available."""
    filtered = [segment for segment in segments if segment.get("text", "").strip()]
    if not filtered:
        return [], []

    step = max(1, window - overlap)
    chunks: list[str] = []
    metadatas: list[dict] = []
    for start_idx in range(0, len(filtered), step):
        window_segments = filtered[start_idx : start_idx + window]
        text = " ".join(segment["text"].strip() for segment in window_segments).strip()
        while window_segments and count_tokens(text) > max_tokens:
            window_segments = window_segments[:-1]
            text = " ".join(segment["text"].strip() for segment in window_segments).strip()
        if not window_segments or not text:
            continue
        metadata: dict[str, float] = {}
        start = window_segments[0].get("start")
        end = window_segments[-1].get("end")
        if start is not None and end is not None:
            metadata["timestamp_start"] = float(start)
            metadata["timestamp_end"] = float(end)
        chunks.append(text)
        metadatas.append(metadata)
    return chunks, metadatas
