"""Brainpack MCP server exposing machine-safe inventory and retrieval tools."""

import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Any

import typer
from mcp.server.fastmcp import FastMCP

from brainpack import __version__
from brainpack.authoring import add_source_to_pack
from brainpack.lifecycle import remove_installed_pack
from brainpack.cli import (
    add as _cli_add,
    build as _cli_build,
)
from brainpack.payloads import (
    _list_payload,
    _retrieve_payload,
    _status_payload,
)
from brainpack.paths import packs_dir
from brainpack.config import load_config, write_config
from brainpack.machine_output import (
    build_error_envelope,
    build_success_envelope,
    capture_machine_command,
)

app = FastMCP("Brainpack", json_response=True)


def _is_expected_stdio_shutdown(exc: BaseException) -> bool:
    """Return True for normal stdio server shutdown exceptions."""
    if isinstance(exc, (KeyboardInterrupt, BrokenPipeError, EOFError)):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return all(_is_expected_stdio_shutdown(child) for child in exc.exceptions)
    return False


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
    """List your installed packs."""
    return _tool_result(command="list", action=lambda: _list_payload(machine=True))


@app.tool()
def status(pack: str) -> dict[str, Any]:
    """Show details for one pack."""
    return _tool_result(
        command="status",
        pack=pack,
        action=lambda: _status_payload(pack, machine=True),
    )


@app.tool()
def retrieve(pack: str, query: str) -> dict[str, Any]:
    """Find the most relevant source passages for a query."""
    return _tool_result(
        command="retrieve",
        pack=pack,
        action=lambda: _retrieve_payload(pack, query, machine=True),
    )




@app.tool()
def build(
    pack: str,
    model: str = "small",
    language: str | None = None,
) -> dict[str, Any]:
    """Build or update a pack."""
    return _command_tool_result(
        command="build",
        pack=pack,
        action=lambda: _cli_build(pack=pack, model=model, language=language),
    )


@app.tool()
def add(source: str | None = None, yaml: str | None = None) -> dict[str, Any]:
    """Add a pack from a path, URL, registry id, or pasted YAML."""
    if bool(source) == bool(yaml):
        return build_error_envelope(
            command="add",
            error_code="invalid_add_input",
            message="Provide exactly one of 'source' or 'yaml'.",
            meta={"surface": "mcp", "server_version": __version__},
        )

    if yaml is not None:
        def action() -> None:
            with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=True, encoding="utf-8") as handle:
                handle.write(yaml)
                handle.flush()
                _cli_add(source=handle.name)

        return _command_tool_result(command="add", action=action)

    return _command_tool_result(
        command="add",
        action=lambda: _cli_add(source=source),
    )


@app.tool()
def add_sources(pack: str, urls: list[str], model: str = "small", language: str | None = None) -> dict[str, Any]:
    """Add source URLs to a pack and rebuild it."""
    def action() -> None:
        pack_dir = packs_dir() / pack
        config = load_config(pack_dir)
        updated = config
        for url in urls:
            updated = add_source_to_pack(updated, url)
        write_config(updated, pack_dir / "pack.yaml")
        _cli_build(pack=pack, model=model, language=language)

    return _command_tool_result(command="add_sources", pack=pack, action=action)


@app.tool()
def remove(pack: str, confirm: bool = False) -> dict[str, Any]:
    """Remove a pack and move it to the OS trash. Must be called with confirm=True to proceed."""
    if not confirm:
        pack_dir = packs_dir() / pack
        if not pack_dir.exists():
            return {"ok": False, "error": f"Pack '{pack}' not found."}
        return {
            "ok": True,
            "data": {
                "warning": f"This will move pack '{pack}' and all its data to the trash. Call again with confirm=True to proceed.",
                "pack": pack,
            },
        }

    return _command_tool_result(
        command="remove",
        pack=pack,
        action=lambda: remove_installed_pack(packs_dir() / pack),
    )


def run_stdio_server() -> None:
    """Run the Brainpack MCP server over stdio."""
    import sys
    print("Brainpack MCP server running on stdio.", file=sys.stderr)
    try:
        app.run(transport="stdio")
    except BaseException as exc:
        if _is_expected_stdio_shutdown(exc):
            return
        raise
