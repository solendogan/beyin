"""Brainpack MCP server exposing machine-safe inventory and retrieval tools."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Any

import typer
from mcp.server.fastmcp import FastMCP

from brainpack import __version__
from brainpack.cli import (
    _doctor_payload,
    _chat_one_shot_payload,
    _list_payload,
    _query_payload,
    _status_payload,
    add,
    build,
)
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
def brainpack_list() -> dict[str, Any]:
    """List installed packs using Brainpack's stable machine-safe payload."""
    return _tool_result(command="list", action=lambda: _list_payload(machine=True))


@app.tool()
def brainpack_status(pack: str) -> dict[str, Any]:
    """Inspect one installed pack using Brainpack's stable machine-safe payload."""
    return _tool_result(
        command="status",
        pack=pack,
        action=lambda: _status_payload(pack, machine=True),
    )


@app.tool()
def brainpack_doctor(pack: str, operation: str = "all") -> dict[str, Any]:
    """Inspect structured pack readiness for query and build operations."""
    return _tool_result(
        command="doctor",
        pack=pack,
        action=lambda: _doctor_payload(pack, operation, machine=True),
    )


@app.tool()
def brainpack_query(pack: str, question: str) -> dict[str, Any]:
    """Run one cited retrieval query against a pack."""
    return _tool_result(
        command="query",
        pack=pack,
        action=lambda: _query_payload(pack, question, machine=True),
    )


@app.tool()
def brainpack_chat(pack: str, question: str) -> dict[str, Any]:
    """Run one one-shot chat query against a pack."""
    return _tool_result(
        command="chat",
        pack=pack,
        action=lambda: _chat_one_shot_payload(pack, question, machine=True),
    )


@app.tool()
def brainpack_build(
    pack: str,
    model: str = "small",
    language: str | None = None,
) -> dict[str, Any]:
    """Build or incrementally update a pack."""
    return _command_tool_result(
        command="build",
        pack=pack,
        action=lambda: build(pack=pack, model=model, language=language),
    )


@app.tool()
def brainpack_add(source: str) -> dict[str, Any]:
    """Install a pack from a local path, URL, or marketplace-style identifier."""
    return _command_tool_result(
        command="add",
        action=lambda: add(source=source),
    )


def run_stdio_server() -> None:
    """Run the Brainpack MCP server over stdio."""
    app.run(transport="stdio")
