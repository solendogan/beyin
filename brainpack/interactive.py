"""TTY-only interactive helpers for Brainpack."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from typing import Any

import typer

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
