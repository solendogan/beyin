"""Shared machine-safe JSON helpers for CLI commands."""

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

CLI_SCHEMA_VERSION = "beyin.cli.v1"
EXIT_USAGE = 2
EXIT_PRECONDITION = 3
EXIT_UNEXPECTED = 4


def _build_meta(
    *,
    command: str,
    pack: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload = {
        "schema": CLI_SCHEMA_VERSION,
        "command": command,
    }
    if pack is not None:
        payload["pack"] = pack
    if meta:
        payload.update(meta)
    return payload


def build_success_envelope(
    *,
    command: str,
    data: Any,
    pack: Optional[str] = None,
    warnings: Optional[list[str]] = None,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the shared success envelope for machine-safe responses."""
    return {
        "ok": True,
        "meta": _build_meta(command=command, pack=pack, meta=meta),
        "data": data,
        "warnings": list(warnings or []),
    }


def build_error_envelope(
    *,
    command: str,
    error_code: str,
    message: str,
    pack: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    warnings: Optional[list[str]] = None,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the shared failure envelope for machine-safe responses."""
    return {
        "ok": False,
        "meta": _build_meta(command=command, pack=pack, meta=meta),
        "error": {
            "code": error_code,
            "message": message,
            "details": dict(details or {}),
        },
        "warnings": list(warnings or []),
    }


def emit_json(payload: dict[str, Any]) -> None:
    """Write exactly one JSON document to stdout."""
    sys.stdout.write(json.dumps(payload))
    sys.stdout.write("\n")
    sys.stdout.flush()


@dataclass(slots=True)
class MachineExit(Exception):
    """Structured machine-mode failure with a stable exit code."""

    code: str
    message: str
    exit_code: int
    details: dict[str, Any] = field(default_factory=dict)
    pack: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

    @classmethod
    def usage(
        cls,
        code: str,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        pack: Optional[str] = None,
        warnings: Optional[list[str]] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> "MachineExit":
        return cls(
            code=code,
            message=message,
            exit_code=EXIT_USAGE,
            details=dict(details or {}),
            pack=pack,
            warnings=list(warnings or []),
            meta=dict(meta or {}),
        )

    @classmethod
    def precondition(
        cls,
        code: str,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        pack: Optional[str] = None,
        warnings: Optional[list[str]] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> "MachineExit":
        return cls(
            code=code,
            message=message,
            exit_code=EXIT_PRECONDITION,
            details=dict(details or {}),
            pack=pack,
            warnings=list(warnings or []),
            meta=dict(meta or {}),
        )


def capture_machine_command(
    *,
    command: str,
    action: Callable[[], Any],
    pack: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], int]:
    """Run one machine-safe action and return its normalized envelope plus exit code."""
    try:
        data = action()
        return (
            build_success_envelope(
                command=command,
                pack=pack,
                data=data,
                meta=meta,
            ),
            0,
        )
    except MachineExit as exc:
        return (
            build_error_envelope(
                command=command,
                pack=exc.pack or pack,
                error_code=exc.code,
                message=exc.message,
                details=exc.details,
                warnings=exc.warnings,
                meta=exc.meta or meta,
            ),
            exc.exit_code,
        )
    except Exception as exc:  # pragma: no cover - exercised via contract tests
        return (
            build_error_envelope(
                command=command,
                pack=pack,
                error_code="unexpected_error",
                message="Unexpected error while running command.",
                details={"type": type(exc).__name__},
                meta=meta,
            ),
            EXIT_UNEXPECTED,
        )


def run_machine_command(
    *,
    command: str,
    action: Callable[[], Any],
    pack: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> int:
    """Run one machine-safe command, normalizing expected and unexpected failures."""
    payload, exit_code = capture_machine_command(
        command=command,
        action=action,
        pack=pack,
        meta=meta,
    )
    emit_json(payload)
    return exit_code
