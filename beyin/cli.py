"""beyin CLI — build and query commands."""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from typing import List, Optional

import click
import typer
from typer.core import TyperCommand

from beyin import __version__
from beyin.config import (
    PackConfig,
    SourceEntry,
    _load_config_from_file,
    load_config,
    write_public_config,
    write_config,
)
from beyin.inventory import (
    human_guidance_command,
    inspect_pack,
    list_packs,
    load_config_from_source_path,
    load_pack_origin,
    next_action_reason,
    pack_file_hash,
    pack_config_hash,
    pack_diverged_from_origin,
    resolve_pack_origin,
    save_pack_origin,
    serialize_pack_detail,
    serialize_pack_sources,
    serialize_pack_summary,
    summarize_pack_changes,
    utc_now_iso,
)
from beyin.pack_state import (
    check_model_provenance,
    check_transcription_provenance,
    get_audio_step,
    is_audio_step_done,
    is_processed,
    load_state,
    mark_audio_step,
    mark_empty,
    mark_failed,
    mark_processed,
    save_state,
)
from beyin.lifecycle import remove_installed_pack, reset_pack_runtime
from beyin.machine_output import MachineExit, run_machine_command
from beyin.source_ids import artifact_stem, canonical_source_id
from beyin.settings import (
    available_setup_choices,
    load_settings,
    needs_initial_setup,
    resolve_build_defaults,
    save_settings,
)
from beyin.build_report import BuildReport
from beyin.payloads import (
    _list_payload,
    _load_query_runtime,
    _query_payload,
    _status_payload,
)
from beyin.paths import packs_dir
from beyin.readiness import (
    _check_ffmpeg_available,
    _check_ollama_reachable,
    _has_audio_sources,
    _has_youtube_sources,
    _query_provider_error,
    _youtube_build_issue,
    _ytdlp_version_ok,
    _YTDLP_MIN_VERSION,
)
from beyin.ui import (
    bold, box_bottom, box_row, box_sep, box_top, cyan, dim, green, red,
    render_header, render_meta, render_review, render_rows, render_status, render_table, tbl_bottom,
    tbl_row, tbl_sep, tbl_top, visible_len as _visible_len, wrap_text, yellow,
    _col, _display_status, _display_type, _episode_icon, _origin_display,
    _pack_label, _render_pack_table, _status_styled,
)


def _missing_parameter_label(param: click.Parameter) -> str:
    if isinstance(param, click.Argument):
        return f"<{param.name.replace('_', '-')}>"
    if isinstance(param, click.Option):
        return next(
            (opt for opt in param.opts if opt.startswith("--")),
            param.opts[0] if param.opts else f"--{param.name.replace('_', '-')}",
        )
    return param.name


def _strip_help_option_from_help_text(help_text: str) -> str:
    lines = help_text.splitlines()
    output: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if "╭─ Options" not in line:
            if "--help" not in line:
                output.append(line)
            i += 1
            continue

        block = [line]
        i += 1
        while i < len(lines):
            block.append(lines[i])
            if "╰" in lines[i]:
                i += 1
                break
            i += 1

        filtered = [row for row in block if "--help" not in row]
        has_visible_option = any(
            ("│" in row or "|" in row) and "--" in row
            for row in filtered[1:-1]
        )
        if has_visible_option:
            output.extend(filtered)

    return "\n".join(output)


def _beyin_command_path(ctx: click.Context) -> str:
    parts: list[str] = []
    cursor = ctx
    while cursor is not None:
        if cursor.info_name:
            parts.append(cursor.info_name)
        cursor = cursor.parent
    if not parts:
        return "beyin"
    parts = list(reversed(parts))
    parts[0] = "beyin"
    return " ".join(parts)


def _argument_usage_token(param: click.Argument) -> str:
    token = f"<{param.name.replace('_', '-')}>"
    if param.nargs != 1:
        token += "..."
    return token


def _option_usage_token(param: click.Option) -> Optional[str]:
    if param.hidden or "--help" in param.opts:
        return None
    primary = next(
        (opt for opt in param.opts if opt.startswith("--")),
        param.opts[0] if param.opts else f"--{param.name.replace('_', '-')}",
    )
    if param.is_flag:
        value = primary
    else:
        value = f"{primary} <{param.name.replace('_', '-')}>"
    return value if param.required else f"[{value}]"


def _rewrite_usage_line(help_text: str, ctx: click.Context, command: click.Command) -> str:
    arguments = [
        token
        for param in command.get_params(ctx)
        if isinstance(param, click.Argument)
        for token in [_argument_usage_token(param)]
    ]
    options = [
        token
        for param in command.get_params(ctx)
        if isinstance(param, click.Option)
        for token in [_option_usage_token(param)]
        if token is not None
    ]
    usage = f" Usage: {_beyin_command_path(ctx)}"
    if arguments:
        usage += " " + " ".join(arguments)
    if options:
        usage += " " + " ".join(options)

    lines = help_text.splitlines()
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("Usage:"):
            leading = line[: len(line) - len(line.lstrip())]
            lines[idx] = f"{leading}{usage.strip()}"
            break
    return "\n".join(lines)


def _colorize_missing_arg_help(help_text: str) -> str:
    if not sys.stderr.isatty():
        return help_text

    styled = help_text
    for heading in ("Usage:", "Arguments", "Options"):
        styled = styled.replace(heading, click.style(heading, fg="cyan", bold=True))
    styled = styled.replace("[required]", click.style("[required]", fg="red", bold=True))
    styled = re.sub(
        r"(?m)^(\s*Usage:\s+)(beyin .+)$",
        lambda match: match.group(1) + click.style(match.group(2), fg="bright_white", bold=True),
        styled,
    )
    styled = re.sub(
        r"(?m)(--[a-zA-Z0-9-]+(?:,\s+-[a-zA-Z])?)",
        lambda match: click.style(match.group(1), fg="green", bold=True),
        styled,
    )
    return styled


def _command_help_text(command: click.Command, ctx: click.Context) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        command.get_help(ctx)
    return buf.getvalue()


def _render_missing_parameter_error(
    ctx: click.Context,
    command: click.Command,
    exc: click.MissingParameter,
) -> None:
    param = exc.param
    if param is None:
        raise exc

    typer.echo(f"{bold('beyin')} {dim(f'v{__version__}')}", err=True)
    typer.echo("", err=True)
    typer.echo(f"{red('Error:')} Missing required argument: {_missing_parameter_label(param)}", err=True)
    typer.echo("", err=True)
    help_text = _command_help_text(command, ctx)
    help_text = _strip_help_option_from_help_text(help_text)
    help_text = _rewrite_usage_line(help_text, ctx, command)
    help_text = _colorize_missing_arg_help(help_text)
    typer.echo(help_text.rstrip() + "\n", err=True)


class BeyinCommand(TyperCommand):
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except click.MissingParameter as exc:
            if ctx.resilient_parsing:
                raise
            _render_missing_parameter_error(ctx, self, exc)
            raise click.exceptions.Exit(2)


app = typer.Typer(
    help=(
        "beyin — use with an agent for evidence retrieval, or run query in local model mode"
    ),
    add_completion=False,
)

_PACKS_DIR = packs_dir()
_YTDLP_MIN_VERSION = "2025.11.12"


def detect_source_type(url: str) -> str:
    from beyin.downloader import detect_source_type as _detect_source_type

    return _detect_source_type(url)


def check_deno_available() -> bool:
    from beyin.downloader import check_deno_available as _check_deno_available

    return _check_deno_available()


def download_audio(*args, **kwargs):
    from beyin.downloader import download_audio as _download_audio

    return _download_audio(*args, **kwargs)


def download_podcast_audio(*args, **kwargs):
    from beyin.downloader import download_podcast_audio as _download_podcast_audio

    return _download_podcast_audio(*args, **kwargs)


def list_podcast_episodes(*args, **kwargs):
    from beyin.downloader import list_podcast_episodes as _list_podcast_episodes

    return _list_podcast_episodes(*args, **kwargs)


def list_youtube_episodes(*args, **kwargs):
    from beyin.downloader import list_youtube_episodes as _list_youtube_episodes

    return _list_youtube_episodes(*args, **kwargs)


def load_model(*args, **kwargs):
    from beyin.embedder import load_model as _load_model

    return _load_model(*args, **kwargs)


def build_new_pack_config(*args, **kwargs):
    from beyin.authoring import build_new_pack_config as _build_new_pack_config

    return _build_new_pack_config(*args, **kwargs)


def remove_sources_from_pack(*args, **kwargs):
    from beyin.authoring import remove_sources_from_pack as _remove_sources_from_pack

    return _remove_sources_from_pack(*args, **kwargs)


def select_sources_from_pack(*args, **kwargs):
    from beyin.authoring import select_sources_from_pack as _select_sources_from_pack

    return _select_sources_from_pack(*args, **kwargs)


def chunk_text(*args, **kwargs):
    from beyin.chunker import chunk_text as _chunk_text

    return _chunk_text(*args, **kwargs)


def is_interactive_session(*args, **kwargs):
    from beyin.interactive import is_interactive_session as _is_interactive_session

    return _is_interactive_session(*args, **kwargs)


def load_prompt_backend():
    from beyin.interactive import load_prompt_backend as _load_prompt_backend

    return _load_prompt_backend()


def _interactive_select(*args, **kwargs):
    from beyin.interactive import _select as _select

    return _select(*args, **kwargs)


def _interactive_text(*args, **kwargs):
    from beyin.interactive import _text as _text

    return _text(*args, **kwargs)


def _interactive_model_description(*args, **kwargs):
    from beyin.interactive import _model_description as _model_description

    return _model_description(*args, **kwargs)


def _interactive_choice(*args, **kwargs):
    from beyin.interactive import _choice as _choice

    return _choice(*args, **kwargs)


def _interactive_confirm(*args, **kwargs):
    from beyin.interactive import _confirm as _confirm

    return _confirm(*args, **kwargs)


def _interactive_abort_type():
    from beyin.interactive import InteractiveAbort

    return InteractiveAbort


def _candidate_audio_paths(*args, **kwargs):
    from beyin.audio_pipeline import _candidate_audio_paths as _impl

    return _impl(*args, **kwargs)


def _canonical_audio_path(*args, **kwargs):
    from beyin.audio_pipeline import _canonical_audio_path as _impl

    return _impl(*args, **kwargs)


def _chunk_transcript_segments(*args, **kwargs):
    from beyin.audio_pipeline import _chunk_transcript_segments as _impl

    return _impl(*args, **kwargs)


def _legacy_transcript_path(*args, **kwargs):
    from beyin.audio_pipeline import _legacy_transcript_path as _impl

    return _impl(*args, **kwargs)


def _load_transcript_segments(*args, **kwargs):
    from beyin.audio_pipeline import _load_transcript_segments as _impl

    return _impl(*args, **kwargs)


def _save_transcript_segments(*args, **kwargs):
    from beyin.audio_pipeline import _save_transcript_segments as _impl

    return _impl(*args, **kwargs)


def _transcript_path(*args, **kwargs):
    from beyin.audio_pipeline import _transcript_path as _impl

    return _impl(*args, **kwargs)


def fetch_article(*args, **kwargs):
    from beyin.ingester import fetch_article as _fetch_article

    return _fetch_article(*args, **kwargs)


def resolve_article_ingestion(*args, **kwargs):
    from beyin.ingester import resolve_article_ingestion as _resolve_article_ingestion

    return _resolve_article_ingestion(*args, **kwargs)


def load_text_like_source(*args, **kwargs):
    from beyin.ingester import load_text_like_source as _load_text_like_source

    return _load_text_like_source(*args, **kwargs)


def load_document_source(*args, **kwargs):
    from beyin.ingester import load_document_source as _load_document_source

    return _load_document_source(*args, **kwargs)


def run_query(*args, **kwargs):
    from beyin.query import run_query as _run_query

    return _run_query(*args, **kwargs)


def retrieve_evidence(*args, **kwargs):
    from beyin.query import retrieve_evidence as _retrieve_evidence

    return _retrieve_evidence(*args, **kwargs)


def multi_retrieve_evidence(*args, **kwargs):
    from beyin.query import multi_retrieve_evidence as _multi_retrieve_evidence

    return _multi_retrieve_evidence(*args, **kwargs)


def _source_label(*args, **kwargs):
    from beyin.query import _source_label as _query_source_label

    return _query_source_label(*args, **kwargs)


def get_collection(*args, **kwargs):
    from beyin.store import get_collection as _get_collection

    return _get_collection(*args, **kwargs)


def embed_and_store(*args, **kwargs):
    from beyin.store import embed_and_store as _embed_and_store

    return _embed_and_store(*args, **kwargs)


def purge_removed_sources(*args, **kwargs):
    from beyin.store import purge_removed_sources as _purge_removed_sources

    return _purge_removed_sources(*args, **kwargs)


def transcribe_audio(*args, **kwargs):
    from beyin.transcriber import transcribe_audio as _transcribe_audio

    return _transcribe_audio(*args, **kwargs)




def _render_usage_guidance(summary: Optional[dict] = None, *, err: bool = False) -> None:
    """Render the shared human onboarding guidance across home, status, and errors."""
    def _echo(line: str = "") -> None:
        typer.echo(line, err=err)

    pack_name = _pack_label(summary)
    status = summary.get("status") if summary else None
    lifecycle_command = human_guidance_command(summary) if summary else None
    build_cmd = f"beyin build {pack_name}" if summary else "beyin build <pack>"
    status_cmd = f"beyin status {pack_name}" if summary else "beyin status <pack>"

    def _agent_block() -> None:
        _echo(f"  {bold('Use with agent')}")
        _echo(f"    {dim('1.')} beyin mcp-server")
        _echo(f"    {dim('2.')} beyin create")
        _echo(f"    {dim('3.')} {build_cmd}")
        if summary:
            if status == "blocked":
                _echo(f"    {yellow('!')}  Unblock: {lifecycle_command}")
            elif status in {"new", "needs-build", "partially-ready", "error"}:
                _echo(f"    {dim('->')} Next: {lifecycle_command}")
            elif status == "ready":
                _echo(f"    {green('OK')} {pack_name} is ready for agent use")

    def _local_block() -> None:
        _echo(f"  {bold('Use with local model')}")
        _echo(f"    {dim('1.')} Install Ollama")
        _echo(f"    {dim('2.')} {status_cmd}")
        _echo(f"    {dim('3.')} beyin create")
        _echo(f"    {dim('4.')} {build_cmd}")
        if summary and status == "ready":
            _echo(f'    {dim("5.")} beyin query {pack_name} "question"')

    for i, fn in enumerate([_agent_block, _local_block]):
        if i:
            _echo()
        fn()


def _render_home_screen() -> None:
    """Show the default introductory screen for no-argument CLI entry."""
    summaries = list_packs(_PACKS_DIR, _pack_readiness_details)
    settings = load_settings()

    typer.echo(f"  {bold('beyin')} {dim(f'v{__version__}')}")
    typer.echo("")

    # Settings section
    typer.echo(f"  {bold('Settings')}")
    typer.echo(f"  {dim('─' * 38)}")
    settings_rows = [
        ("Transcription", settings.preferred_transcription_backend),
        ("Whisper model", settings.preferred_whisper_model),
        ("Local model", settings.preferred_llm_model),
    ]
    for line in render_rows(settings_rows):
        typer.echo(line)
    typer.echo("")
    for line in _render_dependency_section():
        typer.echo(line)
    typer.echo("")

    # Packs section
    typer.echo(f"  {bold('Installed packs')}")
    typer.echo(f"  {dim('─' * 38)}")
    if not summaries:
        typer.echo(f"  {dim('No packs installed yet.')}")
    else:
        _render_pack_table(summaries, limit=6)
        if len(summaries) > 6:
            typer.echo(f"  {dim(f'...and {len(summaries) - 6} more')}")
    typer.echo("")

    # Footer
    _footer = (
        dim("Run 'beyin help' for all commands")
        + "  "
        + dim("·")
        + "  "
        + dim("beyin settings")
        + "  "
        + dim("·")
        + "  "
        + dim("beyin create")
    )
    typer.echo(f"  {_footer}")


def _run_initial_setup_flow() -> bool:
    """Run the interactive first-run setup and return True when it handled output."""
    from beyin.interactive import run_initial_setup_flow as interactive_run_initial_setup_flow

    return interactive_run_initial_setup_flow(prompt_backend=load_prompt_backend())


def run_authoring_menu() -> bool:
    """Run the TTY-only create/import/manage chooser for no-arg interactive sessions."""
    from beyin.interactive import run_authoring_menu as interactive_run_authoring_menu

    summaries = list_packs(_PACKS_DIR, _pack_readiness_details)
    return interactive_run_authoring_menu(
        packs_dir=_PACKS_DIR,
        prompt_backend=load_prompt_backend(),
        import_handler=add,
        pack_summaries=summaries,
    )


def run_create_flow() -> bool:
    """Run the interactive create flow behind the direct `beyin create` command."""
    from beyin.interactive import run_create_flow as interactive_run_create_flow

    return interactive_run_create_flow(
        packs_dir=_PACKS_DIR,
        prompt_backend=load_prompt_backend(),
    )


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Render the home screen when beyin runs without a subcommand."""
    if ctx.invoked_subcommand is None:
        existing = list_packs(_PACKS_DIR, _pack_readiness_details)
        if needs_initial_setup() and is_interactive_session() and not existing:
            _run_initial_setup_flow()
            return
        if is_interactive_session():
            # Inventory-first: show the home table when packs are already installed.
            # Only route to the authoring menu on an empty inventory.
            if existing:
                _render_home_screen()
                return
            if run_authoring_menu():
                return
        _render_home_screen()


def _settings_display_rows(settings) -> list[tuple[str, str]]:
    """Return label/value rows for the current settings table."""
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


def _dependency_display_rows(settings=None) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str]]:
    """Return capability-aware dependency rows plus hard failures."""
    current = settings or load_settings()
    failures: list[str] = []
    capabilities = set(current.enabled_capabilities or [])
    selected_file_types = set(current.enabled_local_file_types or [])

    runtime_rows: list[tuple[str, str]] = []
    if capabilities.intersection({"youtube", "podcasts"}):
        if shutil.which("ffmpeg"):
            ffmpeg_status = "found"
        else:
            ffmpeg_status = "NOT FOUND  →  brew install ffmpeg"
            failures.append("ffmpeg")
        runtime_rows.append(("Audio/video", f"ffmpeg: {ffmpeg_status}"))

    if "youtube" in capabilities:
        ok, version = _ytdlp_version_ok()
        if ok:
            ytdlp_status = f"found ({version})"
        elif version == "unknown":
            ytdlp_status = "NOT FOUND  →  pip install --upgrade yt-dlp"
            failures.append("yt-dlp")
        else:
            ytdlp_status = f"OUTDATED ({version} < {_YTDLP_MIN_VERSION})  →  pip install --upgrade yt-dlp"
            failures.append("yt-dlp")
        runtime_rows.append(("YouTube", f"yt-dlp: {ytdlp_status}"))

    if "local_query" in capabilities:
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
        if extension not in selected_file_types:
            continue
        try:
            __import__(module)
            status = f"{module}: found"
        except ImportError:
            status = f"{module}: not installed  →  {hint}"
        file_type_rows.append((label, status))

    return runtime_rows, file_type_rows, failures


def _render_dependency_section(*, title: str = "Dependencies", settings=None) -> list[str]:
    runtime_rows, file_type_rows, _ = _dependency_display_rows(settings=settings)
    lines = [f"  {bold(title)}", f"  {dim('─' * 38)}"]
    if runtime_rows:
        lines.extend(render_rows(runtime_rows))
    else:
        lines.append(f"  {dim('No extra runtime tools selected.')}")
    if file_type_rows:
        lines.append("")
        lines.extend(render_rows(file_type_rows))
    return lines


@app.command(name="settings", cls=BeyinCommand)
def settings_command() -> None:
    """Show current settings and edit them interactively in a terminal."""
    from beyin.settings import BeyinSettings
    InteractiveAbort = _interactive_abort_type()

    current = load_settings()

    # Always show current settings as a table
    for line in render_header(version=__version__, step="beyin Settings"):
        typer.echo(line)
    typer.echo("")
    for line in render_rows(_settings_display_rows(current)):
        typer.echo(line)
    typer.echo("")
    for line in _render_dependency_section():
        typer.echo(line)
    typer.echo("")

    if not is_interactive_session():
        _hint = dim("Run 'beyin settings' in a terminal to edit.")
        typer.echo(f"  {_hint}")
        return

    # TTY: inline edit menu loop
    backend = load_prompt_backend()

    # Work on a mutable copy of the settings fields
    staged = BeyinSettings(
        version=current.version,
        setup_completed=current.setup_completed,
        enabled_capabilities=list(current.enabled_capabilities),
        enabled_local_file_types=list(current.enabled_local_file_types),
        preferred_transcription_backend=current.preferred_transcription_backend,
        preferred_whisper_model=current.preferred_whisper_model,
        preferred_llm_model=current.preferred_llm_model,
    )

    _DIVIDER = {"value": "__divider__", "name": "──────────────────────"}
    _SAVE = {"value": "__save__", "name": "Save and exit"}
    _EXIT = {"value": "__exit__", "name": "Exit without saving"}

    try:
        while True:
            choices = [
                {"value": "transcription", "name": f"Transcription backend ({staged.preferred_transcription_backend})"},
                {"value": "whisper_model", "name": f"Whisper model         ({staged.preferred_whisper_model})"},
                {"value": "llm_model", "name": f"Local model           ({staged.preferred_llm_model})"},
                _DIVIDER,
                _SAVE,
                _EXIT,
            ]
            selection = _interactive_select(
                backend,
                "What would you like to change?",
                choices=choices,
            )

            if selection == "__save__":
                save_settings(staged)
                typer.echo(f"  {green('OK')} {bold('Settings saved.')}")
                return

            if selection == "__exit__" or selection == "__divider__":
                typer.echo("  Settings unchanged.")
                return

            if selection == "llm_model":
                try:
                    typer.echo(f"  {dim('← Back  (Ctrl+C)')}")
                    new_val = _interactive_text(
                        backend,
                        "Local model",
                        default=staged.preferred_llm_model,
                    )
                    staged.preferred_llm_model = new_val or staged.preferred_llm_model
                except InteractiveAbort:
                    continue

            elif selection == "whisper_model":
                choices = available_setup_choices()
                new_val = _interactive_select(
                    backend,
                    "Whisper model",
                    choices=[
                        _interactive_choice(
                            value,
                            value,
                            help_text=_interactive_model_description(value),
                        )
                        for value in choices["whisper_models"]
                    ] + [
                        {"value": "__back__", "name": "← Back"},
                    ],
                    default=staged.preferred_whisper_model,
                )
                if new_val != "__back__":
                    staged.preferred_whisper_model = new_val

            elif selection == "transcription":
                new_val = _interactive_select(
                    backend,
                    "Transcription backend",
                    choices=[
                        {"value": "mlx-whisper", "name": "mlx-whisper"},
                        {"value": "faster-whisper", "name": "faster-whisper"},
                        {"value": "__back__", "name": "← Back"},
                    ],
                    default=staged.preferred_transcription_backend,
                )
                if new_val != "__back__":
                    staged.preferred_transcription_backend = new_val

    except InteractiveAbort:
        typer.echo("  Settings unchanged.")
        return


@app.command(cls=BeyinCommand)
def help(
    ctx: typer.Context,
) -> None:
    """Show top-level help using a friendly command alias."""
    term_w = min(shutil.get_terminal_size((80, 24)).columns, 100)

    typer.echo(f"{bold('beyin')} {dim(f'v{__version__}')}")
    typer.echo("")
    typer.echo(f"{dim('Tip: append --help to any command for usage and options, e.g. beyin build --help')}")
    typer.echo("")

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Pack lifecycle",
            [
                ("create", "Create a new pack"),
                ("add", "Import a pack.yaml from a path, URL, or id"),
                ("build", "Build or incrementally update a pack"),
                ("update", "Refresh an installed pack from its remembered origin"),
                ("remove", "Remove an installed pack"),
            ],
        ),
        (
            "Inspect and retrieve",
            [
                ("list", "List installed packs"),
                ("status", "Inspect one pack in detail"),
                ("query", "Ask one local question against a pack"),
            ],
        ),
        (
            "Manage sources",
            [
                ("add-source", "Append one or more sources to a pack"),
                ("remove-source", "Remove one or more sources from a pack"),
            ],
        ),
        (
            "Agent integration",
            [
                ("mcp-server", "Run the local MCP server for agents"),
            ],
        ),
        (
            "Settings and support",
            [
                ("settings", "View or edit beyin settings"),
                ("check-deps", "Check ffmpeg and yt-dlp availability"),
                ("about", "Show a short beyin overview"),
                ("help", "Show this command guide"),
            ],
        ),
    ]

    def _render_command_table(rows: list[tuple[str, str]]) -> list[str]:
        cmd_w = min(14, max(len(name) for name, _ in rows))
        desc_w = max(20, term_w - cmd_w - 8)

        if term_w >= 72:
            lines = []
            for name, description in rows:
                wrapped = wrap_text(description, desc_w)
                first = wrapped[0] if wrapped else ""
                lines.append(f"{name.ljust(cmd_w)}  {first}")
                for line in wrapped[1:]:
                    lines.append(f"{' ' * cmd_w}  {line}")
            return lines

        compact_lines: list[str] = []
        for idx, (name, description) in enumerate(rows):
            compact_lines.append(f"{bold(name)}")
            for line in wrap_text(description, max(20, term_w - 4)):
                compact_lines.append(f"  {dim(line)}")
            if idx < len(rows) - 1:
                compact_lines.append(f"{dim('─' * max(12, term_w - 4))}")
        return compact_lines

    for title, commands in sections:
        typer.echo(f"{bold(title + ':')}")
        for line in _render_command_table(commands):
            typer.echo(line)
        typer.echo("")

    typer.echo(f"{dim('Project')}  https://github.com/buralog/beyin")


@app.command(cls=BeyinCommand)
def about() -> None:
    """Show a short overview of beyin."""
    typer.echo(f"{bold('beyin')} {dim(f'v{__version__}')}")
    typer.echo("")
    typer.echo("beyin turns your own sources into local knowledge packs.")
    typer.echo("Connect them to coding agents over MCP so tools like Codex or Claude Code can query them")
    typer.echo("and answer questions with your own context.")
    typer.echo("")
    typer.echo("You can also use beyin directly on your machine.")
    typer.echo("Ask questions with your configured local model, such as Ollama, and get answers")
    typer.echo("grounded in the sources you added.")
    typer.echo("")
    for line in render_review(
        "Best For",
        [
            ("Agents", "Expose packs over MCP for evidence retrieval and workflow integration"),
            ("Direct use", "Ask one-off questions locally with your configured model"),
            ("Owned context", "Keep your retrieval layer local instead of pushing source data elsewhere"),
        ],
    ):
        typer.echo(line[2:] if line.startswith("  ") else line)
    typer.echo("")
    for line in render_meta(
        [
            "Open source",
            "https://github.com/buralog/beyin",
        ]
    ):
        typer.echo(line[2:] if line.startswith("  ") else line)




def _resolve_pack_dir(
    pack: str,
    *,
    missing_next_step: str = "beyin add <path-or-url-or-id>",
    missing_note: Optional[str] = None,
    machine_command: Optional[str] = None,
) -> Path:
    """Resolve pack name to directory under ~/.beyin/."""
    pack_dir = _PACKS_DIR / pack
    if not pack_dir.exists():
        if machine_command:
            details = {"next_action": missing_next_step}
            if missing_note:
                details["note"] = missing_note
            raise MachineExit.precondition(
                "pack_not_found",
                f"Pack '{pack}' is not installed.",
                pack=pack,
                details=details,
            )
        typer.echo(f"Error: Pack '{pack}' is not installed.", err=True)
        typer.echo(f"Next step: {missing_next_step}", err=True)
        if missing_note:
            typer.echo(missing_note, err=True)
        raise typer.Exit(code=1)
    return pack_dir



def _pack_readiness_details(config) -> dict[str, list[str]]:
    """Return build-time blocker/warning details for one installed pack."""
    blockers: list[str] = []
    warnings: list[str] = []

    if _has_youtube_sources(config):
        youtube_issue = _youtube_build_issue()
        if youtube_issue is not None:
            blockers.append(youtube_issue)

    if _has_audio_sources(config) and not _check_ffmpeg_available():
        blockers.append(
            "ffmpeg is required for audio builds. Install: brew install ffmpeg"
        )

    return {"blockers": blockers, "warnings": warnings}


def _render_next_step(command: str, reason: str, *, err: bool = False) -> None:
    """Print one explicit next command and why it matters."""
    typer.echo(f"Next step: {command}", err=err)
    typer.echo(reason, err=err)



def _render_query_output(result: dict) -> None:
    """Print the LLM answer followed by visible sources."""
    if result.get("coverage_warning"):
        typer.echo(f"Warning: {result['coverage_warning']}\n")
    typer.echo(result["answer"])
    if not result["sources"]:
        return

    typer.echo("\nSources:")
    grouped: dict[tuple[str, str], list[dict]] = {}
    ordered_keys: list[tuple[str, str]] = []
    for source in result["sources"]:
        key = (source.get("title", "Unknown"), source.get("url", ""))
        if key not in grouped:
            ordered_keys.append(key)
            grouped[key] = []
        grouped[key].append(source)

    for index, key in enumerate(ordered_keys, start=1):
        title, url = key
        typer.echo(f"  [{index}] {title} — {url}")
        ranges: list[str] = []
        seen_ranges: set[str] = set()
        for source in grouped[key]:
            start = source.get("timestamp_start")
            end = source.get("timestamp_end")
            if start is None or end is None:
                continue
            label = _source_label(
                {
                    "title": title,
                    "url": url,
                    "timestamp_start": start,
                    "timestamp_end": end,
                }
            )
            range_label = label.split("(")[-1].rstrip(")")
            if range_label in seen_ranges:
                continue
            seen_ranges.add(range_label)
            ranges.append(range_label)
        for range_label in ranges:
            typer.echo(f"      - {range_label}")


def _source_rows(config, state: dict) -> list[tuple[str, str, str]]:
    """Return (icon, label, detail) for each source in config."""
    processed = state.get("processed", {})
    audio_steps = state.get("audio_steps", {})
    rows = []
    for source in config.sources:
        url = source.url
        sid = canonical_source_id(url)
        source_type = detect_source_type(url)

        if sid in processed:
            entry = processed[sid]
            if entry.get("status") == "done":
                rows.append((green("✓"), entry.get("title") or url, ""))
            else:
                reason = entry.get("reason", "failed")
                rows.append((red("✗"), entry.get("title") or url, dim(reason[:50])))
        elif sid in audio_steps:
            entry = audio_steps[sid]
            stages = entry.get("stages", {})
            title = entry.get("title") or url
            rows.append((_episode_icon(stages), title, ""))
        elif source_type in {"youtube", "podcast"} and audio_steps:
            embedded = sum(1 for e in audio_steps.values() if e.get("stages", {}).get("embedded"))
            total = len(audio_steps)
            rows.append((green("✓") if embedded == total else yellow("~"), url, dim(f"{embedded}/{total} episodes")))
        else:
            rows.append((dim("·"), url, dim("not built")))
    return rows


def _parse_episode_selection(raw: str, audio_eps: list[dict]) -> list[dict]:
    """Parse a selection string like '1,3,5' or '1-5' or 'all' against audio_eps."""
    if raw == "all":
        return audio_eps
    indexes: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                indexes.update(range(int(start), int(end) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            indexes.add(int(part))
    selected = [ep for i, ep in enumerate(audio_eps, start=1) if i in indexes]
    if not selected:
        typer.echo("  No valid episodes selected — skipping audio downloads.")
    return selected


def _select_episodes_for_download(
    episodes: list[dict],
    source_url: str,
    label: str = "episode",
) -> list[dict]:
    """Separate auto-include entries (transcript/article) from audio-requiring ones.
    Prompt user to pick which audio entries to download. Returns filtered list."""
    text_eps = [ep for ep in episodes if ep.get("transcript_text", "").strip() or ep.get("mode") == "article"]
    audio_eps = [ep for ep in episodes if not ep.get("transcript_text", "").strip() and ep.get("mode") != "article"]

    if not audio_eps:
        return episodes  # nothing needs downloading — no prompt needed

    total = len(episodes)
    typer.echo(f"\nFound {total} {label}(s): {source_url}")
    if text_eps:
        typer.echo(f"  {len(text_eps)} {label}(s) have transcripts and will be processed automatically.")
    typer.echo(f"  {len(audio_eps)} {label}(s) require audio download + transcription:\n")
    for i, ep in enumerate(audio_eps, start=1):
        typer.echo(f"  {i}. {ep.get('title', 'Unknown')}")

    typer.echo(
        f"\nEnter {label} numbers to download (e.g. 1,3,5), a range (e.g. 1-5), "
        "'all', or 'skip' to skip audio downloads:"
    )
    raw = typer.prompt("Selection", default="skip").strip().lower()

    selected_audio = [] if raw == "skip" else _parse_episode_selection(raw, audio_eps)
    typer.echo("")
    return text_eps + selected_audio


def _prompt_create_config() -> PackConfig:
    """Collect the non-TTY fallback guided creation inputs."""
    source_input = typer.prompt("Source URL or local path").strip()
    name = typer.prompt("Pack name").strip()
    if not re.match(r"^[\w.-]+$", name):
        typer.echo(
            f"Error: Pack name '{name}' contains invalid characters. "
            "Only alphanumerics, hyphens, underscores, and dots are allowed.",
            err=True,
        )
        raise typer.Exit(code=1)

    description = typer.prompt("Short description").strip()
    try:
        return build_new_pack_config(
            name=name,
            description=description,
            source_input=source_input,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)


def _write_pack_yaml_from_source(
    resolved: dict[str, str],
    destination: Path,
) -> tuple[Path, object]:
    """Resolve a validated YAML source and write it into the managed pack dir."""
    is_url = resolved["resolved"].startswith(("http://", "https://"))
    tmp_file = None
    try:
        if is_url:
            fd, tmp_file = tempfile.mkstemp(suffix=".yaml")
            os.close(fd)
            try:
                urllib.request.urlretrieve(resolved["resolved"], tmp_file)
            except Exception as exc:
                typer.echo(
                    f"Error: Failed to download {resolved['resolved']}: {exc}",
                    err=True,
                )
                raise typer.Exit(code=1)
            yaml_path = Path(tmp_file)
        else:
            yaml_path = Path(resolved["resolved"]).expanduser().resolve()
            if not yaml_path.exists():
                typer.echo(f"Error: '{resolved['source']}' not found.", err=True)
                raise typer.Exit(code=1)

        try:
            config = _load_config_from_file(yaml_path)
        except Exception as exc:
            typer.echo(f"Error: Invalid pack.yaml: {exc}", err=True)
            raise typer.Exit(code=1)

        if not re.match(r"^[\w.-]+$", config.id):
            typer.echo(
                f"Error: Pack id '{config.id}' contains invalid characters. "
                "Only alphanumerics, hyphens, underscores, and dots are allowed.",
                err=True,
            )
            raise typer.Exit(code=1)

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(yaml_path, destination)
        return yaml_path, config
    finally:
        if tmp_file is not None:
            Path(tmp_file).unlink(missing_ok=True)


def _runtime_update_status(pack: str, state: dict, current_hash: str) -> tuple[str, str | None]:
    """Return a short runtime-status label and an explicit follow-up command, if any."""
    result = str(state.get("last_build_result") or "").strip() or "not-built"
    built_hash = state.get("last_built_pack_hash")
    if result == "success" and built_hash == current_hash:
        return "ready", None
    if built_hash and built_hash != current_hash:
        return "stale", f"beyin build {pack}"
    if result in {"failed", "mixed", "completed_with_issues", "error"}:
        return result, f"beyin build {pack}"
    if result == "success":
        return "success-with-older-definition", f"beyin build {pack}"
    return result, f"beyin build {pack}"


@app.command(cls=BeyinCommand)
def create() -> None:
    """Guide the user through creating a new pack without hand-editing YAML."""
    if is_interactive_session():
        if not run_create_flow():
            raise typer.Exit(code=1)
        return

    config = _prompt_create_config()
    pack_dir = _PACKS_DIR / config.id
    if pack_dir.exists():
        typer.echo(
            f"Error: Pack '{config.id}' already exists.\n"
            f"Choose a new name or run `beyin update {config.id}`.",
            err=True,
        )
        raise typer.Exit(code=1)

    write_public_config(config, pack_dir / "pack.yaml")

    typer.echo(f"Created pack '{config.id}'.")
    typer.echo(f"Source saved: {config.sources[0].url}")
    typer.echo("")
    _render_next_step(
        f"beyin build {config.id}",
        "Build indexes the source into local expert memory.",
    )


@app.command(cls=BeyinCommand)
def build(
    pack: str = typer.Argument(..., help="Pack name (directory under ~/.beyin/)"),
    sources: Optional[List[str]] = typer.Option(
        None,
        "--source",
        "-s",
        help="Build only selected current sources by index, range, or visible text match. Repeat to include multiple selections.",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Whisper model size: tiny/tiny.en/base/base.en/small/small.en/medium/medium.en/large",
    ),
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Whisper language code (e.g. 'en', 'fr', 'es'). Default: auto-detect",
    ),
    reset: bool = typer.Option(
        False,
        "--reset",
        help="Clear generated runtime artifacts before rebuilding. Preserves pack.yaml and origin.json.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show per-episode download, transcribe, and embed lines.",
    ),
):
    """Build or incrementally update a pack from its pack.yaml sources.

    Examples:
      - Full build:      beyin build <pack>
      - One source:      beyin build <pack> --source 2
      - Source range:    beyin build <pack> --source 1-3
      - Text match:      beyin build <pack> --source "WWDC"
      - Tiny model:      beyin build <pack> --model tiny
      - Set language:    beyin build <pack> --language tr
      - Reset runtime:   beyin build <pack> --reset
      - Verbose build:   beyin build <pack> --verbose
    """
    pack_dir = _resolve_pack_dir(pack)
    if reset:
        reset_pack_runtime(pack_dir)
    config = load_config(pack_dir)
    state = load_state(pack_dir)
    current_pack_hash = pack_config_hash(pack_dir)
    full_config = config
    selected_sources = None
    if sources:
        source_rows = serialize_pack_sources(config, state)
        try:
            config, selected_sources = select_sources_from_pack(
                config,
                list(sources),
                source_rows=source_rows,
            )
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1)
        typer.echo(
            f"Building {len(config.sources)} selected source(s) from '{full_config.id}' "
            f"(out of {len(full_config.sources)} total)."
        )
    build_defaults = resolve_build_defaults(
        cli_model=model,
        cli_language=language,
    )

    # SAF-01: enforce model provenance before any ChromaDB write
    check_model_provenance(state, config.embedding_model, pack_name=config.id)
    if _has_audio_sources(config):
        check_transcription_provenance(
            state,
            current_model=str(build_defaults["model"]),
            current_language=build_defaults["language"],
            pack_name=config.id,
        )
    save_state(pack_dir, state)  # persist model registration on first build

    model_size = build_defaults["model"]
    # Lazy-loaded: only initialized when we actually need to embed something.
    _model_obj = None
    _collection = None
    _embedding_resources_announced = False

    def _get_embed_resources():
        nonlocal _model_obj, _collection, _embedding_resources_announced
        if _model_obj is None:
            if not verbose and not _embedding_resources_announced:
                typer.echo(f"  [embed] Loading embedding model: {config.embedding_model}")
                _embedding_resources_announced = True
            _model_obj = load_model(config.embedding_model)
            _collection = get_collection(pack_dir, config.id)
        return _model_obj, _collection

    # Purge chunks from sources that have been removed from pack.yaml.
    # Uses the full config (not the partial selection) so all active URLs are known.
    chroma_path = pack_dir / "chroma"
    if chroma_path.exists():
        _purge_collection = get_collection(pack_dir, full_config.id)
        active_urls = {s.url for s in full_config.sources}
        purged = purge_removed_sources(_purge_collection, active_urls)
        if purged:
            for url in purged:
                typer.echo(f"  [purge] Removed stale chunks for: {url}")

    audio_dir = pack_dir / "audio"
    transcripts_dir = pack_dir / "transcripts"
    audio_dir.mkdir(exist_ok=True)
    transcripts_dir.mkdir(exist_ok=True)

    report = BuildReport()
    youtube_issue = _youtube_build_issue()
    ffmpeg_available = _check_ffmpeg_available()
    for source in config.sources:
        source_url = source.url
        effective_limit = source.limit if source.limit is not None else config.episode_limit
        source_type = detect_source_type(source_url)

        if source_type in {"article", "local_text", "local_document", "local_file", "pack"}:
            if is_processed(state, source_url):
                typer.echo(f"  [skip] {source_url}")
                report.record(source_url[:40], "skipped", skipped=1)
                continue

            failure_reason = ""
            if source_type == "article":
                typer.echo(f"  [fetch] {source_url}")
                resolved = resolve_article_ingestion(source_url)
                if resolved is None:
                    result = None
                    failure_reason = "trafilatura extraction returned None"
                    failure_message = f"Could not extract text from {source_url} — skipping"
                elif resolved["mode"] in {"article", "transcript"}:
                    result = (resolved["text"], resolved["title"], resolved.get("metadata_url") or source_url)
                    failure_message = ""
                elif resolved["mode"] == "podcast_audio":
                    result = resolved
                    failure_message = ""
                else:
                    result = None
                    failure_reason = resolved.get("reason", "podcast episode page missing transcript and audio")
                    failure_message = f"{failure_reason} — skipping"
            elif source_type == "local_text":
                typer.echo(f"  [load] {source_url}")
                try:
                    result = load_text_like_source(source_url)
                except FileNotFoundError:
                    result = None
                    failure_reason = f"missing local source: {source_url}"
                    failure_message = f"Missing local source: {source_url} — skipping"
                except ValueError as exc:
                    result = None
                    failure_reason = str(exc)
                    failure_message = f"{exc} — skipping"
                else:
                    failure_message = ""
            elif source_type == "local_document":
                typer.echo(f"  [load] {source_url}")
                try:
                    result = load_document_source(source_url)
                except FileNotFoundError:
                    result = None
                    failure_reason = f"missing local source: {source_url}"
                    failure_message = f"Missing local source: {source_url} — skipping"
                except ImportError as exc:
                    result = None
                    failure_reason = str(exc)
                    failure_message = f"{exc} — skipping"
                except ValueError as exc:
                    result = None
                    failure_reason = str(exc)
                    failure_message = f"{exc} — skipping"
                else:
                    failure_message = ""
            elif source_type == "pack":
                result = None
                failure_reason = "pack config sources belong on beyin add"
                failure_message = (
                    "Pack config sources belong on `beyin add <path-or-url-or-id>`, not build sources."
                )
            else:
                result = None
                failure_reason = f"unsupported local source type: {source_url}"
                failure_message = f"Unsupported local source type: {source_url} — skipping"

            if result is None:
                typer.echo(
                    f"  [warn] {failure_message}",
                    err=True,
                )
                mark_failed(state, source_url, reason=failure_reason)
                save_state(pack_dir, state)
                report.record(source_url[:40], "failed", failure_reason=failure_reason)
                continue

            if source_type == "article" and isinstance(result, dict) and result.get("mode") == "podcast_audio":
                episode_title = result.get("title") or source_url
                source_id = canonical_source_id(source_url)
                transcript_path = _transcript_path(transcripts_dir, source_id)
                legacy_transcript_path = _legacy_transcript_path(transcripts_dir, source_url)
                ffmpeg_available = _check_ffmpeg_available()
                if not ffmpeg_available:
                    failure_reason = (
                        "ffmpeg is required for audio builds. "
                        "Install: brew install ffmpeg or visit https://ffmpeg.org/download.html"
                    )
                    typer.echo(f"  [warn] {failure_reason}", err=True)
                    mark_failed(state, source_url, reason=failure_reason)
                    save_state(pack_dir, state)
                    report.record(episode_title, "failed", failure_reason=failure_reason)
                    continue

                check_transcription_provenance(
                    state,
                    current_model=str(build_defaults["model"]),
                    current_language=build_defaults["language"],
                    pack_name=config.id,
                )
                save_state(pack_dir, state)

                audio_url = result["audio_url"]
                audio_path = download_podcast_audio(audio_url, audio_dir, episode_title)
                if audio_path is None:
                    failure_reason = "download failed after retry"
                    typer.echo(
                        f"  [warn] Download failed for {episode_title} — skipping",
                        err=True,
                    )
                    mark_failed(state, source_url, reason=failure_reason)
                    save_state(pack_dir, state)
                    report.record(episode_title, "failed", failure_reason=failure_reason)
                    continue

                mark_audio_step(state, source_url, "downloaded", episode_title, source_id=source_id)
                save_state(pack_dir, state)
                typer.echo(f"  [transcribe] {episode_title}")
                segments = transcribe_audio(
                    audio_path,
                    model_size=model_size,
                    language=language,
                    verbose=verbose,
                )
                if not segments:
                    failure_reason = "transcription returned empty"
                    typer.echo(
                        f"  [warn] Transcription failed for {episode_title} — skipping",
                        err=True,
                    )
                    mark_empty(state, source_url, failure_reason, source_id=source_id, title=episode_title)
                    save_state(pack_dir, state)
                    report.record(episode_title, "empty", failure_reason=failure_reason)
                    continue

                _save_transcript_segments(transcript_path, segments)
                mark_audio_step(state, source_url, "transcribed", episode_title, source_id=source_id)
                save_state(pack_dir, state)
                chunks, range_metadata = _chunk_transcript_segments(segments)
                if not chunks:
                    failure_reason = "no indexable transcript chunks"
                    typer.echo(
                        f"  [warn] No indexable transcript chunks for {episode_title} — skipping",
                        err=True,
                    )
                    mark_empty(state, source_url, failure_reason, source_id=source_id, title=episode_title)
                    save_state(pack_dir, state)
                    report.record(episode_title, "empty", failure_reason=failure_reason)
                    continue

                metadatas = []
                for chunk_range in range_metadata:
                    metadata = {
                        "url": result.get("metadata_url") or source_url,
                        "title": episode_title,
                        "source_id": source_id,
                    }
                    metadata.update(chunk_range)
                    metadatas.append(metadata)
                if not verbose:
                    typer.echo(f"  [embed] {episode_title}")
                model_obj, collection = _get_embed_resources()
                new_count = embed_and_store(collection, model_obj, chunks, metadatas, url=source_id)
                mark_audio_step(state, source_url, "embedded", episode_title, source_id=source_id)
                save_state(pack_dir, state)
                if verbose:
                    typer.echo(f"  [embed] {episode_title} — {new_count} chunks")
                report.record(episode_title, "done", new=new_count)
                continue

            if source_type == "article":
                text, title, metadata_url = result
            else:
                text, title = result
                metadata_url = source_url
            chunks = chunk_text(text)
            metadatas = [{"url": metadata_url, "title": title} for _ in chunks]
            model_obj, collection = _get_embed_resources()
            new_count = embed_and_store(collection, model_obj, chunks, metadatas, url=source_url)
            mark_processed(state, source_url, title)
            save_state(pack_dir, state)
            if verbose:
                typer.echo(f"  [embed] {title} — {new_count} chunks")
            report.record(title, "done", new=new_count)

        else:  # youtube, podcast, or local media
            if source_type == "youtube":
                if youtube_issue:
                    typer.echo(f"  [warn] {youtube_issue}", err=True)
                    report.record(source_url[:40], "blocked", failure_reason=youtube_issue)
                    continue
                if not ffmpeg_available:
                    ffmpeg_reason = (
                        "ffmpeg is required for audio builds. "
                        "Install: brew install ffmpeg or visit https://ffmpeg.org/download.html"
                    )
                    typer.echo(f"  [warn] {ffmpeg_reason}", err=True)
                    report.record(source_url[:40], "blocked", failure_reason=ffmpeg_reason)
                    continue
                playlist_title, episodes = list_youtube_episodes(source_url, effective_limit)
                if playlist_title:
                    state.setdefault("playlist_titles", {})[source_url] = playlist_title
            elif source_type == "podcast":
                playlist_title, episodes = None, list_podcast_episodes(source_url, effective_limit)
            elif source_type == "podcast_audio":
                playlist_title = None
                episodes = [{"url": source_url, "title": source.title or source_url}]
            else:
                local_path = Path(source_url).expanduser()
                title = source.title or local_path.stem
                playlist_title = None
                episodes = [{"url": str(local_path), "title": title}]

            if not episodes:
                typer.echo(f"  [warn] No episodes found for {source_url}", err=True)
                continue

            total = len(episodes)
            for idx, episode in enumerate(episodes, start=1):
                episode_url = episode["url"]
                transcript_text = episode.get("transcript_text", "").strip()
                episode_title = episode.get("title", "Unknown")
                source_id = canonical_source_id(episode, source_type=source_type)
                episode_counter = f"Episode {idx}/{total}: {episode_title}"

                # Skip if fully embedded already
                if is_audio_step_done(state, episode_url, "embedded", source_id=source_id):
                    typer.echo(f"  [skip] {episode_title}")
                    report.record(episode_title, "skipped", skipped=1)
                    continue

                # Step 1: download
                audio_path = None
                ep_step = get_audio_step(state, episode_url, source_id=source_id)
                # Always scan for existing audio files — handles interrupted builds where
                # the file was saved but state wasn't (avoids unnecessary re-downloads).
                candidates = _candidate_audio_paths(audio_dir, source_id, episode)
                if candidates:
                    candidate = candidates[0]
                    if candidate.exists() and candidate.stat().st_size >= 10_000:
                        audio_path = candidate
                        if not ep_step.get("stages", {}).get("downloaded"):
                            # File exists but state wasn't saved — recover
                            mark_audio_step(
                                state,
                                episode_url,
                                "downloaded",
                                episode_title,
                                source_id=source_id,
                                parent_source_url=source_url,
                            )
                            save_state(pack_dir, state)

                if episode.get("mode") == "article":
                    typer.echo(f"  [fetch] {episode_counter}")
                    article_result = fetch_article(episode_url)
                    if article_result is None:
                        typer.echo(f"  [warn] Could not extract text from {episode_url} — skipping", err=True)
                        mark_failed(state, episode_url, "article fetch failed", source_id=source_id, title=episode_title, parent_source_url=source_url)
                        save_state(pack_dir, state)
                        report.record(episode_title, "failed", failure_reason="article fetch failed")
                        continue
                    art_text, art_title = article_result
                    chunks = chunk_text(art_text)
                    metadatas = [{"url": episode_url, "title": art_title} for _ in chunks]
                    model_obj, collection = _get_embed_resources()
                    new_count = embed_and_store(collection, model_obj, chunks, metadatas, url=episode_url)
                    mark_audio_step(state, episode_url, "embedded", art_title, source_id=source_id, parent_source_url=source_url)
                    save_state(pack_dir, state)
                    if verbose:
                        typer.echo(f"  [embed] {art_title} — {new_count} chunks")
                    report.record(art_title, "done", new=new_count)
                    continue

                if audio_path is None:
                    if transcript_text:
                        pass
                    elif source_type in {"local_audio", "local_video"}:
                        candidate = Path(episode_url).expanduser()
                        if candidate.exists() and candidate.is_file() and candidate.stat().st_size >= 10_000:
                            audio_path = candidate
                        else:
                            typer.echo(
                                f"  [warn] Missing or invalid local media source: {episode_url} — skipping",
                                err=True,
                            )
                            mark_failed(
                                state,
                                episode_url,
                                "missing or invalid local media source",
                                source_id=source_id,
                                title=episode_title,
                                parent_source_url=source_url,
                            )
                            save_state(pack_dir, state)
                            report.record(
                                episode_title,
                                "failed",
                                failure_reason="missing or invalid local media source",
                            )
                            continue
                        typer.echo(f"  [load] {episode_counter}")
                    else:
                        if not ffmpeg_available:
                            ffmpeg_reason = (
                                "ffmpeg is required for audio builds. "
                                "Install: brew install ffmpeg or visit https://ffmpeg.org/download.html"
                            )
                            typer.echo(f"  [warn] {ffmpeg_reason}", err=True)
                            report.record(episode_title, "blocked", failure_reason=ffmpeg_reason)
                            continue
                        typer.echo(f"  [download] {episode_counter}")
                        if source_type == "youtube":
                            audio_path = download_audio(episode_url, audio_dir, episode_title, verbose=verbose)
                        else:
                            audio_path = download_podcast_audio(episode_url, audio_dir, episode_title)

                    if (
                        audio_path is None
                        and not transcript_text
                        and source_type not in {"local_audio", "local_video"}
                    ):
                        typer.echo(f"  [download] retrying {episode_counter}...")
                        if source_type == "youtube":
                            audio_path = download_audio(episode_url, audio_dir, episode_title, verbose=verbose)
                        else:
                            audio_path = download_podcast_audio(episode_url, audio_dir, episode_title)

                    if audio_path is None and not transcript_text:
                        typer.echo(
                            f"  [warn] Download failed for {episode_title} — skipping",
                            err=True,
                        )
                        mark_failed(
                            state,
                            episode_url,
                            "download failed after retry",
                            source_id=source_id,
                            title=episode_title,
                            parent_source_url=source_url,
                        )
                        save_state(pack_dir, state)
                        report.record(episode_title, "failed", failure_reason="download failed after retry")
                        continue

                    if audio_path is not None and source_type not in {"local_audio", "local_video"}:
                        audio_path = _canonical_audio_path(audio_dir, source_id, audio_path)
                        mark_audio_step(
                            state,
                            episode_url,
                            "downloaded",
                            episode_title,
                            source_id=source_id,
                            parent_source_url=source_url,
                        )
                        save_state(pack_dir, state)

                # Step 2: transcribe
                transcript_path = _transcript_path(transcripts_dir, source_id)
                legacy_transcript_path = _legacy_transcript_path(transcripts_dir, episode_url)
                if is_audio_step_done(state, episode_url, "transcribed", source_id=source_id):
                    segments = _load_transcript_segments(transcript_path, legacy_transcript_path)
                else:
                    # Check if transcript file already exists (interrupted build recovery)
                    existing_segments = _load_transcript_segments(transcript_path, legacy_transcript_path)
                    if existing_segments:
                        segments = existing_segments
                        mark_audio_step(
                            state,
                            episode_url,
                            "transcribed",
                            source_id=source_id,
                            parent_source_url=source_url,
                        )
                        save_state(pack_dir, state)
                    else:
                        if transcript_text:
                            typer.echo(f"  [ingest] {episode_counter}")
                            transcript_chunks = chunk_text(transcript_text)
                            segments = [{"text": chunk} for chunk in transcript_chunks]
                        else:
                            typer.echo(f"  [transcribe] {episode_counter}")
                            segments = transcribe_audio(audio_path, model_size=model_size, language=language, verbose=verbose)
                        if not segments:
                            typer.echo(
                                f"  [warn] Transcription failed for {episode_title} — skipping",
                                err=True,
                            )
                            mark_empty(
                                state,
                                episode_url,
                                "transcription returned empty",
                                source_id=source_id,
                                title=episode_title,
                                parent_source_url=source_url,
                            )
                            save_state(pack_dir, state)
                            report.record(episode_title, "empty", failure_reason="transcription returned empty")
                            continue
                        _save_transcript_segments(transcript_path, segments)
                        mark_audio_step(
                            state,
                            episode_url,
                            "transcribed",
                            source_id=source_id,
                            parent_source_url=source_url,
                        )
                        save_state(pack_dir, state)

                if not segments:
                    typer.echo(
                        f"  [warn] Stored transcript missing for {episode_title} — re-run build",
                        err=True,
                    )
                    report.record(episode_title, "failed", failure_reason="stored transcript missing")
                    continue

                # Step 3: chunk + embed
                chunks, range_metadata = _chunk_transcript_segments(segments)
                if not chunks and transcript_text:
                    transcript_chunks = chunk_text(transcript_text)
                    if transcript_chunks:
                        segments = [{"text": chunk} for chunk in transcript_chunks]
                        _save_transcript_segments(transcript_path, segments)
                        chunks = transcript_chunks
                        range_metadata = [{} for _ in transcript_chunks]
                if not chunks:
                    typer.echo(
                        f"  [warn] No indexable transcript chunks for {episode_title} — skipping",
                        err=True,
                    )
                    mark_empty(
                        state,
                        episode_url,
                        "no indexable transcript chunks",
                        source_id=source_id,
                        title=episode_title,
                        parent_source_url=source_url,
                    )
                    save_state(pack_dir, state)
                    report.record(episode_title, "empty", failure_reason="no indexable transcript chunks")
                    continue
                metadatas = []
                for chunk_range in range_metadata:
                    metadata = {"url": episode_url, "title": episode_title, "source_id": source_id}
                    metadata.update(chunk_range)
                    metadatas.append(metadata)
                if not verbose:
                    typer.echo(f"  [embed] {episode_counter}")
                model_obj, collection = _get_embed_resources()
                new_count = embed_and_store(collection, model_obj, chunks, metadatas, url=source_id)
                mark_audio_step(
                    state,
                    episode_url,
                    "embedded",
                    source_id=source_id,
                    parent_source_url=source_url,
                )
                save_state(pack_dir, state)
                if verbose:
                    typer.echo(f"  [embed] {episode_title} — {new_count} chunks")
                report.record(episode_title, "done", new=new_count)

    # --- Final output: always print compact summary table + verdict ---
    typer.echo("")
    typer.echo(report.render_table())
    typer.echo("")
    typer.echo(report.render_verdict())
    issues_recap = report.render_issues_recap()
    if issues_recap:
        typer.echo("")
        typer.echo(issues_recap)

    # --- Persist recap state for later status inspection ---
    full_build = len(config.sources) == len(full_config.sources)
    partial_selection = bool(sources) and not full_build
    state["last_build_result"] = "partial-selection" if partial_selection and not report.had_issues else report.result
    state["last_build_summary"] = (
        f"Partial build complete — {len(config.sources)} selected source(s) processed. "
        f"Run `beyin build {full_config.id}` to finish the remaining sources."
        if partial_selection and not report.had_issues
        else report.summary_line
    )
    if not report.had_issues and full_build:
        state["last_build_at"] = utc_now_iso()
        state["last_built_pack_hash"] = current_pack_hash
    save_state(pack_dir, state)

    if report.had_issues:
        raise typer.Exit(code=1)


@app.command(cls=BeyinCommand)
def query(
    pack: str = typer.Argument(..., help="Pack name to query in local mode"),
    question: str = typer.Argument(..., help="Question to answer in local mode"),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-safe JSON output.",
    ),
):
    """Query a pack directly in local model mode and receive a cited LLM answer."""
    if json_mode:
        raise typer.Exit(
            code=run_machine_command(
                command="query",
                pack=pack,
                action=lambda: _query_payload(pack, question, machine=True),
            )
        )
    _render_query_output(_query_payload(pack, question))


@app.command(name="check-deps", cls=BeyinCommand)
def check_deps() -> None:
    """Check runtime dependencies: ffmpeg, yt-dlp, and optional document libs."""
    current = load_settings()
    runtime_rows, file_type_rows, failures = _dependency_display_rows(current)

    typer.echo("Selected capabilities:")
    for label, value in _settings_display_rows(current)[:2]:
        typer.echo(f"{label}: {value}")
    typer.echo("")

    for label, value in runtime_rows:
        typer.echo(f"{label}: {value}")

    if file_type_rows:
        typer.echo("")
        typer.echo("Document sources:")
        for label, value in file_type_rows:
            typer.echo(f"  {label}: {value}")

    if failures:
        raise typer.Exit(code=1)


@app.command(name="list", cls=BeyinCommand)
def list_command(
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-safe JSON output.",
    ),
) -> None:
    """List installed packs in a compact inventory view."""
    if json_mode:
        raise typer.Exit(
            code=run_machine_command(
                command="list",
                action=lambda: _list_payload(machine=True),
            )
        )

    summaries = _list_payload()["packs"]
    if not summaries:
        typer.echo("No packs installed.")
        return

    _render_pack_table(summaries)


@app.command(name="status", cls=BeyinCommand)
def status_command(
    pack: str = typer.Argument(..., help="Pack name to inspect"),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-safe JSON output.",
    ),
) -> None:
    """Inspect one installed pack in detail."""
    if json_mode:
        raise typer.Exit(
            code=run_machine_command(
                command="status",
                pack=pack,
                action=lambda: _status_payload(pack, machine=True),
            )
        )

    import shutil

    summary = _status_payload(pack)["pack"]
    state = summary["state"]
    config = summary["config"]

    term_w = min(shutil.get_terminal_size((80, 24)).columns, 100)

    # ── Package header ────────────────────────────────────────────────────────
    typer.echo()
    typer.echo(f"  {bold(config.name)}")
    typer.echo()

    info_rows: list[tuple[str, str]] = [("ID", config.id), ("Status", _status_styled(summary["status"])), ("Version", config.version)]
    if config.description:
        info_rows.append(("Description", config.description))
    build_date = (summary.get("last_build_at") or "")[:10]
    if build_date:
        info_rows.append(("Last built", build_date))
    sync_date = (summary.get("last_sync_at") or "")[:10]
    if sync_date:
        info_rows.append(("Last synced", sync_date))
    if config.tags:
        info_rows.append(("Tags", ", ".join(config.tags)))
    if config.contributors:
        info_rows.append(("Contributors", ", ".join(config.contributors)))
    origin = summary.get("origin") or {}
    if origin:
        info_rows.append(("Origin", origin.get("source") or origin.get("type") or "unknown"))

    label_w = max(len(label) for label, _ in info_rows)
    for label, value in info_rows:
        typer.echo(f"  {dim(label.ljust(label_w))}  {value}")

    if summary.get("blockers"):
        typer.echo()
        for blocker in summary["blockers"]:
            typer.echo(f"  {red('!')}  {blocker}")
    if summary.get("warnings"):
        typer.echo()
        for warning in summary["warnings"]:
            typer.echo(f"  {yellow('!')}  {warning}")

    # ── Sources table (borderless) ────────────────────────────────────────────
    processed_state = state.get("processed", {})
    audio_steps = state.get("audio_steps", {})
    playlist_titles_state = state.get("playlist_titles", {})
    _PLAYLIST_LABEL = {"youtube": "YouTube Playlist", "podcast": "Podcast Feed"}

    source_count = summary["source_count"]
    typer.echo()
    typer.echo(f"  {bold(f'Sources ({source_count})')}")
    typer.echo()

    W_NUM = 2
    W_STATUS = 10
    W_TITLE = max(20, term_w - W_NUM - W_STATUS - 8)
    _CONT = " " * (2 + W_NUM + 2 + W_STATUS + 2)  # indent for continuation lines

    def _ansi_col(text: str, width: int) -> str:
        return text + " " * max(0, width - _visible_len(text))

    def _srow(num: str, status: str, title: str) -> str:
        return f"  {_ansi_col(num, W_NUM)}  {_ansi_col(status, W_STATUS)}  {title}"

    def _ep_status(stages: dict) -> str:
        if stages.get("embedded"):
            return green("ready")
        if stages.get("transcribed") or stages.get("downloaded"):
            return yellow("partial")
        return dim("pending")

    def _source_audio_entries(url: str, source_type: str) -> list[dict]:
        direct_sid = canonical_source_id(url)
        if direct_sid in audio_steps:
            return [audio_steps[direct_sid]]
        owned = [
            entry for entry in audio_steps.values()
            if entry.get("parent_source_url") == url
        ]
        if owned:
            return sorted(owned, key=lambda e: e.get("title") or e.get("url") or "")
        if source_type not in {"youtube", "podcast"}:
            return []
        return []

    def _source_failures(url: str) -> list[dict]:
        direct_sid = canonical_source_id(url)
        failures: list[dict] = []
        direct = processed_state.get(direct_sid)
        if isinstance(direct, dict) and direct.get("status") == "failed":
            failures.append(direct)
        owned = [
            entry for sid, entry in processed_state.items()
            if sid != direct_sid
            and isinstance(entry, dict)
            and entry.get("status") == "failed"
            and entry.get("parent_source_url") == url
        ]
        failures.extend(sorted(owned, key=lambda e: e.get("title") or e.get("url") or ""))
        return failures

    # Header + separator
    typer.echo(_srow(dim("#"), dim("Status"), dim("Title")))
    typer.echo("  " + dim("─" * (term_w - 2)))

    sources = config.sources
    last_parent: str | None = "UNSET"
    for i, source in enumerate(sources, start=1):
        if source.parent_url != last_parent:
            last_parent = source.parent_url
            if source.parent_url:
                header = source.parent_title or source.parent_url
                typer.echo(f"  {bold(header)}")
                typer.echo(f"  {dim(source.parent_url)}")
                typer.echo()
        url = source.url
        sid = canonical_source_id(url)
        source_type = detect_source_type(url)
        source_audio_entries = _source_audio_entries(url, source_type)
        source_failures = _source_failures(url)

        if sid in processed_state:
            entry = processed_state[sid]
            status_cell = green("ready") if entry.get("status") == "done" else red("failed")
            title = entry.get("title") or url
            for j, line in enumerate(wrap_text(title, W_TITLE)):
                typer.echo(_srow(str(i) if j == 0 else "", status_cell if j == 0 else "", line))
            for line in wrap_text(url, W_TITLE):
                typer.echo(_CONT + dim(line))

        elif source_audio_entries and sid in audio_steps:
            entry = source_audio_entries[0]
            status_cell = _ep_status(entry.get("stages", {}))
            title = entry.get("title") or url
            for j, line in enumerate(wrap_text(title, W_TITLE)):
                typer.echo(_srow(str(i) if j == 0 else "", status_cell if j == 0 else "", line))
            for line in wrap_text(url, W_TITLE):
                typer.echo(_CONT + dim(line))

        elif source_type in {"youtube", "podcast"} and (source_audio_entries or source_failures):
            embedded = sum(1 for e in source_audio_entries if e.get("stages", {}).get("embedded"))
            total = len(source_audio_entries) + len(source_failures)
            failed = len(source_failures)
            status_text = f"{embedded}/{total} ready"
            if failed:
                status_text += f", {failed} failed"
            pl_status = green(status_text) if embedded == total and failed == 0 else yellow(status_text)
            real_title = playlist_titles_state.get(url) or _PLAYLIST_LABEL.get(source_type, "Playlist")
            for j, line in enumerate(wrap_text(real_title, W_TITLE)):
                typer.echo(_srow(str(i) if j == 0 else "", pl_status if j == 0 else "", line))
            for line in wrap_text(url, W_TITLE):
                typer.echo(_CONT + dim(line))
            typer.echo()
            episode_rows = [
                {
                    "url": ep.get("url") or "",
                    "title": ep.get("title") or ep.get("url") or "",
                    "status": _ep_status(ep.get("stages", {})),
                }
                for ep in source_audio_entries
            ] + [
                {
                    "url": ep.get("url") or "",
                    "title": ep.get("title") or ep.get("url") or "",
                    "status": red("failed"),
                }
                for ep in source_failures
            ]
            episode_rows.sort(key=lambda ep: ep["title"] or ep["url"])
            for k, ep in enumerate(episode_rows, start=1):
                ep_status = ep["status"]
                ep_prefix = f"{k}. "
                ep_indent = " " * len(ep_prefix)
                ep_title_lines = wrap_text(ep["title"], W_TITLE - len(ep_prefix))
                for j, line in enumerate(ep_title_lines):
                    prefix = ep_prefix if j == 0 else ep_indent
                    typer.echo(_srow("", ep_status if j == 0 else "", prefix + line))
                for line in wrap_text(ep["url"], W_TITLE - len(ep_indent)):
                    typer.echo(_CONT + dim(ep_indent + line))

        else:
            display_title = source.title or url
            for j, line in enumerate(wrap_text(display_title, W_TITLE)):
                typer.echo(_srow(str(i) if j == 0 else "", dim("pending") if j == 0 else "", line))
            if source.title:
                for line in wrap_text(url, W_TITLE):
                    typer.echo(_CONT + dim(line))

        if i < len(sources):
            # Print group separator when parent_url changes between sources
            next_source = sources[i]
            if source.parent_url != next_source.parent_url:
                typer.echo()
                if next_source.parent_url:
                    typer.echo(f"  {dim('─' * (term_w - 4))}")
            else:
                typer.echo()

    typer.echo()


@app.command(name="add", cls=BeyinCommand)
def add(
    source: str = typer.Argument(..., help="Local path or URL to a pack.yaml file"),
):
    """Add a shared pack from a local path, URL, or marketplace-style id."""
    try:
        resolved = resolve_pack_origin(source, _PACKS_DIR)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except KeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    destination_config = Path(tempfile.mkdtemp()) / "probe.yaml"
    _, config = _write_pack_yaml_from_source(resolved, destination_config)
    shutil.rmtree(destination_config.parent, ignore_errors=True)

    dest_dir = _PACKS_DIR / config.id
    if dest_dir.exists():
        typer.echo(
            f"Error: Pack '{config.id}' is already installed.\n"
            f"Use `beyin update {config.id}` to refresh it.",
            err=True,
        )
        raise typer.Exit(code=1)

    dest_dir.mkdir(parents=True)
    _write_pack_yaml_from_source(resolved, dest_dir / "pack.yaml")
    installed_hash = pack_config_hash(dest_dir)
    save_pack_origin(
        dest_dir,
        {
            "type": resolved["type"],
            "source": resolved["source"],
            "resolved": resolved["resolved"],
            "added_at": utc_now_iso(),
            "last_sync_at": utc_now_iso(),
            "last_sync_status": "synced",
            "last_source_hash": installed_hash,
            "last_synced_pack_hash": installed_hash,
            "last_updated_at": utc_now_iso(),
            "last_update_summary": ["initial add"],
        },
    )
    typer.echo(
        f"Pack '{config.id}' added to {dest_dir}/\n"
        f"Run `beyin build {config.id}` to ingest sources."
    )


@app.command(hidden=True, cls=BeyinCommand)
def install(
    source: str = typer.Argument(..., help="Local path or URL to a pack.yaml file"),
) -> None:
    """Backward-compatible alias for `beyin add`."""
    add(source)


@app.command(cls=BeyinCommand)
def update(
    pack: str = typer.Argument(..., help="Pack name to update"),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Whisper model size: tiny/tiny.en/base/base.en/small/small.en/medium/medium.en/large",
    ),
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Whisper language code (e.g. 'en', 'fr', 'es'). Default: auto-detect",
    ),
):
    """Fetch new sources and rebuild a pack incrementally."""
    pack_dir = _PACKS_DIR / pack
    if not pack_dir.exists():
        typer.echo(f"Error: Pack '{pack}' not found.", err=True)
        typer.echo(f"Add it first: beyin add <path-or-url-or-id>", err=True)
        raise typer.Exit(code=1)

    state = load_state(pack_dir)
    current_hash = pack_config_hash(pack_dir)
    origin = load_pack_origin(pack_dir)
    local_changed_since_sync = pack_diverged_from_origin(pack_dir, origin)
    if origin.get("source"):
        try:
            resolved = resolve_pack_origin(origin["source"], _PACKS_DIR)
        except (FileNotFoundError, KeyError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1)

        current_config = load_config(pack_dir)
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            tmp_yaml = tmp_dir / "incoming.yaml"
            _, incoming_config = _write_pack_yaml_from_source(resolved, tmp_yaml)
            if incoming_config.id != current_config.id:
                typer.echo(
                    f"Error: Incoming pack id '{incoming_config.id}' does not match installed pack '{current_config.id}'.",
                    err=True,
                )
                raise typer.Exit(code=1)
            incoming_hash = pack_file_hash(tmp_yaml)
            upstream_changed = incoming_hash != origin.get("last_source_hash")
            if upstream_changed and local_changed_since_sync:
                typer.echo(
                    f"Pack '{pack}' has local changes and the origin has changed too.",
                    err=True,
                )
                typer.echo(
                    "Update stopped to avoid overwriting local edits.",
                    err=True,
                )
                typer.echo(
                    f"Origin: {origin.get('source')}",
                    err=True,
                )
                typer.echo(
                    f"Local pack file: {pack_dir / 'pack.yaml'}",
                    err=True,
                )
                raise typer.Exit(code=1)
            changes = [] if incoming_hash == current_hash else summarize_pack_changes(current_config, incoming_config)
            if changes:
                typer.echo("Updating pack definition:")
                for line in changes:
                    typer.echo(f"  - {line}")
                shutil.copy2(tmp_yaml, pack_dir / "pack.yaml")
                current_hash = pack_config_hash(pack_dir)
            origin.update(
                {
                    "type": resolved["type"],
                    "source": resolved["source"],
                    "resolved": resolved["resolved"],
                    "last_sync_at": utc_now_iso(),
                    "last_sync_status": "synced",
                    "last_source_hash": incoming_hash,
                    "last_synced_pack_hash": current_hash,
                    "last_updated_at": utc_now_iso(),
                    "last_update_summary": changes or ["no config changes"],
                }
            )
            save_pack_origin(pack_dir, origin)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        if not changes:
            if local_changed_since_sync and not upstream_changed:
                typer.echo(f"Origin for '{pack}' is already current.")
                typer.echo("Local pack differs from the last synced origin.")
                typer.echo(f"Pack file: {pack_dir / 'pack.yaml'}")
                return
            runtime_status, next_step = _runtime_update_status(pack, state, current_hash)
            if runtime_status == "ready":
                typer.echo(f"Pack '{pack}' is up-to-date.")
            else:
                typer.echo(f"Pack '{pack}' definition is already current.")
                typer.echo(f"Runtime status: {runtime_status}")
                if next_step:
                    typer.echo(f"Next step: {next_step}")
            return
    else:
        runtime_status, next_step = _runtime_update_status(pack, state, current_hash)
        if runtime_status == "ready":
            typer.echo(f"Pack '{pack}' is up-to-date.")
        else:
            typer.echo(f"Pack '{pack}' has no remembered remote origin.")
            typer.echo(f"Runtime status: {runtime_status}")
            if next_step:
                typer.echo(f"Next step: {next_step}")
        return

    build(pack=pack, model=model, language=language, reset=False, verbose=False)


@app.command(name="add-source", cls=BeyinCommand)
def add_source_command(
    pack: str = typer.Argument(..., help="Pack name to add sources to"),
    urls: List[str] = typer.Argument(
        ...,
        help="One or more sources to add (URLs or supported local file paths)",
    ),
    build_after: bool = typer.Option(
        False,
        "--build",
        "-b",
        help="Run build immediately after adding sources.",
    ),
) -> None:
    """Add one or more sources to an existing pack's pack.yaml.

    Examples:
      - Single URL:     beyin add-source <pack> https://example.com/article
      - Multiple URLs:  beyin add-source <pack> https://a.com https://b.com
      - Local file:     beyin add-source <pack> ./notes.md
      - Add + build:    beyin add-source <pack> https://example.com/feed.xml --build
    """
    from beyin.config import write_config
    from beyin.authoring import add_source_to_pack as _add_source
    pack_dir = _resolve_pack_dir(pack)
    previous = load_config(pack_dir)

    updated_config = previous
    for url in urls:
        updated_config = _add_source(updated_config, url)

    new_count = len(updated_config.sources) - len(previous.sources)
    if new_count == 0:
        typer.echo("All provided sources are already in this pack.")
        return

    write_config(updated_config, pack_dir / "pack.yaml", previous=previous)

    typer.echo(f"Added {new_count} source(s) to '{pack}':")
    new_sources = updated_config.sources[len(previous.sources):]
    for entry in new_sources:
        source_type = detect_source_type(entry.url)
        label = f"{entry.title} — {entry.url}" if entry.title else entry.url
        typer.echo(f"  + [{source_type}] {label}")

    if new_count > 1 and not build_after:
        typer.echo(f"\nPack has {new_count} new source(s). Review with `beyin status {pack}`, then run `beyin build {pack}` when ready.")

    if build_after:
        typer.echo("")
        build(pack=pack, model=None, language=None, reset=False, verbose=False)


@app.command(name="remove-source", cls=BeyinCommand)
def remove_source_command(
    pack: str = typer.Argument(..., help="Pack name to remove sources from"),
    selectors: List[str] = typer.Argument(
        ...,
        help="One or more source selectors to remove (current index or visible title/source text)",
    ),
    build_after: bool = typer.Option(
        False,
        "--build",
        "-b",
        help="Run build immediately after removing sources.",
    ),
) -> None:
    """Remove one or more sources from an existing pack by index or text match.

    Selectors can be:
      - Single index:   beyin remove-source <pack> 2
      - Multiple:       beyin remove-source <pack> 1 3 5
      - Range:          beyin remove-source <pack> 1-3
      - Text match:     beyin remove-source <pack> "WWDC"

    Removed sources are no longer re-indexed on build, but their existing chunks remain
    in the vector store until you rebuild. Run with --build to clean up immediately.
    """
    pack_dir = _resolve_pack_dir(pack)
    previous = load_config(pack_dir)
    state = load_state(pack_dir)
    source_rows = serialize_pack_sources(previous, state)

    try:
        updated_config, removed_rows = remove_sources_from_pack(
            previous,
            selectors,
            source_rows=source_rows,
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    write_config(updated_config, pack_dir / "pack.yaml", previous=previous)

    typer.echo(f"Removed {len(removed_rows)} source(s) from '{pack}':")
    for row in removed_rows:
        typer.echo(
            f"  - #{row['index']} [{row.get('type', 'unknown')}] {row.get('title') or row.get('source') or row.get('url')}"
        )

    if build_after:
        typer.echo("")
        build(pack=pack, model=None, language=None, reset=False, verbose=False)
    else:
        typer.echo("")
        typer.echo(f"Warning: removed chunks are still in the vector store until you rebuild.")
        typer.echo(f"Run: beyin build {pack}")


@app.command(name="remove", cls=BeyinCommand)
def remove_command(
    pack: str = typer.Argument(..., help="Pack name to permanently remove"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation and remove without prompting.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Alias for --yes. Skip confirmation and remove without prompting.",
    ),
) -> None:
    """Permanently remove one installed pack and all its data."""
    pack_dir = _resolve_pack_dir(pack)

    bypass = yes or force
    if not bypass:
        if not is_interactive_session():
            typer.echo(
                f"Error: `beyin remove {pack}` requires --yes in non-interactive use.",
                err=True,
            )
            typer.echo(
                f"Run: beyin remove {pack} --yes",
                err=True,
            )
            raise typer.Exit(code=1)
        # Interactive TTY: use InquirerPy confirmation
        from beyin.interactive import _confirm, InteractiveAbort
        try:
            backend = load_prompt_backend()
            confirmed = _interactive_confirm(
                backend,
                f"Permanently remove pack '{pack}' and all its data?",
                default=False,
                instruction="This action cannot be undone.",
            )
        except InteractiveAbort:
            typer.echo("Remove cancelled.")
            return
        if not confirmed:
            typer.echo("Remove cancelled.")
            return

    remove_installed_pack(pack_dir)
    typer.echo(f"Pack '{pack}' removed.")


@app.command(name="mcp-server", cls=BeyinCommand)
def mcp_server_command() -> None:
    """Run beyin as a local stdio server for agents on the same machine."""
    from beyin.mcp_server import run_stdio_server

    run_stdio_server()


if __name__ == "__main__":
    app()
