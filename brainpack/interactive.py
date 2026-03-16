"""TTY-only interactive helpers for Brainpack."""

from __future__ import annotations

import importlib
import platform
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from brainpack import __version__
from brainpack.authoring import (
    add_source_to_pack,
    build_new_pack_config,
    update_pack_metadata,
)
from brainpack.config import load_config, write_config
from brainpack.settings import (
    BrainpackSettings,
    available_setup_choices,
    describe_settings_summary,
    load_settings,
    save_settings,
)
from brainpack.ui import render_header, render_meta, render_review, render_status


class InteractiveAbort(RuntimeError):
    """Normalized interactive cancellation for later prompt-driven flows."""


def is_interactive_session(stdin: Any = None, stdout: Any = None) -> bool:
    """Return True when both input and output streams are TTY-backed."""
    input_stream = sys.stdin if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout
    return bool(
        getattr(input_stream, "isatty", lambda: False)()
        and getattr(output_stream, "isatty", lambda: False)()
    )


def require_interactive_session() -> None:
    """Raise a reusable abort when interactive prompts are unavailable."""
    if not is_interactive_session():
        raise InteractiveAbort("Interactive prompts require a TTY session.")


def load_prompt_backend():
    """Load InquirerPy lazily so normal CLI imports stay dependency-light."""
    return importlib.import_module("InquirerPy.inquirer")


def normalize_prompt_abort(action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Collapse prompt cancellations into one reusable exception type."""
    try:
        return action(*args, **kwargs)
    except (EOFError, KeyboardInterrupt) as exc:
        raise InteractiveAbort("Interactive flow cancelled.") from exc


def _choice(
    value: str,
    name: str | None = None,
    *,
    help_text: str | None = None,
) -> dict[str, str]:
    label = name or value
    if help_text:
        short = help_text if len(help_text) <= 52 else help_text[:51] + "…"
        return {"value": value, "name": f"{label:<22}  {short}"}
    return {"value": value, "name": label}


def _echo_lines(lines: list[str]) -> None:
    for line in lines:
        typer.echo(line)


def _print_screen(
    title: str,
    intro_lines: list[str],
    *,
    show_brand: bool = False,
    footer_lines: list[str] | None = None,
) -> None:
    if show_brand:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        _echo_lines(render_header(version=__version__, step=title))
    else:
        typer.echo("")
        _echo_lines([f"  {typer.style(title, bold=True)}"])
    typer.echo("")
    _echo_lines(render_meta(intro_lines))
    if footer_lines:
        typer.echo("")
        _echo_lines(render_meta(footer_lines))
    typer.echo("")


def _print_review(title: str, lines: list[str]) -> None:
    typer.echo("")
    rows: list[tuple[str, str]] = []
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            rows.append((key.strip(), value.strip()))
        else:
            rows.append(("", line))
    _echo_lines(render_review(title, rows))
    typer.echo("")


def _print_prompt_hint(text: str | None) -> None:
    if not text:
        return
    _echo_lines(render_meta([text]))
    typer.echo("")


def _machine_label() -> str:
    system = platform.system()
    machine = platform.machine()
    human = {
        "Darwin": "Mac",
        "Linux": "Linux",
        "Windows": "Windows",
    }.get(system, system)
    return f"{human} ({system.lower()} {machine.lower()})"


def _setup_path_description(value: str) -> str:
    if value == "recommended":
        return "Agent-first defaults. Tune details later."
    return "Pick mode, audio, transcription, and local answers."


def _mode_description(value: str) -> str:
    descriptions = {
        "agent": "Via Claude Code, Codex, or another AI agent.",
        "local": "Use brainpack query/chat as your main UI.",
        "both": "Keep agent and local workflows both ready.",
    }
    return descriptions.get(value, value)


def _backend_description(value: str) -> str:
    descriptions = {
        "mlx-whisper": "Apple Silicon. Metal-accelerated transcription.",
        "faster-whisper": "Linux, Windows, or non-Apple-Silicon fallback.",
    }
    return descriptions.get(value, value)


def _model_description(value: str) -> str:
    descriptions = {
        "small": "Fastest. Comfortable on 8 GB RAM.",
        "medium": "Better accuracy. Best on 12–16 GB RAM.",
        "large": "Best quality. Needs 16 GB+ RAM, slower.",
    }
    return descriptions.get(value, value)


def _provider_description(value: str) -> str:
    descriptions = {
        "none": "Skip for now, configure later.",
        "ollama": "Local model on this machine via Ollama.",
        "openai": "OpenAI API for local-mode answering.",
    }
    return descriptions.get(value, value)


def _print_setup_intro(*, first_run: bool) -> None:
    title = "Start your first setup now" if first_run else "Update Brainpack settings"
    intro_lines = [
        "Turn your favorite content into local queryable context.",
        f"Detected machine: {_machine_label()}",
    ]
    footer_lines = [
        "You can change these defaults later with `brainpack settings`.",
        "Press Ctrl+C at any time to cancel without writing changes.",
    ]
    _print_screen(title, intro_lines, footer_lines=footer_lines, show_brand=True)


def _print_authoring_intro(packs_dir: Path, pack_summaries: list | None = None) -> None:
    if pack_summaries is not None:
        total = len(pack_summaries)
        ready = sum(1 for s in pack_summaries if s.get("status") == "ready")
        if total == 0:
            summary_line = "No packs installed yet."
        elif ready == total:
            summary_line = f"{total} pack{'s' if total != 1 else ''} installed, all ready."
        elif ready > 0:
            summary_line = f"{total} pack{'s' if total != 1 else ''} installed, {ready} ready."
        else:
            needs = total - ready
            summary_line = f"{total} pack{'s' if total != 1 else ''} installed, {needs} need building."
    else:
        pack_count = 0
        if packs_dir.exists():
            pack_count = len(
                [
                    path
                    for path in packs_dir.iterdir()
                    if path.is_dir() and (path / "pack.yaml").exists()
                ]
            )
        summary_line = f"Installed packs detected: {pack_count}"
    _print_screen(
        "What would you like to do?",
        [summary_line, "Choice details appear under the menu."],
        show_brand=True,
    )


def _print_create_intro() -> None:
    _print_screen(
        "Create a new pack",
        [
            "Start with one source. Brainpack infers the content path from the value you paste.",
        ],
        footer_lines=[
            "After creation, run `brainpack build <name>` to index the source into local retrieval memory.",
        ],
        show_brand=True,
    )


def _print_import_intro() -> None:
    _print_screen(
        "Import an existing pack",
        [
            "This keeps `brainpack add` semantics intact and only imports an already-authored pack.",
        ],
        show_brand=True,
    )


def _print_manage_intro(pack_count: int) -> None:
    _print_screen(
        "Manage an existing pack",
        [
            f"Available packs: {pack_count}",
            "Update metadata or append another content source without hand-editing YAML.",
        ],
        show_brand=True,
    )


def _prompt(prompt_backend: Any, prompt_type: str, **kwargs: Any) -> Any:
    hint = kwargs.pop("hint", None)
    _print_prompt_hint(hint)
    kwargs.setdefault("instruction", "")
    prompt = getattr(prompt_backend, prompt_type)(
        raise_keyboard_interrupt=True,
        **kwargs,
    )
    return normalize_prompt_abort(prompt.execute)


def _select(
    prompt_backend: Any,
    message: str,
    *,
    choices: list[dict[str, str]],
    default: str | None = None,
) -> str:
    return _prompt(
        prompt_backend,
        "select",
        message=message,
        choices=choices,
        default=default,
    )


def _text(
    prompt_backend: Any,
    message: str,
    *,
    default: str | None = None,
    instruction: str | None = None,
) -> str:
    return str(
        _prompt(
            prompt_backend,
            "text",
            message=message,
            default=default or "",
            instruction="",
            hint=instruction,
        )
    ).strip()


def _confirm(
    prompt_backend: Any,
    message: str,
    *,
    default: bool = True,
    instruction: str | None = None,
) -> bool:
    return bool(
        _prompt(
            prompt_backend,
            "confirm",
            message=message,
            default=default,
            instruction="",
            hint=instruction,
        )
    )


def _select_setup_path(prompt_backend: Any, *, current: str = "recommended") -> str:
    return _select(
        prompt_backend,
        "Select a setup path",
        choices=[
            _choice("recommended", "Recommended", help_text=_setup_path_description("recommended")),
            _choice("custom", "Custom", help_text=_setup_path_description("custom")),
        ],
        default=current,
    )


def _select_preferred_mode(prompt_backend: Any, *, current: str) -> str:
    return _select(
        prompt_backend,
        "Select the preferred Brainpack mode",
        choices=[
            _choice("agent", "Use with agent", help_text=_mode_description("agent")),
            _choice("local", "Use with local model", help_text=_mode_description("local")),
            _choice("both", "Use with both", help_text=_mode_description("both")),
        ],
        default=current,
    )


def _stage_settings(
    current: BrainpackSettings,
    *,
    prompt_backend: Any,
    first_run: bool,
) -> BrainpackSettings:
    choices = available_setup_choices()
    _print_setup_intro(first_run=first_run)
    setup_path = _select_setup_path(prompt_backend)
    preferred_mode = _select_preferred_mode(
        prompt_backend,
        current=current.preferred_mode,
    )

    if setup_path == "recommended":
        recommended = choices["recommended"]
        staged = BrainpackSettings(
            version=current.version,
            setup_completed=True,
            preferred_mode=preferred_mode,
            audio_enabled_by_default=bool(recommended["audio_enabled_by_default"]),
            preferred_transcription_backend=str(
                recommended["preferred_transcription_backend"]
            ),
            preferred_whisper_model=str(recommended["preferred_whisper_model"]),
            preferred_local_provider=str(recommended["preferred_local_provider"]),
        )
        _print_review("Recommended defaults preview", describe_settings_summary(staged).splitlines())
        return staged

    audio_enabled = _confirm(
        prompt_backend,
        "Enable audio/video defaults",
        default=current.audio_enabled_by_default,
        instruction="Choose whether new setups should assume audio/video transcription is available.",
    )
    transcription_backend = current.preferred_transcription_backend
    whisper_model = current.preferred_whisper_model
    if audio_enabled:
        transcription_backend = _select(
            prompt_backend,
            "Select a transcription backend",
            choices=[
                _choice(value, value, help_text=_backend_description(value))
                for value in choices["transcription_backends"]
            ],
            default=current.preferred_transcription_backend,
        )
        whisper_model = _select(
            prompt_backend,
            "Select the default Whisper model",
            choices=[
                _choice(value, value, help_text=_model_description(value))
                for value in choices["whisper_models"]
            ],
            default=current.preferred_whisper_model,
        )
    local_provider = _select(
        prompt_backend,
        "Select the default local answer provider",
        choices=[
            _choice(
                value,
                {
                    "none": "Skip for now",
                    "ollama": "Ollama",
                    "openai": "OpenAI",
                }.get(value, value),
                help_text=_provider_description(value),
            )
            for value in choices["local_providers"]
        ],
        default=current.preferred_local_provider,
    )
    staged = BrainpackSettings(
        version=current.version,
        setup_completed=True,
        preferred_mode=preferred_mode,
        audio_enabled_by_default=audio_enabled,
        preferred_transcription_backend=transcription_backend,
        preferred_whisper_model=whisper_model,
        preferred_local_provider=local_provider,
    )
    _print_review("Review setup", describe_settings_summary(staged).splitlines())
    return staged


def _print_applied_summary(settings: BrainpackSettings) -> None:
    if settings.preferred_mode in {"agent", "both"}:
        next_lines = [
            "Quick start for agent mode:",
            "  1. brainpack mcp-server  \u2190 add this to your agent's MCP config",
            "  2. brainpack create       \u2190 create your first pack",
            "  3. brainpack build <pack>",
        ]
    else:
        next_lines = [
            "Quick start:",
            "  1. brainpack create",
            "  2. brainpack build <pack>",
            '  3. brainpack query <pack> "your question"',
        ]
    _echo_lines(
        render_status(
            "Setup complete",
            [
                *describe_settings_summary(settings).splitlines(),
                "",
                *next_lines,
            ],
            tone="success",
        )
    )


def _run_settings_flow(
    *,
    current: BrainpackSettings,
    prompt_backend: Any,
    cancel_message: str,
    first_run: bool,
) -> bool:
    active = current
    while True:
        try:
            staged = _stage_settings(
                active,
                prompt_backend=prompt_backend,
                first_run=first_run,
            )
            confirmed = _confirm(
                prompt_backend,
                "Apply these settings",
                default=True,
                instruction="Choose No to revise your selections. Press Ctrl+C to exit without saving.",
            )
        except InteractiveAbort:
            typer.echo(cancel_message)
            return False

        if confirmed:
            save_settings(staged)
            _print_applied_summary(staged)
            return True

        typer.echo("")
        _echo_lines(
            render_status(
                "Nothing saved yet",
                ["Returning to setup so you can revise the selections."],
                tone="info",
            )
        )
        typer.echo("")
        active = staged


def run_authoring_menu(
    *,
    packs_dir: Path,
    prompt_backend: Any | None = None,
    import_handler: Callable[[str], Any] | None = None,
    pack_summaries: list | None = None,
) -> bool:
    """Show the interactive create/import/manage chooser for human sessions."""
    backend = prompt_backend
    if backend is None:
        require_interactive_session()
        backend = load_prompt_backend()

    _print_authoring_intro(packs_dir, pack_summaries)
    try:
        selection = _select(
            backend,
            "Choose an action",
            choices=[
                _choice(
                    "create",
                    "Create new pack",
                    help_text="New pack from a URL, YouTube link, or local path.",
                ),
                _choice(
                    "import",
                    "Import existing pack",
                    help_text="Import a pack.yaml from a path or URL.",
                ),
                _choice(
                    "manage",
                    "Manage existing pack",
                    help_text="Edit metadata or add another source.",
                ),
            ],
            default="create",
        )
    except InteractiveAbort:
        typer.echo("Authoring menu cancelled.")
        return False

    if selection == "create":
        return bool(run_create_flow(packs_dir=packs_dir, prompt_backend=backend))
    if selection == "import":
        return bool(
            run_import_flow(
                packs_dir=packs_dir,
                prompt_backend=backend,
                import_handler=import_handler,
            )
        )
    return bool(run_manage_pack_flow(packs_dir=packs_dir, prompt_backend=backend))


def run_create_flow(
    *,
    packs_dir: Path,
    prompt_backend: Any | None = None,
) -> bool:
    """Run the guided new-pack authoring flow."""
    backend = prompt_backend
    if backend is None:
        require_interactive_session()
        backend = load_prompt_backend()

    _print_create_intro()
    try:
        source_input = _text(
            backend,
            "Source URL or local path",
            instruction="Use a URL, feed, YouTube link, or a local text-like path.",
        )
        name = _text(backend, "Pack name")
        description = _text(backend, "Short description")
        config = build_new_pack_config(
            name=name,
            description=description,
            source_input=source_input,
        )
        _print_review(
            "Review pack",
            [
                f"Name: {config.name}",
                f"Description: {config.description}",
                f"First source: {config.sources[0].url}",
            ],
        )
        confirmed = _confirm(backend, "Create this pack", default=True)
    except InteractiveAbort:
        typer.echo("Pack creation cancelled. No files were written.")
        return False
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        return False

    if not name or not re.match(r"^[\w.-]+$", name):
        typer.echo(
            f"Error: Pack name '{name}' contains invalid characters. "
            "Only alphanumerics, hyphens, underscores, and dots are allowed.",
            err=True,
        )
        return False

    pack_dir = packs_dir / config.id
    if pack_dir.exists():
        typer.echo(
            f"Error: Pack '{config.id}' already exists.\n"
            f"Choose a new name or run `brainpack update {config.id}`.",
            err=True,
        )
        return False

    if not confirmed:
        typer.echo("Pack creation cancelled. No files were written.")
        return False

    write_config(config, pack_dir / "pack.yaml")
    _echo_lines(
        render_status(
            f"Created pack '{config.id}'",
            [
                f"Source saved: {config.sources[0].url}",
                "",
                f"Next step: brainpack build {config.id}",
                "Build indexes the source into local expert memory.",
            ],
            tone="success",
        )
    )
    return True


def run_import_flow(
    *,
    packs_dir: Path,
    prompt_backend: Any | None = None,
    import_handler: Callable[[str], Any] | None = None,
) -> bool:
    """Prompt for a pack source and delegate to the explicit import command path."""
    del packs_dir  # Reserved for future pack-aware import UX; direct add owns import semantics today.

    backend = prompt_backend
    if backend is None:
        require_interactive_session()
        backend = load_prompt_backend()
    if import_handler is None:
        raise RuntimeError("run_import_flow requires an import handler.")

    _print_import_intro()
    try:
        source = _text(
            backend,
            "Path, URL, or marketplace id for pack.yaml",
            instruction="This uses the same import path as `brainpack add`.",
        )
    except InteractiveAbort:
        typer.echo("Pack import cancelled.")
        return False

    import_handler(source)
    return True


def run_manage_pack_flow(
    *,
    packs_dir: Path,
    prompt_backend: Any | None = None,
) -> bool:
    """Run the guided manage flow for basic metadata and source edits."""
    backend = prompt_backend
    if backend is None:
        require_interactive_session()
        backend = load_prompt_backend()

    pack_choices = [
        _choice(path.name)
        for path in sorted(packs_dir.iterdir(), key=lambda item: item.name)
        if path.is_dir() and (path / "pack.yaml").exists()
    ] if packs_dir.exists() else []

    if not pack_choices:
        _echo_lines(
            render_status(
                "No packs installed yet",
                ["Create one with `brainpack create` first."],
                tone="warn",
            )
        )
        return False

    _print_manage_intro(len(pack_choices))
    try:
        pack_name = _select(
            backend,
            "Choose a pack to manage",
            choices=pack_choices,
            default=pack_choices[0]["value"],
        )
        pack_dir = packs_dir / pack_name
        current = load_config(pack_dir)
        description = _text(
            backend,
            "Pack description",
            default=current.description,
        )
        add_source = _confirm(backend, "Add another source", default=False)

        staged = update_pack_metadata(current, description=description)
        if add_source:
            source_input = _text(
                backend,
                "New source URL or local path",
                instruction="Local text-like paths stay authored as content sources.",
            )
            staged = add_source_to_pack(staged, source_input)

        review_lines = [
            f"Pack: {pack_name}",
            f"Description: {staged.description}",
            f"Source count: {len(staged.sources)}",
        ]
        if add_source:
            review_lines.append(f"Latest source: {staged.sources[-1].url}")
        _print_review("Review pack changes", review_lines)
        confirmed = _confirm(backend, "Apply pack changes", default=True)
    except InteractiveAbort:
        typer.echo("Pack changes cancelled. pack.yaml unchanged.")
        return False
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        return False

    if not confirmed:
        typer.echo("Pack changes cancelled. pack.yaml unchanged.")
        return False

    write_config(staged, pack_dir / "pack.yaml")
    _echo_lines(
        render_status(
            f"Updated pack '{pack_name}'",
            [
                f"Next step: brainpack build {pack_name}",
                "Rebuild after authoring changes so retrieval uses the latest sources.",
            ],
            tone="success",
        )
    )
    return True


def run_initial_setup_flow(*, prompt_backend: Any | None = None) -> bool:
    """Run the one-time initial setup flow and persist confirmed settings."""
    backend = prompt_backend
    if backend is None:
        require_interactive_session()
        backend = load_prompt_backend()
    return _run_settings_flow(
        current=load_settings(),
        prompt_backend=backend,
        cancel_message="Setup cancelled. Settings unchanged.",
        first_run=True,
    )


def run_settings_flow(*, prompt_backend: Any | None = None) -> bool:
    """Run the explicit editable settings flow and persist confirmed settings."""
    backend = prompt_backend
    if backend is None:
        require_interactive_session()
        backend = load_prompt_backend()
    return _run_settings_flow(
        current=load_settings(),
        prompt_backend=backend,
        cancel_message="Settings update cancelled. Settings unchanged.",
        first_run=False,
    )
