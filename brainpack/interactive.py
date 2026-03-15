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
    choice = {"value": value, "name": name or value}
    if help_text:
        choice["help"] = help_text
    return choice


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
        _echo_lines(render_header(version=__version__, step=title))
    else:
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
        return "Set up the agent-first path quickly, then configure optional local features later."
    return "Choose mode, audio/video defaults, transcription backend, model size, and local answers."


def _mode_description(value: str) -> str:
    descriptions = {
        "agent": "Best when Brainpack works with Codex, Claude, or another AI assistant.",
        "local": "Best when you want Brainpack query/chat to be your main interface.",
        "both": "Keep both paths ready and let Brainpack highlight either workflow.",
    }
    return descriptions.get(value, value)


def _backend_description(value: str) -> str:
    descriptions = {
        "mlx-whisper": (
            "Best on Apple Silicon Macs. Uses Metal acceleration for faster local transcription."
        ),
        "faster-whisper": (
            "Cross-platform option for Linux, Windows, and non-Apple-Silicon fallback setups."
        ),
    }
    return descriptions.get(value, value)


def _model_description(value: str) -> str:
    descriptions = {
        "small": (
            "Fastest and lightest. Rough guide: comfortable on 8 GB RAM machines."
        ),
        "medium": (
            "Better accuracy than small. Rough guide: best on about 12-16 GB RAM."
        ),
        "large": (
            "Best quality. Rough guide: strongest choice for 16 GB+ RAM and slower runs."
        ),
    }
    return descriptions.get(value, value)


def _provider_description(value: str) -> str:
    descriptions = {
        "none": "Skip local-answer setup for now.",
        "ollama": "Use a local runtime on this machine, such as qwen via Ollama.",
        "openai": "Use a hosted model API for local-mode answering.",
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


def _print_mode_intro(current: str) -> None:
    _print_screen(
        "Choose the workflow Brainpack should emphasize",
        [
            "This changes which guidance Brainpack highlights first.",
            f"Current preference: {current}",
        ],
        show_brand=False,
    )


def _print_custom_setup_intro(
    *,
    choices: dict[str, Any],
    current: BrainpackSettings,
) -> None:
    footer_lines = [
        f"Current mode: {current.preferred_mode}",
        (
            "Current transcription: "
            f"{current.preferred_transcription_backend} / {current.preferred_whisper_model}"
        ),
        f"Current local answers: {current.preferred_local_provider}",
    ]
    _print_screen(
        "Choose custom setup defaults",
        [
            "Tune machine defaults up front. Choice details appear under the menu.",
        ],
        footer_lines=footer_lines,
        show_brand=False,
    )


def _print_authoring_intro(packs_dir: Path) -> None:
    pack_count = 0
    if packs_dir.exists():
        pack_count = len(
            [
                path
                for path in packs_dir.iterdir()
                if path.is_dir() and (path / "pack.yaml").exists()
            ]
        )
    _print_screen(
        "Choose your next Brainpack action",
        [
            f"Installed packs detected: {pack_count}",
            "Choice details appear under the menu.",
        ],
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
    if prompt_type == "select":
        choices = kwargs.get("choices", [])
        if any("help" in choice for choice in choices):
            return _prompt_select_with_help(prompt_backend, **kwargs)
    hint = kwargs.pop("hint", None)
    _print_prompt_hint(hint)
    if "instruction" in kwargs:
        kwargs["instruction"] = ""
    prompt = getattr(prompt_backend, prompt_type)(
        raise_keyboard_interrupt=True,
        **kwargs,
    )
    return normalize_prompt_abort(prompt.execute)


def _prompt_select_with_help(prompt_backend: Any, **kwargs: Any) -> Any:
    help_by_value = {
        choice["value"]: choice.get("help", "")
        for choice in kwargs["choices"]
        if isinstance(choice, dict)
    }
    plain_choices = [
        {
            key: value
            for key, value in choice.items()
            if key in {"value", "name", "enabled"}
        }
        for choice in kwargs["choices"]
    ]
    long_instruction = help_by_value.get(kwargs.get("default")) or next(
        (text for text in help_by_value.values() if text),
        "",
    )

    if getattr(prompt_backend, "__name__", "") == "InquirerPy.inquirer":
        prompt = _build_dynamic_select_prompt(
            message=kwargs["message"],
            choices=plain_choices,
            default=kwargs.get("default"),
            instruction="",
            long_instruction=long_instruction,
            help_by_value=help_by_value,
        )
        return normalize_prompt_abort(prompt.execute)

    prompt = prompt_backend.select(
        raise_keyboard_interrupt=True,
        message=kwargs["message"],
        choices=plain_choices,
        default=kwargs.get("default"),
        instruction="",
        long_instruction=long_instruction,
    )
    return normalize_prompt_abort(prompt.execute)


def _build_dynamic_select_prompt(
    *,
    message: str,
    choices: list[dict[str, str]],
    default: str | None,
    instruction: str | None,
    long_instruction: str,
    help_by_value: dict[str, str],
) -> Any:
    list_prompt = importlib.import_module("InquirerPy.prompts.list")

    class DynamicHelpListPrompt(list_prompt.ListPrompt):
        def __init__(self, *args: Any, help_lookup: dict[str, str], **kwargs: Any) -> None:
            self._help_lookup = help_lookup
            super().__init__(*args, **kwargs)
            self._sync_help()

        def _sync_help(self) -> None:
            selected = self.content_control.selection["value"]
            self._long_instruction = self._help_lookup.get(selected, "")

        def _handle_up(self, event: Any) -> None:
            super()._handle_up(event)
            self._sync_help()
            self._redraw()

        def _handle_down(self, event: Any) -> None:
            super()._handle_down(event)
            self._sync_help()
            self._redraw()

    return DynamicHelpListPrompt(
        message=message,
        choices=choices,
        default=default,
        instruction=instruction or "",
        long_instruction=long_instruction,
        raise_keyboard_interrupt=True,
        help_lookup=help_by_value,
    )


def _select(
    prompt_backend: Any,
    message: str,
    *,
    choices: list[dict[str, str]],
    default: str | None = None,
    instruction: str | None = None,
) -> str:
    return _prompt(
        prompt_backend,
        "select",
        message=message,
        choices=choices,
        default=default,
        instruction=instruction,
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
            default=default,
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
            _choice(
                "recommended",
                "Recommended",
                help_text=_setup_path_description("recommended"),
            ),
            _choice(
                "custom",
                "Custom",
                help_text=_setup_path_description("custom"),
            ),
        ],
        default=current,
        instruction="Arrow keys move. Enter confirms.",
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
        instruction="Arrow keys move. Enter confirms.",
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
    _print_mode_intro(current=current.preferred_mode)
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

    _print_custom_setup_intro(choices=choices, current=current)
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
            instruction="Only valid backends for this machine are shown.",
        )
        whisper_model = _select(
            prompt_backend,
            "Select the default Whisper model",
            choices=[
                _choice(value, value, help_text=_model_description(value))
                for value in choices["whisper_models"]
            ],
            default=current.preferred_whisper_model,
            instruction=(
                "Rough RAM guidance only; real usage varies by backend, device, and transcript length."
            ),
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
        instruction="This affects Brainpack query/chat defaults, not MCP retrieval.",
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
    next_lines = ["Next step: brainpack create"]
    if settings.preferred_mode in {"agent", "both"}:
        next_lines.append("After building a pack, connect your assistant with `brainpack mcp-server`.")
    else:
        next_lines.append("After building a pack, use `brainpack query` or `brainpack chat`.")
    _echo_lines(
        render_status(
            "Applied settings",
            [
                *describe_settings_summary(settings).splitlines(),
                "",
                *next_lines,
                "Create a pack with these defaults, or rerun `brainpack settings` later.",
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
) -> bool:
    """Show the interactive create/import/manage chooser for human sessions."""
    backend = prompt_backend
    if backend is None:
        require_interactive_session()
        backend = load_prompt_backend()

    _print_authoring_intro(packs_dir)
    try:
        selection = _select(
            backend,
            "Choose an action",
            choices=[
                _choice(
                    "create",
                    "Create new pack",
                    help_text="Author a fresh pack from a URL or local text-like file.",
                ),
                _choice(
                    "import",
                    "Import existing pack",
                    help_text="Bring in an existing pack.yaml from a path, URL, or marketplace id.",
                ),
                _choice(
                    "manage",
                    "Manage existing pack",
                    help_text="Update pack metadata or append another content source.",
                ),
            ],
            default="create",
            instruction="Arrow keys move. Enter confirms.",
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

    pack_dir = packs_dir / config.name
    if pack_dir.exists():
        typer.echo(
            f"Error: Pack '{config.name}' already exists.\n"
            f"Choose a new name or run `brainpack update {config.name}`.",
            err=True,
        )
        return False

    if not confirmed:
        typer.echo("Pack creation cancelled. No files were written.")
        return False

    write_config(config, pack_dir / "pack.yaml")
    _echo_lines(
        render_status(
            f"Created pack '{config.name}'",
            [
                f"Source saved: {config.sources[0].url}",
                "",
                f"Next step: brainpack build {config.name}",
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
            instruction="Arrow keys move. Enter confirms.",
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
