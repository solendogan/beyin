"""Pack build state management via meta.json."""
import json
from pathlib import Path
from typing import Any, Dict

import typer

from brainpack.source_ids import canonical_source_id

_STATE_SCHEMA_VERSION = 3


def _default_state() -> Dict[str, Any]:
    return {
        "schema_version": _STATE_SCHEMA_VERSION,
        "embedding_model": None,
        "transcription_model": None,
        "transcription_language": None,
        "processed": {},
        "audio_steps": {},
        "last_build_result": None,
        "last_build_summary": None,
    }


def _extract_url(source: Any) -> str:
    if isinstance(source, dict):
        return str(source.get("url", ""))
    return str(source)


def _record_source_id(source: Any, source_id: str | None = None) -> str:
    return source_id or canonical_source_id(source)


def _upgrade_processed(processed: Dict[str, Any]) -> Dict[str, Any]:
    upgraded: Dict[str, Any] = {}
    for key, entry in processed.items():
        record = dict(entry) if isinstance(entry, dict) else {"status": str(entry)}
        url = record.get("url", key)
        sid = record.get("source_id") or canonical_source_id(url)
        record["source_id"] = sid
        record.setdefault("url", url)
        upgraded[sid] = record
    return upgraded


def _upgrade_audio_steps(audio_steps: Dict[str, Any]) -> Dict[str, Any]:
    upgraded: Dict[str, Any] = {}
    for key, entry in audio_steps.items():
        record = dict(entry) if isinstance(entry, dict) else {}
        url = record.get("url", key)
        sid = record.get("source_id") or canonical_source_id(
            {"url": url, "guid": record.get("guid"), "id": record.get("id")}
        )
        record["source_id"] = sid
        record.setdefault("url", url)
        stages = dict(record.get("stages", {}))
        for step in ("downloaded", "transcribed", "embedded"):
            if step in record:
                stages[step] = bool(record.pop(step))
        record["stages"] = stages
        upgraded[sid] = record
    return upgraded


def _upgrade_state(state: Dict[str, Any]) -> Dict[str, Any]:
    upgraded = _default_state()
    upgraded.update(state)
    upgraded["schema_version"] = _STATE_SCHEMA_VERSION
    upgraded["processed"] = _upgrade_processed(upgraded.get("processed", {}))
    upgraded["audio_steps"] = _upgrade_audio_steps(upgraded.get("audio_steps", {}))
    upgraded["transcription_model"] = (
        None
        if upgraded.get("transcription_model") is None
        else str(upgraded.get("transcription_model"))
    )
    upgraded["transcription_language"] = (
        None
        if upgraded.get("transcription_language") is None
        else str(upgraded.get("transcription_language"))
    )
    upgraded["last_build_result"] = (
        None
        if upgraded.get("last_build_result") is None
        else str(upgraded.get("last_build_result"))
    )
    upgraded["last_build_summary"] = (
        None
        if upgraded.get("last_build_summary") is None
        else str(upgraded.get("last_build_summary"))
    )
    return upgraded


def load_state(pack_dir: Path) -> Dict[str, Any]:
    """Load meta.json from pack_dir. Returns default state if file does not exist."""
    state_path = pack_dir / "meta.json"
    if state_path.exists():
        return _upgrade_state(json.loads(state_path.read_text()))
    return _default_state()


def save_state(pack_dir: Path, state: Dict[str, Any]) -> None:
    """Write state to meta.json with human-readable indentation."""
    state_path = pack_dir / "meta.json"
    state_path.write_text(json.dumps(_upgrade_state(state), indent=2))


def is_processed(state: Dict[str, Any], source: Any, source_id: str | None = None) -> bool:
    """Return True if the source has already been successfully processed."""
    sid = _record_source_id(source, source_id=source_id)
    return sid in state.get("processed", {})


def mark_processed(
    state: Dict[str, Any],
    source: Any,
    title: str,
    source_id: str | None = None,
) -> None:
    """Record a source as successfully processed in state (mutates in-place)."""
    sid = _record_source_id(source, source_id=source_id)
    state.setdefault("processed", {})[sid] = {
        "source_id": sid,
        "url": _extract_url(source),
        "title": title,
        "status": "done",
    }


def mark_failed(
    state: Dict[str, Any],
    source: Any,
    reason: str,
    source_id: str | None = None,
) -> None:
    """Record a source as failed so it is not retried on every build."""
    sid = _record_source_id(source, source_id=source_id)
    state.setdefault("processed", {})[sid] = {
        "source_id": sid,
        "url": _extract_url(source),
        "status": "failed",
        "reason": reason,
    }


def get_audio_step(
    state: Dict[str, Any],
    source: Any,
    source_id: str | None = None,
) -> Dict[str, Any]:
    """Return step tracking dict for a source. Returns {} if not tracked yet."""
    sid = _record_source_id(source, source_id=source_id)
    return state.get("audio_steps", {}).get(sid, {})


def mark_audio_step(
    state: Dict[str, Any],
    source: Any,
    step: str,
    title: str = "",
    source_id: str | None = None,
    parent_source_url: str | None = None,
) -> None:
    """
    Mark a specific step as complete for a source.
    Steps: 'downloaded', 'transcribed', 'embedded'.
    Mutates state in-place — caller must call save_state().
    """
    sid = _record_source_id(source, source_id=source_id)
    audio_steps = state.setdefault("audio_steps", {})
    episode = audio_steps.setdefault(
        sid,
        {"source_id": sid, "url": _extract_url(source), "stages": {}},
    )
    if title:
        episode["title"] = title
    if parent_source_url:
        episode["parent_source_url"] = parent_source_url
    episode.setdefault("stages", {})[step] = True


def is_audio_step_done(
    state: Dict[str, Any],
    source: Any,
    step: str,
    source_id: str | None = None,
) -> bool:
    """Return True if the given step is marked complete for the source."""
    sid = _record_source_id(source, source_id=source_id)
    return state.get("audio_steps", {}).get(sid, {}).get("stages", {}).get(step, False)


def check_model_provenance(
    state: Dict[str, Any], current_model: str, pack_name: str
) -> None:
    """
    Enforce embedding model consistency (SAF-01).

    - First build (embedding_model is None): record the model in state and return.
    - Subsequent builds: abort with actionable error if model differs.

    IMPORTANT: Caller must call save_state() after this returns to persist the
    first-build model registration. This function mutates state but does NOT write
    to disk — keeping write-to-disk responsibility in the caller (cli.py).
    """
    recorded = state.get("embedding_model")
    if recorded is None:
        state["embedding_model"] = current_model
        return
    if recorded != current_model:
        raise typer.BadParameter(
            f"Embedding model mismatch: pack '{pack_name}' was built with "
            f"'{recorded}' but pack.yaml now specifies '{current_model}'. "
            f"Run `brainpack build {pack_name} --reset` to rebuild from scratch, "
            f"or revert pack.yaml to use '{recorded}'."
        )


def check_transcription_provenance(
    state: Dict[str, Any],
    current_model: str,
    current_language: str | None,
    pack_name: str,
) -> None:
    """
    Enforce transcription-model consistency for audio-derived pack data.

    Audio transcripts and chunks should not silently mix outputs produced by
    different Whisper model sizes or language settings.
    """
    recorded_model = state.get("transcription_model")
    recorded_language = state.get("transcription_language")
    has_audio_state = bool(state.get("audio_steps"))

    if recorded_model is None:
        state["transcription_model"] = current_model
        state["transcription_language"] = current_language
        return

    if recorded_model != current_model:
        if has_audio_state:
            raise typer.BadParameter(
                f"Transcription model mismatch: pack '{pack_name}' was built with "
                f"Whisper '{recorded_model}' but the current build is using '{current_model}'. "
                f"Run `brainpack build {pack_name} --reset` to rebuild transcripts and chunks from scratch, "
                f"or switch back to '{recorded_model}'."
            )
        state["transcription_model"] = current_model

    if recorded_language != current_language:
        if has_audio_state:
            previous = recorded_language or "auto-detect"
            current = current_language or "auto-detect"
            raise typer.BadParameter(
                f"Transcription language mismatch: pack '{pack_name}' was built with "
                f"'{previous}' but the current build is using '{current}'. "
                f"Run `brainpack build {pack_name} --reset` to rebuild transcripts and chunks from scratch, "
                f"or switch back to '{previous}'."
            )
        state["transcription_language"] = current_language
