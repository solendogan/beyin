"""TTY-only interactive helpers for Brainpack."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from typing import Any


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

