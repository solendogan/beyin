"""Whisper transcription — mlx-whisper on Apple Silicon, faster-whisper everywhere else."""
import platform
import sys
from pathlib import Path
from typing import Callable, Optional

_MLX_MODEL_MAP = {
    "tiny":      "mlx-community/whisper-tiny-mlx",
    "tiny.en":   "mlx-community/whisper-tiny.en-mlx",
    "base":      "mlx-community/whisper-base-mlx",
    "base.en":   "mlx-community/whisper-base.en-mlx",
    "small":     "mlx-community/whisper-small-mlx",
    "small.en":  "mlx-community/whisper-small.en-mlx",
    "medium":    "mlx-community/whisper-medium-mlx",
    "medium.en": "mlx-community/whisper-medium.en-mlx",
    "large":     "mlx-community/whisper-large-v3-mlx",
}


def _is_apple_silicon() -> bool:
    """Return True on Apple Silicon (arm64 + darwin)."""
    return sys.platform == "darwin" and platform.machine() == "arm64"


def transcribe_audio(
    audio_path: Path,
    model_size: str = "small",
    language: Optional[str] = None,
    verbose: bool = False,
    progress_callback: Optional[Callable[[float, Optional[float]], None]] = None,
) -> list[dict]:
    """
    Transcribe audio file. Returns list of segment dicts:
    [{"start": float, "end": float, "text": str}, ...]

    Backend selected automatically: mlx-whisper on arm64+darwin, faster-whisper elsewhere.
    Returns [] on any failure — never raises.
    """
    try:
        if _is_apple_silicon():
            return _transcribe_mlx(
                audio_path,
                model_size,
                language,
                verbose=verbose,
                progress_callback=progress_callback,
            )
        return _transcribe_faster(
            audio_path,
            model_size,
            language,
            verbose=verbose,
            progress_callback=progress_callback,
        )
    except Exception:
        return []


def _transcribe_faster(
    audio_path: Path,
    model_size: str,
    language: Optional[str],
    verbose: bool = False,
    progress_callback: Optional[Callable[[float, Optional[float]], None]] = None,
) -> list[dict]:
    """faster-whisper backend — Linux / non-Apple-Silicon."""
    from faster_whisper import WhisperModel  # lazy import
    import typer
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(audio_path),
        language=language,                    # None = auto-detect
        vad_filter=True,                      # TRN-02: Silero VAD prevents hallucination loops
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,     # additional hallucination guard
        beam_size=5,
        word_timestamps=False,               # segment timestamps sufficient (TRN-04)
    )
    total_duration = getattr(info, "duration", None)
    result = []
    for seg in segments:
        if progress_callback is not None:
            progress_callback(seg.end, total_duration)
        if verbose:
            typer.echo(f"  [transcribe] [{seg.start:.1f}s] {seg.text.strip()}")
        result.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
    return result


def _transcribe_mlx(
    audio_path: Path,
    model_size: str,
    language: Optional[str],
    verbose: bool = False,
    progress_callback: Optional[Callable[[float, Optional[float]], None]] = None,
) -> list[dict]:
    """mlx-whisper backend — Apple Silicon only. Must only be called after _is_apple_silicon() check."""
    import mlx_whisper  # lazy import — NOT available on Linux
    hf_repo = _MLX_MODEL_MAP.get(model_size, "mlx-community/whisper-small-mlx")
    output = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=hf_repo,
        language=language,                    # None = auto-detect
        condition_on_previous_text=False,     # TRN-02 mitigation: no native VAD in mlx-whisper
        word_timestamps=False,               # segment-level sufficient (TRN-04)
        verbose=True if verbose else False,  # False keeps MLX progress visible without per-segment logs
    )
    return [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}
        for seg in output.get("segments", [])
    ]
