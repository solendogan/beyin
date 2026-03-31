"""Shared runtime readiness summaries for setup and CLI surfaces."""

from __future__ import annotations

from typing import Any

from beyin.install_hints import ffmpeg_install_hint, yt_dlp_install_hint
from beyin.readiness import _YTDLP_MIN_VERSION


def settings_display_rows(settings: Any) -> list[tuple[str, str]]:
    capability_map = {
        "web": "Web",
        "youtube": "YouTube/video",
        "podcasts": "Podcasts/RSS",
        "local_files": "Local files",
        "local_query": "Local answers",
    }
    enabled = settings.enabled_capabilities or []
    local_files = settings.enabled_local_file_types or []
    return [
        (
            "Enabled",
            ", ".join(capability_map.get(value, value) for value in enabled) or "none",
        ),
        (
            "File types",
            ", ".join(file_type.upper() for file_type in local_files) or "plain text only",
        ),
        ("Transcription", settings.preferred_transcription_backend),
        ("Whisper model", settings.preferred_whisper_model),
        ("Local model", settings.preferred_llm_model),
    ]


def dependency_display_rows(
    settings: Any,
    *,
    command_exists,
    import_module,
    ytdlp_version_ok,
    include_all: bool = False,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str]]:
    failures: list[str] = []
    capabilities = set(settings.enabled_capabilities or [])
    selected_file_types = set(settings.enabled_local_file_types or [])

    runtime_rows: list[tuple[str, str]] = []
    if include_all or capabilities.intersection({"youtube", "podcasts"}):
        if command_exists("ffmpeg"):
            ffmpeg_status = "found"
        else:
            ffmpeg_status = f"NOT FOUND  →  {ffmpeg_install_hint()}"
            failures.append("ffmpeg")
        runtime_rows.append(("Audio/video", f"ffmpeg: {ffmpeg_status}"))

    if include_all or "youtube" in capabilities:
        ok, version = ytdlp_version_ok()
        if ok:
            ytdlp_status = f"found ({version})"
        elif version == "unknown":
            ytdlp_status = f"NOT FOUND  →  {yt_dlp_install_hint()}"
            failures.append("yt-dlp")
        else:
            ytdlp_status = f"OUTDATED ({version} < {_YTDLP_MIN_VERSION})  →  {yt_dlp_install_hint()}"
            failures.append("yt-dlp")
        runtime_rows.append(("Audio/video", f"yt-dlp: {ytdlp_status}"))

    if not include_all and "local_query" in capabilities:
        runtime_rows.append(("Local answers", "Ollama is user-managed  →  install and run separately"))

    file_type_rows: list[tuple[str, str]] = []
    for label, module, hint in [
        ("PDF (.pdf)", "pdfplumber", "pip install pdfplumber"),
        ("DOCX (.docx)", "docx", "pip install python-docx"),
        ("PPTX (.pptx)", "pptx", "pip install python-pptx"),
        ("EPUB (.epub)", "ebooklib", "pip install ebooklib"),
        ("XLSX (.xlsx)", "openpyxl", "pip install openpyxl"),
    ]:
        extension = label.split("(")[1].split(")")[0].strip(".").lower()
        if not include_all and extension not in selected_file_types:
            continue
        try:
            import_module(module)
            status = f"{module}: found"
        except ImportError:
            status = f"{module}: not installed  →  {hint}"
        file_type_rows.append((label, status))

    return runtime_rows, file_type_rows, failures


def readiness_summary_lines(settings: Any, *, command_exists, import_module, ytdlp_version_ok) -> list[str]:
    runtime_rows, file_type_rows, failures = dependency_display_rows(
        settings,
        command_exists=command_exists,
        import_module=import_module,
        ytdlp_version_ok=ytdlp_version_ok,
    )
    lines: list[str] = []
    if failures:
        lines.append("Still needed before some selected workflows are ready:")
    else:
        lines.append("Selected workflows look ready on this machine.")
    for label, value in runtime_rows:
        lines.append(f"{label}: {value}")
    for label, value in file_type_rows:
        lines.append(f"{label}: {value}")
    if not runtime_rows and not file_type_rows:
        lines.append("No extra runtime tools selected.")
    return lines
