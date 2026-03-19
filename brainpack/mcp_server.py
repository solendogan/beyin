"""Brainpack MCP server exposing machine-safe inventory and retrieval tools."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import typer
from mcp.server.fastmcp import FastMCP

from brainpack import __version__
from brainpack.authoring import add_source_to_pack
from brainpack.cli import (
    add as _cli_add,
    build as _cli_build,
)
from brainpack.payloads import (
    _doctor_payload,
    _evidence_payload,
    _list_payload,
    _status_payload,
)
from brainpack.config import load_config, write_config
from brainpack.machine_output import (
    build_error_envelope,
    build_success_envelope,
    capture_machine_command,
)

app = FastMCP("Brainpack", json_response=True)


def _tool_result(
    *,
    command: str,
    action,
    pack: str | None = None,
) -> dict[str, Any]:
    """Reuse the machine-safe CLI envelope for MCP tool responses."""
    payload, _ = capture_machine_command(
        command=command,
        action=action,
        pack=pack,
        meta={"surface": "mcp", "server_version": __version__},
    )
    return payload


def _command_tool_result(
    *,
    command: str,
    action,
    pack: str | None = None,
) -> dict[str, Any]:
    """Run a CLI command implementation with captured output for MCP use."""
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    exit_code = 0

    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        try:
            action()
        except typer.Exit as exc:
            exit_code = exc.exit_code or 0

    details = {
        "exit_code": exit_code,
        "stdout": stdout_buffer.getvalue().strip(),
        "stderr": stderr_buffer.getvalue().strip(),
    }
    meta = {"surface": "mcp", "server_version": __version__}

    if exit_code == 0:
        return build_success_envelope(
            command=command,
            pack=pack,
            data=details,
            meta=meta,
        )

    message = details["stderr"] or details["stdout"] or f"{command} exited with code {exit_code}."
    return build_error_envelope(
        command=command,
        pack=pack,
        error_code=f"{command}_failed",
        message=message.splitlines()[0],
        details=details,
        meta=meta,
    )


@app.tool()
def packs() -> dict[str, Any]:
    """List all installed packs with status and next-action guidance."""
    return _tool_result(command="list", action=lambda: _list_payload(machine=True))


@app.tool()
def status(pack: str) -> dict[str, Any]:
    """Inspect one installed pack — lifecycle state, blockers, and recommended next action."""
    return _tool_result(
        command="status",
        pack=pack,
        action=lambda: _status_payload(pack, machine=True),
    )


@app.tool()
def doctor(pack: str, operation: str = "all") -> dict[str, Any]:
    """Check pack readiness for query or build operations."""
    return _tool_result(
        command="doctor",
        pack=pack,
        action=lambda: _doctor_payload(pack, operation, machine=True),
    )


@app.tool()
def evidence(pack: str, question: str) -> dict[str, Any]:
    """Return retrieval evidence chunks for external agent synthesis — no LLM answer included."""
    return _tool_result(
        command="evidence",
        pack=pack,
        action=lambda: _evidence_payload(pack, question, machine=True),
    )




@app.tool()
def build(
    pack: str,
    model: str = "small",
    language: str | None = None,
) -> dict[str, Any]:
    """Build or incrementally update a pack's index."""
    return _command_tool_result(
        command="build",
        pack=pack,
        action=lambda: _cli_build(pack=pack, model=model, language=language),
    )


@app.tool()
def add(source: str) -> dict[str, Any]:
    """Install a pack from a local path, URL, or registry slug."""
    return _command_tool_result(
        command="add",
        action=lambda: _cli_add(source=source),
    )


@app.tool()
def add_sources(pack: str, urls: list[str], model: str = "small", language: str | None = None) -> dict[str, Any]:
    """Add one or more source URLs to an existing pack and rebuild it."""
    def action() -> None:
        pack_dir = Path.home() / ".brainpacks" / pack
        config = load_config(pack_dir)
        updated = config
        for url in urls:
            updated = add_source_to_pack(updated, url)
        write_config(updated, pack_dir / "pack.yaml")
        _cli_build(pack=pack, model=model, language=language)

    return _command_tool_result(command="add_sources", pack=pack, action=action)


def run_stdio_server() -> None:
    """Run the Brainpack MCP server over stdio."""
    import sys
    print("Brainpack MCP server running on stdio.", file=sys.stderr)
    app.run(transport="stdio")
