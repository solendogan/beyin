"""Shared runtime readiness summaries for setup and CLI surfaces."""

from __future__ import annotations

from typing import Any

from beyin.install_hints import (
    ffmpeg_install_hint,
    nltk_punkt_tab_install_hint,
    yt_dlp_install_hint,
)
from beyin.readiness import _YTDLP_MIN_VERSION


_DOCUMENT_SOURCE_MODULES: list[tuple[str, str, str, str]] = [
    ("pdf", "PDF", ".pdf", "pdfplumber"),
    ("docx", "DOCX", ".docx", "docx"),
    ("pptx", "PPTX", ".pptx", "pptx"),
    ("epub", "EPUB", ".epub", "ebooklib"),
    ("xlsx", "XLSX", ".xlsx", "openpyxl"),
]


def settings_display_rows(settings: Any) -> list[tuple[str, str]]:
    capability_map = {
        "web": "Web",
        "youtube": "Videos",
        "podcasts": "Podcasts",
        "local_files": "Local files",
        "local_query": "Local answers",
    }
    enabled = settings.enabled_capabilities or []
    local_files = settings.enabled_local_file_types or []
    rows = [
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
    ]
    if "local_query" in enabled:
        rows.append(("Local model", settings.preferred_llm_model))
    return rows


def dependency_snapshot(
    settings: Any,
    *,
    command_exists,
    import_module,
    nltk_punkt_tab_available,
    ytdlp_version_ok,
    include_all: bool = False,
) -> dict[str, Any]:
    failures: list[str] = []
    capabilities = set(settings.enabled_capabilities or [])
    selected_file_types = set(settings.enabled_local_file_types or [])

    runtime: list[dict[str, Any]] = []
    if nltk_punkt_tab_available():
        punkt_tab_status = "found"
        punkt_tab_available = True
        punkt_tab_hint = None
    else:
        punkt_tab_status = "not_found"
        punkt_tab_available = False
        punkt_tab_hint = nltk_punkt_tab_install_hint()
        failures.append("punkt_tab")
    runtime.append(
        {
            "id": "punkt_tab",
            "category": "text_processing",
            "label": "punkt_tab",
            "status": punkt_tab_status,
            "available": punkt_tab_available,
            "install_hint": punkt_tab_hint,
            "selected": True,
        }
    )

    if include_all or capabilities.intersection({"youtube", "podcasts"}):
        ffmpeg_available = command_exists("ffmpeg") is not None
        runtime.append(
            {
                "id": "ffmpeg",
                "category": "audio_video",
                "label": "ffmpeg",
                "status": "found" if ffmpeg_available else "not_found",
                "available": ffmpeg_available,
                "install_hint": None if ffmpeg_available else ffmpeg_install_hint(),
                "selected": include_all or bool(capabilities.intersection({"youtube", "podcasts"})),
            }
        )
        if not ffmpeg_available:
            failures.append("ffmpeg")

    if include_all or "youtube" in capabilities:
        ytdlp_ok, ytdlp_version = ytdlp_version_ok()
        if ytdlp_ok:
            ytdlp_status = "found"
            ytdlp_hint = None
        elif ytdlp_version == "unknown":
            ytdlp_status = "not_found"
            ytdlp_hint = yt_dlp_install_hint()
            failures.append("yt-dlp")
        else:
            ytdlp_status = "outdated"
            ytdlp_hint = yt_dlp_install_hint()
            failures.append("yt-dlp")
        runtime.append(
            {
                "id": "yt-dlp",
                "category": "audio_video",
                "label": "yt-dlp",
                "status": ytdlp_status,
                "available": ytdlp_ok,
                "version": None if ytdlp_version == "unknown" else ytdlp_version,
                "minimum_version": None if ytdlp_ok or ytdlp_version == "unknown" else _YTDLP_MIN_VERSION,
                "install_hint": ytdlp_hint,
                "selected": include_all or "youtube" in capabilities,
            }
        )

    if not include_all and "local_query" in capabilities:
        runtime.append(
            {
                "id": "ollama",
                "category": "local_answers",
                "label": "Ollama",
                "status": "user_managed",
                "available": None,
                "install_hint": "install and run separately",
                "selected": True,
            }
        )

    document_sources: list[dict[str, Any]] = []
    for source_id, label, extension, module in _DOCUMENT_SOURCE_MODULES:
        selected = source_id in selected_file_types
        if not include_all and not selected:
            continue
        try:
            import_module(module)
            available = True
        except ImportError:
            available = False
        document_sources.append(
            {
                "id": source_id,
                "label": label,
                "extension": extension,
                "module": module,
                "status": "found" if available else "not_installed",
                "available": available,
                "selected": selected,
            }
        )

    return {
        "runtime": runtime,
        "document_sources": document_sources,
        "failures": failures,
    }


def dependency_display_rows(
    settings: Any,
    *,
    command_exists,
    import_module,
    nltk_punkt_tab_available,
    ytdlp_version_ok,
    include_all: bool = False,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str]]:
    snapshot = dependency_snapshot(
        settings,
        command_exists=command_exists,
        import_module=import_module,
        nltk_punkt_tab_available=nltk_punkt_tab_available,
        ytdlp_version_ok=ytdlp_version_ok,
        include_all=include_all,
    )

    runtime_rows: list[tuple[str, str]] = []
    for entry in snapshot["runtime"]:
        if entry["id"] == "punkt_tab":
            status = "found" if entry["available"] else f"NOT FOUND  →  {entry['install_hint']}"
            runtime_rows.append(("Text processing", f"punkt_tab: {status}"))
        elif entry["id"] == "ffmpeg":
            status = "found" if entry["available"] else f"NOT FOUND  →  {entry['install_hint']}"
            runtime_rows.append(("Audio/video", f"ffmpeg: {status}"))
        elif entry["id"] == "yt-dlp":
            if entry["status"] == "found":
                status = f"found ({entry['version']})"
            elif entry["status"] == "outdated":
                status = (
                    f"OUTDATED ({entry['version']} < {entry['minimum_version']})  →  {entry['install_hint']}"
                )
            else:
                status = f"NOT FOUND  →  {entry['install_hint']}"
            runtime_rows.append(("Audio/video", f"yt-dlp: {status}"))
        elif entry["id"] == "ollama":
            runtime_rows.append(("Local answers", "Ollama is user-managed  →  install and run separately"))

    file_type_rows = [
        (f"{entry['label']} ({entry['extension']})", f"{entry['module']}: {'found' if entry['available'] else 'not installed'}")
        for entry in snapshot["document_sources"]
    ]

    return runtime_rows, file_type_rows, snapshot["failures"]


def readiness_summary_lines(
    settings: Any,
    *,
    command_exists,
    import_module,
    nltk_punkt_tab_available,
    ytdlp_version_ok,
) -> list[str]:
    runtime_rows, file_type_rows, failures = dependency_display_rows(
        settings,
        command_exists=command_exists,
        import_module=import_module,
        nltk_punkt_tab_available=nltk_punkt_tab_available,
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
