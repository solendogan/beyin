"""TTY-only interactive helpers for Brainpack."""

from __future__ import annotations

import importlib
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

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
    module = importlib.import_module("InquirerPy")
    return module.inquirer


def normalize_prompt_abort(action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Collapse prompt cancellations into one reusable exception type."""
    try:
        return action(*args, **kwargs)
    except (EOFError, KeyboardInterrupt) as exc:
        raise InteractiveAbort("Interactive flow cancelled.") from exc


def _choice(value: str, name: str | None = None) -> dict[str, str]:
    return {"value": value, "name": name or value}


def _prompt(prompt_backend: Any, prompt_type: str, **kwargs: Any) -> Any:
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
            instruction=instruction,
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
            instruction=instruction,
        )
    )


def _select_setup_path(prompt_backend: Any, *, current: str = "recommended") -> str:
    return _select(
        prompt_backend,
        "Setup path",
        choices=[
            _choice("recommended", "Recommended"),
            _choice("custom", "Custom"),
        ],
        default=current,
        instruction="Recommended keeps the first machine setup narrow.",
    )


def _select_preferred_mode(prompt_backend: Any, *, current: str) -> str:
    return _select(
        prompt_backend,
        "Preferred mode",
        choices=[
            _choice("agent", "Use with agent"),
            _choice("local", "Use with local model"),
            _choice("both", "Use with both"),
        ],
        default=current,
        instruction="This changes the guidance Brainpack highlights first.",
    )


def _stage_settings(
    current: BrainpackSettings,
    *,
    prompt_backend: Any,
) -> BrainpackSettings:
    choices = available_setup_choices()
    setup_path = _select_setup_path(prompt_backend)
    preferred_mode = _select_preferred_mode(
        prompt_backend,
        current=current.preferred_mode,
    )

    if setup_path == "recommended":
        recommended = choices["recommended"]
        return BrainpackSettings(
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

    audio_enabled = _confirm(
        prompt_backend,
        "Enable audio/video defaults",
        default=current.audio_enabled_by_default,
    )
    transcription_backend = _select(
        prompt_backend,
        "Transcription backend",
        choices=[_choice(value) for value in choices["transcription_backends"]],
        default=current.preferred_transcription_backend,
        instruction="Only valid backends for this machine are shown.",
    )
    whisper_model = _select(
        prompt_backend,
        "Whisper model",
        choices=[_choice(value) for value in choices["whisper_models"]],
        default=current.preferred_whisper_model,
    )
    local_provider = _select(
        prompt_backend,
        "Local answer provider",
        choices=[_choice(value) for value in choices["local_providers"]],
        default=current.preferred_local_provider,
    )
    return BrainpackSettings(
        version=current.version,
        setup_completed=True,
        preferred_mode=preferred_mode,
        audio_enabled_by_default=audio_enabled,
        preferred_transcription_backend=transcription_backend,
        preferred_whisper_model=whisper_model,
        preferred_local_provider=local_provider,
    )


def _print_applied_summary(settings: BrainpackSettings) -> None:
    typer.echo("Applied settings")
    for line in describe_settings_summary(settings).splitlines():
        typer.echo(f"  {line}")
    typer.echo("Next step: brainpack create")
    typer.echo("Create a pack with these defaults, or rerun `brainpack settings` later.")


def _run_settings_flow(
    *,
    current: BrainpackSettings,
    prompt_backend: Any,
    cancel_message: str,
) -> bool:
    try:
        staged = _stage_settings(
            current,
            prompt_backend=prompt_backend,
        )
        confirmed = _confirm(
            prompt_backend,
            "Apply these settings",
            default=True,
        )
    except InteractiveAbort:
        typer.echo(cancel_message)
        return False

    if not confirmed:
        typer.echo(cancel_message)
        return False

    save_settings(staged)
    _print_applied_summary(staged)
    return True


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

    try:
        selection = _select(
            backend,
            "What do you want to do?",
            choices=[
                _choice("create", "Create new pack"),
                _choice("import", "Import existing pack"),
                _choice("manage", "Manage existing pack"),
            ],
            default="create",
            instruction="Create authors a new pack. Add imports an existing pack.yaml.",
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
    typer.echo(f"Created pack '{config.name}'.")
    typer.echo(f"Source saved: {config.sources[0].url}")
    typer.echo("")
    typer.echo(f"Next step: brainpack build {config.name}")
    typer.echo("Build indexes the source into local expert memory.")
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
        typer.echo("No packs installed yet. Create one with `brainpack create` first.")
        return False

    try:
        pack_name = _select(
            backend,
            "Pack to manage",
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
    typer.echo(f"Updated pack '{pack_name}'.")
    typer.echo(f"Next step: brainpack build {pack_name}")
    typer.echo("Rebuild after authoring changes so retrieval uses the latest sources.")
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
    )
