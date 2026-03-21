"""Runtime loaders and payload builders for Brainpack query/retrieve/status surfaces."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from brainpack.config import PackConfig, load_config
from brainpack.inventory import (
    inspect_pack,
    list_packs,
    next_action_reason,
    pack_config_hash,
    serialize_pack_detail,
    serialize_pack_summary,
)
from brainpack.machine_output import MachineExit
from brainpack.pack_state import load_state
from brainpack.readiness import _query_provider_error
from brainpack.settings import load_settings


# ── Pure helpers (no cli deps) ────────────────────────────────────────────────

def _split_machine_message(message: str) -> tuple[str, dict[str, str]]:
    """Split a multi-line human error into a machine message plus details."""
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines:
        return message, {}
    if len(lines) == 1:
        return lines[0], {}
    return lines[0], {"hint": " ".join(lines[1:])}


def _has_successful_build(state: dict) -> bool:
    if state.get("last_build_at"):
        return True
    processed = state.get("processed", {})
    if any(item.get("status") == "done" for item in processed.values()):
        return True
    audio_steps = state.get("audio_steps", {})
    return any(step.get("stages", {}).get("embedded") for step in audio_steps.values())


def _has_failed_build(state: dict) -> bool:
    return any(item.get("status") == "failed" for item in state.get("processed", {}).values())


def _retrieval_precondition_summary(status: str, pack: str) -> dict:
    next_action = f"brainpack build {pack}"
    return {
        "status": status,
        "next_action": next_action,
        "blockers": [],
        "warnings": [],
    }


def _serialize_query_source(source: dict) -> dict:
    """Return the stable public source payload for retrieval JSON output."""
    payload = {
        "url": source.get("url", ""),
        "title": source.get("title", "Unknown"),
    }
    if source.get("timestamp_start") is not None:
        payload["timestamp_start"] = source["timestamp_start"]
    if source.get("timestamp_end") is not None:
        payload["timestamp_end"] = source["timestamp_end"]
    return payload


def _serialize_retrieve_item(item: dict) -> dict:
    """Return the stable public retrieval result item."""
    payload = {
        "text": item.get("text", ""),
        "url": item.get("url", ""),
        "title": item.get("title", "Unknown"),
        "rank": item.get("rank"),
    }
    if item.get("distance") is not None:
        payload["distance"] = item["distance"]
    if item.get("timestamp_start") is not None:
        payload["timestamp_start"] = item["timestamp_start"]
    if item.get("timestamp_end") is not None:
        payload["timestamp_end"] = item["timestamp_end"]
    return payload


def _build_retrieval_payload(question: str, result: dict, *, machine: bool = False) -> dict:
    """Normalize retrieval results for shared query payload construction."""
    if not machine:
        sources = result["sources"]
    else:
        sources = [_serialize_query_source(source) for source in result["sources"]]
    return {
        "question": question,
        "answer": result["answer"],
        "sources": sources,
    }


def _build_retrieve_payload(question: str, results: list[dict], *, machine: bool = False) -> dict:
    """Normalize retrieval results for the MCP retrieve contract."""
    if machine:
        items = [_serialize_retrieve_item(item) for item in results]
    else:
        items = results
    return {
        "question": question,
        "results": items,
    }


# ── Precondition helpers ──────────────────────────────────────────────────────

def _raise_retrieval_precondition(
    pack: str,
    code: str,
    message: str,
    summary: dict,
    *,
    machine_command: Optional[str] = None,
    include_blocker: bool = False,
) -> None:
    """Stop retrieval flows with consistent human and machine precondition guidance."""
    details = {
        "next_action": summary["next_action"],
        "reason": next_action_reason(summary),
    }
    if include_blocker and summary.get("blockers"):
        blocker_message, _ = _split_machine_message(summary["blockers"][0])
        details["blocker"] = blocker_message
    if machine_command:
        raise MachineExit.precondition(
            code,
            message,
            pack=pack,
            details=details,
        )
    typer.echo(message, err=True)
    if include_blocker and summary.get("blockers"):
        typer.echo(f"Why: {summary['blockers'][0]}", err=True)
    typer.echo("", err=True)
    from brainpack import cli as _cli
    _cli._render_usage_guidance(summary, err=True)
    raise typer.Exit(code=1)


# ── Runtime loaders ───────────────────────────────────────────────────────────

def _load_query_runtime(
    pack: str,
    *,
    machine_command: Optional[str] = None,
) -> tuple[Path, PackConfig, object, object]:
    """Load pack config and retrieval runtime for query surfaces."""
    from brainpack import cli as _cli
    pack_dir = _cli._resolve_pack_dir(pack, machine_command=machine_command)
    config = _cli.load_config(pack_dir)
    provider_error = _cli._query_provider_error(config.llm)
    if provider_error is not None:
        if machine_command:
            message, details = _split_machine_message(provider_error)
            raise MachineExit.precondition(
                "runtime_blocked",
                message,
                pack=pack,
                details=details,
            )
        typer.echo(provider_error, err=True)
        raise typer.Exit(code=1)
    summary = inspect_pack(pack_dir, _cli._pack_readiness_details)
    state = _cli.load_state(pack_dir)
    has_build = _has_successful_build(state)
    current_hash = pack_config_hash(pack_dir)
    last_build_hash = state.get("last_built_pack_hash")
    needs_build = bool(has_build and last_build_hash and last_build_hash != current_hash)
    status = summary["status"]
    if status == "new" or not has_build:
        _raise_retrieval_precondition(
            pack,
            code="pack_not_built",
            message=f"Pack '{pack}' is not built yet.",
            summary=summary,
            machine_command=machine_command,
        )
    if status == "needs-build" or needs_build:
        _raise_retrieval_precondition(
            pack,
            code="pack_needs_build",
            message=(
                f"Pack '{pack}' changed after its last build and needs a rebuild before query can continue."
            ),
            summary=summary,
            machine_command=machine_command,
        )
    if status == "error" and not has_build:
        _raise_retrieval_precondition(
            pack,
            code="pack_build_failed",
            message=f"Pack '{pack}' needs a successful build before query can continue.",
            summary=summary,
            machine_command=machine_command,
        )
    model = _cli.load_model(config.embedding_model)
    collection = _cli.get_collection(pack_dir, config.id)
    return pack_dir, config, model, collection


def _load_evidence_runtime(
    pack: str,
    *,
    machine_command: Optional[str] = None,
) -> tuple[Path, PackConfig, object, object]:
    """Load retrieval-only runtime without requiring answer-provider readiness."""
    from brainpack import cli as _cli
    pack_dir = _cli._resolve_pack_dir(pack, machine_command=machine_command)
    config = _cli.load_config(pack_dir)
    state = _cli.load_state(pack_dir)
    has_build = _has_successful_build(state)
    current_hash = pack_config_hash(pack_dir)
    last_build_hash = state.get("last_built_pack_hash")
    needs_build = bool(has_build and last_build_hash and last_build_hash != current_hash)
    has_error = _has_failed_build(state)

    if has_error and not has_build:
        _raise_retrieval_precondition(
            pack,
            code="pack_build_failed",
            message=f"Pack '{pack}' needs a successful build before retrieve can continue.",
            summary=_retrieval_precondition_summary("error", pack),
            machine_command=machine_command,
        )
    if not has_build:
        _raise_retrieval_precondition(
            pack,
            code="pack_not_built",
            message=f"Pack '{pack}' is not built yet.",
            summary=_retrieval_precondition_summary("new", pack),
            machine_command=machine_command,
        )
    if needs_build:
        _raise_retrieval_precondition(
            pack,
            code="pack_needs_build",
            message=(
                f"Pack '{pack}' changed after its last build and needs a rebuild before retrieve can continue."
            ),
            summary=_retrieval_precondition_summary("needs-build", pack),
            machine_command=machine_command,
        )
    model = _cli.load_model(config.embedding_model)
    collection = _cli.get_collection(pack_dir, config.id)
    return pack_dir, config, model, collection


# ── Payload builders ──────────────────────────────────────────────────────────

def _query_payload(
    pack: str,
    question: str,
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable result payload for query."""
    from brainpack import cli as _cli
    _, config, model, collection = _load_query_runtime(
        pack,
        machine_command="query" if machine else None,
    )
    result = _cli.run_query(
        question=question,
        collection=collection,
        model=model,
        llm_provider=config.llm,
        llm_model=load_settings().preferred_llm_model,
    )
    return _build_retrieval_payload(question, result, machine=machine)


def _retrieve_payload(
    pack: str,
    question: str,
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable retrieval-only payload for MCP."""
    from brainpack import cli as _cli
    _, _, model, collection = _load_evidence_runtime(
        pack,
        machine_command="retrieve" if machine else None,
    )
    results = _cli.retrieve_evidence(question=question, collection=collection, model=model)
    return _build_retrieve_payload(question, results, machine=machine)


def _list_payload(
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable inventory payload for machine-safe list output."""
    from brainpack import cli as _cli
    packs = list_packs(_cli._PACKS_DIR, _cli._pack_readiness_details)
    if machine:
        return {"packs": [serialize_pack_summary(summary) for summary in packs]}
    return {"packs": packs}


def _status_payload(
    pack: str,
    *,
    machine: bool = False,
) -> dict:
    """Build a reusable inventory payload for machine-safe status output."""
    from brainpack import cli as _cli
    pack_dir = _cli._resolve_pack_dir(pack, machine_command="status" if machine else None)
    summary = inspect_pack(pack_dir, _cli._pack_readiness_details)
    if machine:
        return {"pack": serialize_pack_detail(summary)}
    return {"pack": summary}
