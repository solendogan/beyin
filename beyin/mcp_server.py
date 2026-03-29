"""beyin MCP server exposing machine-safe inventory and retrieval tools."""

import json
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import typer
import yaml as pyyaml
from mcp.server.fastmcp import FastMCP

from beyin import __version__
from beyin.authoring import add_source_to_pack, remove_sources_from_pack
from beyin.lifecycle import remove_installed_pack
from beyin.cli import (
    add as _cli_add,
    build as _cli_build,
)
from beyin import cli as _cli_module
from beyin.payloads import (
    _list_payload,
    _retrieve_payload,
    _status_payload,
)
from beyin.paths import packs_dir
from beyin.config import _parse_config_from_raw, PackConfig, load_config, write_config
from beyin.inventory import serialize_pack_sources
from beyin.pack_state import load_state
from beyin.machine_output import (
    build_error_envelope,
    build_success_envelope,
    capture_machine_command,
)

app = FastMCP("beyin", json_response=True)


def _packs_root() -> Path:
    """Use the CLI pack root so MCP mutations and CLI commands stay aligned."""
    return _cli_module._PACKS_DIR


def _normalize_inline_yaml(raw_yaml: str) -> tuple[PackConfig, int]:
    """Parse inline YAML and expand playlist/feed sources before install."""
    data = pyyaml.safe_load(raw_yaml)
    if not isinstance(data, dict):
        raise ValueError("Inline YAML must define a pack object.")

    from beyin.downloader import expand_playlist_sources

    changed = False
    new_sources: list[Any] = []
    for source in data.get("sources") or []:
        url = source.get("url") if isinstance(source, dict) else source
        expansion = expand_playlist_sources(url) if url else None
        if expansion:
            for episode in expansion:
                new_sources.append(
                    {
                        "url": episode["url"],
                        "title": episode.get("title") or episode["url"],
                        "parent_url": url,
                        "parent_title": episode.get("parent_title"),
                    }
                )
            changed = True
        else:
            new_sources.append(source)
    if "sources" in data:
        data["sources"] = new_sources

    return _parse_config_from_raw(data), len(new_sources) if changed else 0


def _install_inline_yaml(raw_yaml: str) -> tuple[str, int]:
    """Install an inline pack YAML directly into the local packs directory."""
    config, expanded_count = _normalize_inline_yaml(raw_yaml)
    if not config.id:
        raise ValueError("Pack YAML must include a name or id.")

    dest_dir = _packs_root() / config.id
    if dest_dir.exists():
        raise ValueError(
            f"Pack '{config.id}' is already installed. Use update or remove it first."
        )

    dest_dir.mkdir(parents=True)
    write_config(config, dest_dir / "pack.yaml")
    return config.id, expanded_count


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
def retrieve(pack: str, queries: list[str]) -> dict[str, Any]:
    """Find the most relevant source passages for one or more queries.

    Pass multiple phrasings of the same question for better coverage — e.g.
    the original query, a keyword-focused version, and a reframed angle.
    All queries run in parallel internally; results are deduplicated and
    ranked by relevance before being returned.

    Example: queries=["when to show hard paywall", "paywall timing onboarding", "hard vs soft paywall LTV"]
    """
    return _tool_result(
        command="retrieve",
        pack=pack,
        action=lambda: _retrieve_payload(pack, queries, machine=True),
    )




@app.tool()
def build(
    pack: str,
    model: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Build or update a pack."""
    return _command_tool_result(
        command="build",
        pack=pack,
        action=lambda: _cli_build(
            pack=pack,
            sources=None,
            model=model,
            language=language,
            reset=False,
            verbose=False,
        ),
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
            try:
                pack_id, expanded_count = _install_inline_yaml(yaml)
            except ValueError as exc:
                typer.echo(f"Error: {exc}", err=True)
                raise typer.Exit(code=1)

            if expanded_count > 0:
                typer.echo(
                    f"Expanded to {expanded_count} source(s). "
                    "Review with the status tool and call build when ready."
                )
            typer.echo(
                f"Pack '{pack_id}' added to {_packs_root() / pack_id}/\n"
                f"Run `beyin build {pack_id}` to ingest sources."
            )

        return _command_tool_result(command="add", action=action)

    return _command_tool_result(
        command="add",
        action=lambda: _cli_add(source=source),
    )


@app.tool()
def add_sources(pack: str, urls: list[str], model: str | None = None, language: str | None = None) -> dict[str, Any]:
    """Add one or more sources to a pack. Rebuilds automatically for single sources. For playlists or RSS feeds, sources are expanded and saved individually — review with status tool, then call build when ready."""
    def action() -> None:
        pack_dir = _packs_root() / pack
        config = load_config(pack_dir)
        updated = config
        for url in urls:
            updated = add_source_to_pack(updated, url)
        new_count = len(updated.sources) - len(config.sources)
        write_config(updated, pack_dir / "pack.yaml")
        if new_count > 1:
            typer.echo(
                f"Added {new_count} source(s) to '{pack}'. "
                "Review sources with the status tool and call build when ready."
            )
        else:
            _cli_build(pack=pack, model=model, language=language)

    return _command_tool_result(command="add_sources", pack=pack, action=action)


@app.tool()
def remove_sources(
    pack: str,
    selectors: list[str],
    rebuild: bool = False,
    model: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Remove sources from a pack by current index or visible source text. Rebuild only when requested."""
    def action() -> None:
        pack_dir = _packs_root() / pack
        config = load_config(pack_dir)
        state = load_state(pack_dir)
        source_rows = serialize_pack_sources(config, state)
        try:
            updated, removed_rows = remove_sources_from_pack(
                config,
                selectors,
                source_rows=source_rows,
            )
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1)

        write_config(updated, pack_dir / "pack.yaml", previous=config)
        typer.echo(f"Removed {len(removed_rows)} source(s) from '{pack}'.")
        if rebuild:
            _cli_build(pack=pack, model=model, language=language)
        else:
            typer.echo(f"Next step: beyin build {pack}")

    return _command_tool_result(command="remove_sources", pack=pack, action=action)


@app.tool()
def remove(pack: str, confirm: bool = False) -> dict[str, Any]:
    """Remove a pack and move it to the OS trash. Must be called with confirm=True to proceed."""
    if not confirm:
        pack_dir = _packs_root() / pack
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
        action=lambda: remove_installed_pack(_packs_root() / pack),
    )


_REGISTRY_INDEX_URL = "https://raw.githubusercontent.com/buralog/beyin/main/packs/index.json"


@app.tool()
def registry(query: str = "") -> dict[str, Any]:
    """Browse the beyin community registry. Search by topic, tag, or keyword. Returns matching packs with install URLs."""
    meta = {"surface": "mcp", "server_version": __version__}
    try:
        with urllib.request.urlopen(_REGISTRY_INDEX_URL, timeout=10) as response:
            packs = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return build_error_envelope(
            command="registry",
            error_code="registry_fetch_failed",
            message=f"Could not fetch registry: {exc}",
            meta=meta,
        )

    if query:
        q = query.lower()
        packs = [
            p for p in packs
            if q in p.get("name", "").lower()
            or q in p.get("description", "").lower()
            or any(q in t.lower() for t in p.get("tags", []))
        ]

    for p in packs:
        p["install"] = f'Use the add tool with source="{p["url"]}" to install this pack.'

    return build_success_envelope(
        command="registry",
        data={"packs": packs, "total": len(packs)},
        meta=meta,
    )


def run_stdio_server() -> None:
    """Run the beyin MCP server over stdio."""
    import sys
    print("beyin MCP server running on stdio.", file=sys.stderr)
    try:
        app.run(transport="stdio")
    except BaseException as exc:
        if _is_expected_stdio_shutdown(exc):
            return
        raise
