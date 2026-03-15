"""Machine-safe CLI contract tests."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from brainpack.machine_output import (
    CLI_SCHEMA_VERSION,
    MachineExit,
    build_error_envelope,
    build_success_envelope,
    emit_json,
    run_machine_command,
)


def _write_pack(
    pack_dir: Path,
    *,
    name: str,
    llm: str = "openai",
    sources: list[str] | None = None,
) -> None:
    urls = sources or ["https://example.com/article"]
    source_lines = "\n".join(f"  - {url}" for url in urls)
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        f"name: {name}\n"
        "description: Test pack\n"
        f"llm: {llm}\n"
        "sources:\n"
        f"{source_lines}\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )


def _mark_pack_built(pack_dir: Path, *, last_build_at: str) -> None:
    from brainpack.inventory import pack_config_hash
    from brainpack.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {},
            "last_build_at": last_build_at,
            "last_built_pack_hash": pack_config_hash(pack_dir),
        },
    )


def _mark_pack_stale(pack_dir: Path, *, last_build_at: str) -> None:
    from brainpack.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {},
            "last_build_at": last_build_at,
            "last_built_pack_hash": "outdated-hash",
        },
    )


def _mark_pack_failed(pack_dir: Path) -> None:
    from brainpack.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {
                "https://example.com/article": {"status": "failed"},
            },
            "audio_steps": {},
        },
    )


def _save_origin(pack_dir: Path, *, source: str, added_at: str, last_updated_at: str | None = None) -> None:
    from brainpack.inventory import save_pack_origin

    origin = {
        "type": "file",
        "source": source,
        "resolved": source,
        "added_at": added_at,
    }
    if last_updated_at is not None:
        origin["last_updated_at"] = last_updated_at
    save_pack_origin(pack_dir, origin)


def _parse_output(result) -> dict:
    return json.loads(result.output)


def _assert_single_machine_document(result, *, ok: bool) -> dict:
    """Assert one parseable JSON document with the shared top-level contract."""
    assert result.output.count("\n") == 1
    assert result.output.startswith("{")
    assert result.output.endswith("}\n")
    payload = _parse_output(result)
    expected_keys = {"ok", "meta", "warnings", "data" if ok else "error"}
    assert set(payload.keys()) == expected_keys
    assert payload["ok"] is ok
    assert payload["meta"]["schema"] == CLI_SCHEMA_VERSION
    return payload


def test_success_envelope_uses_shared_schema_and_top_level_shape():
    """Success responses keep one stable top-level envelope."""
    envelope = build_success_envelope(
        command="list",
        data={"packs": []},
    )

    assert envelope == {
        "ok": True,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "list",
        },
        "data": {"packs": []},
        "warnings": [],
    }


def test_error_envelope_uses_shared_schema_and_top_level_shape():
    """Failure responses reuse the same envelope contract."""
    envelope = build_error_envelope(
        command="status",
        error_code="pack_not_found",
        message="Pack 'missing-pack' is not installed.",
        pack="missing-pack",
        details={"next_action": "brainpack create"},
    )

    assert envelope == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "status",
            "pack": "missing-pack",
        },
        "error": {
            "code": "pack_not_found",
            "message": "Pack 'missing-pack' is not installed.",
            "details": {"next_action": "brainpack create"},
        },
        "warnings": [],
    }


def test_emit_json_writes_one_schema_document_to_stdout(capsys):
    """Machine JSON emission writes one parseable document and nothing else."""
    emit_json(
        build_success_envelope(
            command="list",
            data={"packs": []},
        )
    )

    captured = capsys.readouterr()

    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["meta"]["schema"] == CLI_SCHEMA_VERSION
    assert payload["ok"] is True
    assert captured.out.strip().startswith("{")
    assert captured.out.strip().endswith("}")


def test_machine_exit_code_taxonomy_is_small_and_stable():
    """Covered machine failures map onto the fixed exit-code taxonomy."""
    usage_error = MachineExit.usage(
        "interactive_json_not_supported",
        "brainpack chat --json requires a question argument",
    )
    precondition_error = MachineExit.precondition(
        "pack_not_found",
        "Pack 'missing-pack' is not installed.",
    )

    assert usage_error.exit_code == 2
    assert precondition_error.exit_code == 3


def test_run_machine_command_normalizes_unexpected_error_to_shared_envelope_and_exit_code(
    capsys,
):
    """Unexpected exceptions become one shared machine error response."""

    def explode() -> dict:
        raise RuntimeError("boom")

    exit_code = run_machine_command(
        command="query",
        pack="demo-pack",
        action=explode,
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 4
    assert captured.err == ""
    assert payload == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "query",
            "pack": "demo-pack",
        },
        "error": {
            "code": "unexpected_error",
            "message": "Unexpected error while running command.",
            "details": {"type": "RuntimeError"},
        },
        "warnings": [],
    }


def test_list_json_returns_shared_envelope_for_empty_inventory(tmp_path):
    """list --json returns the shared envelope with an empty packs array."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["list", "--json"])

    assert result.exit_code == 0
    assert _parse_output(result) == {
        "ok": True,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "list",
        },
        "data": {"packs": []},
        "warnings": [],
    }


def test_list_json_serializes_multiple_packs_without_internal_objects(tmp_path):
    """list --json exposes explicit public fields instead of raw inventory internals."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    alpha_pack = packs_root / "alpha-pack"
    beta_pack = packs_root / "beta-pack"
    _write_pack(
        alpha_pack,
        name="alpha-pack",
        sources=[
            "https://example.com/article",
            "https://example.com/other",
        ],
    )
    _write_pack(beta_pack, name="beta-pack")
    _mark_pack_built(alpha_pack, last_build_at="2026-03-13T10:00:00+00:00")
    _mark_pack_built(beta_pack, last_build_at="2026-03-10T10:00:00+00:00")
    _save_origin(
        alpha_pack,
        source="/tmp/alpha-pack.yaml",
        added_at="2026-03-11T09:00:00+00:00",
        last_updated_at="2026-03-12T09:00:00+00:00",
    )
    _save_origin(
        beta_pack,
        source="/tmp/beta-pack.yaml",
        added_at="2026-03-09T09:00:00+00:00",
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ):
        result = runner.invoke(app, ["list", "--json"])

    payload = _parse_output(result)

    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["meta"] == {
        "schema": CLI_SCHEMA_VERSION,
        "command": "list",
    }
    assert payload["data"] == {
        "packs": [
            {
                "name": "alpha-pack",
                "status": "ready",
                "type": "text",
                "provider": "openai",
                "source_count": 2,
                "recent_summary": "build 2026-03-13 / upd 2026-03-12",
                "next_action": 'brainpack query alpha-pack "question"',
                "blockers": [],
                "warnings": [],
                "origin": {
                    "type": "file",
                    "source": "/tmp/alpha-pack.yaml",
                },
            },
            {
                "name": "beta-pack",
                "status": "ready",
                "type": "text",
                "provider": "openai",
                "source_count": 1,
                "recent_summary": "build 2026-03-10 / upd 2026-03-09",
                "next_action": 'brainpack query beta-pack "question"',
                "blockers": [],
                "warnings": [],
                "origin": {
                    "type": "file",
                    "source": "/tmp/beta-pack.yaml",
                },
            },
        ]
    }
    for pack in payload["data"]["packs"]:
        assert "config" not in pack
        assert "state" not in pack


def test_status_json_returns_ready_pack_detail_without_internal_objects(tmp_path):
    """status --json returns one normalized pack detail object for ready packs."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "ready-pack"
    _write_pack(
        pack_dir,
        name="ready-pack",
        sources=[
            "https://example.com/article",
            "https://example.com/other",
        ],
    )
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")
    _save_origin(
        pack_dir,
        source="/tmp/ready-pack.yaml",
        added_at="2026-03-11T09:00:00+00:00",
        last_updated_at="2026-03-12T09:00:00+00:00",
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ):
        result = runner.invoke(app, ["status", "ready-pack", "--json"])

    payload = _parse_output(result)

    assert result.exit_code == 0
    assert payload == {
        "ok": True,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "status",
            "pack": "ready-pack",
        },
        "data": {
            "pack": {
                "name": "ready-pack",
                "status": "ready",
                "type": "text",
                "provider": "openai",
                "source_count": 2,
                "recent_summary": "build 2026-03-13 / upd 2026-03-12",
                "next_action": 'brainpack query ready-pack "question"',
                "blockers": [],
                "warnings": [],
                "origin": {
                    "type": "file",
                    "source": "/tmp/ready-pack.yaml",
                },
                "last_build_at": "2026-03-13T10:00:00+00:00",
                "last_update_at": "2026-03-12T09:00:00+00:00",
                "last_update_summary": [],
            }
        },
        "warnings": [],
    }
    assert "config" not in payload["data"]["pack"]
    assert "state" not in payload["data"]["pack"]


def test_status_json_returns_blocked_pack_detail_without_internal_objects(tmp_path):
    """status --json returns blocked pack detail without leaking config or state objects."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "blocked-pack"
    _write_pack(pack_dir, name="blocked-pack")
    _save_origin(
        pack_dir,
        source="/tmp/blocked-pack.yaml",
        added_at="2026-03-11T09:00:00+00:00",
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        result = runner.invoke(app, ["status", "blocked-pack", "--json"])

    payload = _parse_output(result)
    detail = payload["data"]["pack"]

    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["meta"] == {
        "schema": CLI_SCHEMA_VERSION,
        "command": "status",
        "pack": "blocked-pack",
    }
    assert detail["name"] == "blocked-pack"
    assert detail["status"] == "blocked"
    assert detail["type"] == "text"
    assert detail["provider"] == "openai"
    assert detail["source_count"] == 1
    assert detail["recent_summary"] == "upd 2026-03-11"
    assert detail["next_action"] == "brainpack doctor blocked-pack"
    assert detail["blockers"] == ["Error: OPENAI_API_KEY is not set."]
    assert detail["warnings"] == []
    assert detail["origin"] == {
        "type": "file",
        "source": "/tmp/blocked-pack.yaml",
    }
    assert detail["last_build_at"] is None
    assert detail["last_update_at"] == "2026-03-11T09:00:00+00:00"
    assert detail["last_update_summary"] == []
    assert "config" not in detail
    assert "state" not in detail


def test_status_json_missing_pack_returns_structured_error_and_exact_exit_code(tmp_path):
    """status --json returns the shared missing-pack error envelope with exit code 3."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["status", "missing-pack", "--json"])

    assert result.exit_code == 3
    assert _parse_output(result) == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "status",
            "pack": "missing-pack",
        },
        "error": {
            "code": "pack_not_found",
            "message": "Pack 'missing-pack' is not installed.",
            "details": {"next_action": "brainpack add <path-or-url-or-id>"},
        },
        "warnings": [],
    }


def test_list_json_does_not_load_interactive_prompts_when_settings_are_missing(tmp_path):
    """Machine-safe list stays non-interactive even on a fresh machine."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli.load_prompt_backend",
        side_effect=AssertionError("interactive backend should stay unloaded"),
    ):
        result = runner.invoke(app, ["list", "--json"])

    assert result.exit_code == 0
    assert _parse_output(result)["ok"] is True


def test_status_json_does_not_load_interactive_prompts(tmp_path):
    """status --json must not touch the interactive layer."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "ready-pack"
    _write_pack(pack_dir, name="ready-pack")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ), patch(
        "brainpack.cli.load_prompt_backend",
        side_effect=AssertionError("interactive backend should stay unloaded"),
    ):
        result = runner.invoke(app, ["status", "ready-pack", "--json"])

    assert result.exit_code == 0
    assert _parse_output(result)["ok"] is True


def test_status_json_ignores_saved_mode_preferences_and_stays_machine_safe(
    monkeypatch,
    tmp_path,
):
    """Saved human guidance preferences must not change the status --json contract."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.cli import app
    from brainpack.settings import BrainpackSettings, save_settings

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "ready-pack"
    _write_pack(pack_dir, name="ready-pack")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")
    save_settings(
        BrainpackSettings(
            version=1,
            setup_completed=True,
            preferred_mode="local",
            audio_enabled_by_default=False,
            preferred_transcription_backend="faster-whisper",
            preferred_whisper_model="medium",
            preferred_local_provider="openai",
        )
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ), patch(
        "brainpack.interactive.load_prompt_backend",
        side_effect=AssertionError("interactive backend should stay unloaded"),
    ):
        result = runner.invoke(app, ["status", "ready-pack", "--json"])

    payload = _parse_output(result)

    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["meta"]["command"] == "status"
    assert "Use with local model" not in result.output


def test_query_json_returns_shared_answer_and_sources_payload(tmp_path):
    """query --json returns the shared retrieval payload inside the machine envelope."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "query-pack"
    _write_pack(pack_dir, name="query-pack")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    mock_result = {
        "answer": "Structured answer",
        "sources": [
            {
                "url": "https://example.com/article",
                "title": "Example Article",
                "timestamp_start": 12.0,
                "timestamp_end": 34.0,
                "source_id": "internal-source-id",
            }
        ],
    }

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ), patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ), patch(
        "brainpack.cli.run_query",
        return_value=mock_result,
    ):
        result = runner.invoke(app, ["query", "query-pack", "What happened?", "--json"])

    assert result.exit_code == 0
    assert _parse_output(result) == {
        "ok": True,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "query",
            "pack": "query-pack",
        },
        "data": {
            "question": "What happened?",
            "answer": "Structured answer",
            "sources": [
                {
                    "url": "https://example.com/article",
                    "title": "Example Article",
                    "timestamp_start": 12.0,
                    "timestamp_end": 34.0,
                }
            ],
        },
        "warnings": [],
    }


def test_query_json_does_not_load_interactive_prompts(tmp_path):
    """query --json must remain prompt-free even when settings are absent."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "query-pack"
    _write_pack(pack_dir, name="query-pack")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ), patch(
        "brainpack.cli.load_prompt_backend",
        side_effect=AssertionError("interactive backend should stay unloaded"),
    ), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ), patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ), patch(
        "brainpack.cli.run_query",
        return_value={"answer": "ok", "sources": []},
    ):
        result = runner.invoke(app, ["query", "query-pack", "What happened?", "--json"])

    assert result.exit_code == 0
    assert _parse_output(result)["ok"] is True


def test_load_evidence_runtime_allows_built_openai_pack_without_api_key(tmp_path):
    from brainpack.cli import _load_evidence_runtime

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "evidence-pack"
    _write_pack(pack_dir, name="evidence-pack", llm="openai")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ) as mock_load_model, patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ) as mock_get_collection:
        _, config, _, _ = _load_evidence_runtime("evidence-pack", machine_command="evidence")

    assert config.llm == "openai"
    mock_load_model.assert_called_once_with("all-MiniLM-L6-v2")
    mock_get_collection.assert_called_once()


def test_load_evidence_runtime_allows_built_ollama_pack_without_reachability_check(tmp_path):
    from brainpack.cli import _load_evidence_runtime

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "ollama-pack"
    _write_pack(pack_dir, name="ollama-pack", llm="ollama")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli._check_ollama_reachable",
        return_value=False,
    ) as mock_reachable, patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ), patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ):
        _load_evidence_runtime("ollama-pack", machine_command="evidence")

    mock_reachable.assert_not_called()


@pytest.mark.parametrize(
    ("status_setup", "expected_code", "expected_message"),
    [
        ("new", "pack_not_built", "Pack 'blocked-pack' is not built yet."),
        (
            "needs-build",
            "pack_needs_build",
            "Pack 'blocked-pack' changed after its last build and needs a rebuild before evidence retrieval can continue.",
        ),
        (
            "error",
            "pack_build_failed",
            "Pack 'blocked-pack' needs a successful build before evidence retrieval can continue.",
        ),
    ],
)
def test_load_evidence_runtime_blocks_on_pack_state_only(
    tmp_path,
    status_setup,
    expected_code,
    expected_message,
):
    from brainpack.cli import _load_evidence_runtime
    from brainpack.machine_output import MachineExit

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "blocked-pack"
    _write_pack(pack_dir, name="blocked-pack", llm="openai")

    if status_setup == "needs-build":
        _mark_pack_stale(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")
    elif status_setup == "error":
        _mark_pack_failed(pack_dir)

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        with pytest.raises(MachineExit) as exc_info:
            _load_evidence_runtime("blocked-pack", machine_command="evidence")

    exc = exc_info.value
    assert exc.code == expected_code
    assert exc.message == expected_message


def test_build_evidence_payload_returns_question_and_evidence_without_answer():
    from brainpack.cli import _build_evidence_payload

    payload = _build_evidence_payload(
        "What happened?",
        [
            {
                "text": "Chunk A",
                "url": "https://example.com/a",
                "title": "Article A",
                "rank": 1,
                "distance": 0.11,
                "timestamp_start": 12.0,
                "timestamp_end": 34.0,
            }
        ],
        machine=True,
    )

    assert payload == {
        "question": "What happened?",
        "evidence": [
            {
                "text": "Chunk A",
                "url": "https://example.com/a",
                "title": "Article A",
                "rank": 1,
                "distance": 0.11,
                "timestamp_start": 12.0,
                "timestamp_end": 34.0,
            }
        ],
    }


def test_chat_one_shot_json_matches_query_payload_shape(tmp_path):
    """chat --json one-shot returns the same retrieval payload shape as query --json."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "chat-pack"
    _write_pack(pack_dir, name="chat-pack")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    mock_result = {
        "answer": "Structured answer",
        "sources": [
            {
                "url": "https://example.com/article",
                "title": "Example Article",
                "timestamp_start": 12.0,
                "timestamp_end": 34.0,
                "source_id": "internal-source-id",
            }
        ],
    }

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ), patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ), patch(
        "brainpack.cli.run_query",
        return_value=mock_result,
    ):
        result = runner.invoke(
            app,
            ["chat", "chat-pack", "What happened?", "--json"],
        )

    payload = _parse_output(result)

    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["meta"] == {
        "schema": CLI_SCHEMA_VERSION,
        "command": "chat",
        "pack": "chat-pack",
    }
    assert payload["data"] == {
        "question": "What happened?",
        "answer": "Structured answer",
        "sources": [
            {
                "url": "https://example.com/article",
                "title": "Example Article",
                "timestamp_start": 12.0,
                "timestamp_end": 34.0,
            }
        ],
    }


def test_chat_json_does_not_load_interactive_prompts(tmp_path):
    """chat --json one-shot must not import or invoke the prompt layer."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "chat-pack"
    _write_pack(pack_dir, name="chat-pack")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ), patch(
        "brainpack.cli.load_prompt_backend",
        side_effect=AssertionError("interactive backend should stay unloaded"),
    ), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ), patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ), patch(
        "brainpack.cli.run_query",
        return_value={"answer": "ok", "sources": []},
    ):
        result = runner.invoke(app, ["chat", "chat-pack", "What happened?", "--json"])

    assert result.exit_code == 0
    assert _parse_output(result)["ok"] is True


def test_non_interactive_json_execution_keeps_inquirerpy_unloaded(tmp_path):
    """A machine-safe command should leave the prompt dependency unloaded."""
    removed = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "InquirerPy" or name.startswith("InquirerPy.")
    }

    try:
        from brainpack.cli import app

        runner = CliRunner()
        packs_root = tmp_path / "brainpacks"

        with patch("brainpack.cli._PACKS_DIR", packs_root):
            result = runner.invoke(app, ["list", "--json"])

        assert result.exit_code == 0
        assert not any(
            name == "InquirerPy" or name.startswith("InquirerPy.")
            for name in sys.modules
        )
    finally:
        sys.modules.update(removed)


def test_query_json_missing_pack_returns_structured_error_without_prose_leakage(tmp_path):
    """query --json missing-pack failures stay inside the shared error envelope."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["query", "missing-pack", "What happened?", "--json"])

    assert result.exit_code == 3
    assert result.output.strip().startswith("{")
    assert "Next step:" not in result.output
    assert "Sources:" not in result.output
    assert _parse_output(result) == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "query",
            "pack": "missing-pack",
        },
        "error": {
            "code": "pack_not_found",
            "message": "Pack 'missing-pack' is not installed.",
            "details": {"next_action": "brainpack add <path-or-url-or-id>"},
        },
        "warnings": [],
    }


def test_query_json_missing_api_key_returns_structured_runtime_blocked_error(tmp_path):
    """query --json turns provider readiness failures into structured JSON."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "openai-pack"
    _write_pack(pack_dir, name="openai-pack", llm="openai")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        result = runner.invoke(app, ["query", "openai-pack", "What happened?", "--json"])

    assert result.exit_code == 3
    assert "Next step:" not in result.output
    assert _parse_output(result) == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "query",
            "pack": "openai-pack",
        },
        "error": {
            "code": "runtime_blocked",
            "message": "Error: OPENAI_API_KEY is not set.",
            "details": {
                "hint": "Set it in your shell environment, then retry.",
            },
        },
        "warnings": [],
    }


def test_chat_json_missing_pack_returns_structured_error_without_prose_leakage(tmp_path):
    """chat --json missing-pack failures stay machine-safe and skip onboarding prose."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["chat", "missing-pack", "What happened?", "--json"])

    assert result.exit_code == 3
    assert "Next step:" not in result.output
    assert "Chatting with" not in result.output
    assert _parse_output(result) == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "chat",
            "pack": "missing-pack",
        },
        "error": {
            "code": "pack_not_found",
            "message": "Pack 'missing-pack' is not installed.",
            "details": {
                "next_action": "brainpack create",
                "note": "Use `brainpack add <path-or-url-or-id>` if you already have a pack.yaml to import.",
            },
        },
        "warnings": [],
    }


def test_chat_json_blocked_pack_returns_structured_error_and_exact_exit_code(tmp_path):
    """chat --json returns a structured blocked-pack error instead of human guidance prose."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "blocked-pack"
    _write_pack(pack_dir, name="blocked-pack", llm="openai")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        result = runner.invoke(app, ["chat", "blocked-pack", "What happened?", "--json"])

    assert result.exit_code == 3
    assert "Next step:" not in result.output
    assert "Why:" not in result.output
    assert _parse_output(result) == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "chat",
            "pack": "blocked-pack",
        },
        "error": {
            "code": "pack_blocked",
            "message": "Pack 'blocked-pack' is blocked before chat can start.",
            "details": {
                "next_action": "brainpack doctor blocked-pack",
                "reason": "Resolve the blocker so this pack is ready for agent or local-model use.",
                "blocker": "Error: OPENAI_API_KEY is not set.",
            },
        },
        "warnings": [],
    }


def test_chat_json_without_question_is_rejected_as_usage_error(tmp_path):
    """interactive chat --json is rejected explicitly instead of starting a session."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "chat-pack"
    _write_pack(pack_dir, name="chat-pack")

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["chat", "chat-pack", "--json"])

    assert result.exit_code == 2
    assert "Chatting with" not in result.output
    assert _parse_output(result) == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "chat",
            "pack": "chat-pack",
        },
        "error": {
            "code": "interactive_json_not_supported",
            "message": "brainpack chat --json requires a question argument",
            "details": {},
        },
        "warnings": [],
    }


def test_machine_json_commands_emit_one_document_with_stable_top_level_keys(tmp_path):
    """Covered --json commands emit one machine document with stable success/failure keys."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    ready_pack = packs_root / "ready-pack"
    _write_pack(ready_pack, name="ready-pack")
    _mark_pack_built(ready_pack, last_build_at="2026-03-13T10:00:00+00:00")

    status_pack = packs_root / "status-pack"
    _write_pack(status_pack, name="status-pack", llm="openai")
    _mark_pack_built(status_pack, last_build_at="2026-03-13T10:00:00+00:00")

    mock_result = {
        "answer": "Structured answer",
        "sources": [{"url": "https://example.com/article", "title": "Example Article"}],
    }

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ), patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ), patch(
        "brainpack.cli.run_query",
        return_value=mock_result,
    ):
        list_result = runner.invoke(app, ["list", "--json"])
        status_result = runner.invoke(app, ["status", "status-pack", "--json"])
        query_result = runner.invoke(app, ["query", "ready-pack", "What happened?", "--json"])
        chat_result = runner.invoke(app, ["chat", "ready-pack", "What happened?", "--json"])

    _assert_single_machine_document(list_result, ok=True)
    _assert_single_machine_document(status_result, ok=True)
    _assert_single_machine_document(query_result, ok=True)
    _assert_single_machine_document(chat_result, ok=True)


def test_query_json_unbuilt_pack_returns_structured_next_action_precondition_error(tmp_path):
    """query --json rejects unbuilt packs with the shared precondition contract."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "new-pack"
    _write_pack(pack_dir, name="new-pack", llm="ollama")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli._check_ollama_reachable",
        return_value=True,
    ), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ) as mock_load_model, patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ) as mock_get_collection, patch(
        "brainpack.cli.run_query",
    ) as mock_run_query:
        result = runner.invoke(app, ["query", "new-pack", "What happened?", "--json"])

    payload = _assert_single_machine_document(result, ok=False)

    assert result.exit_code == 3
    assert payload == {
        "ok": False,
        "meta": {
            "schema": CLI_SCHEMA_VERSION,
            "command": "query",
            "pack": "new-pack",
        },
        "error": {
            "code": "pack_not_built",
            "message": "Pack 'new-pack' is not built yet.",
            "details": {
                "next_action": "brainpack build new-pack",
                "reason": "Build this pack before Brainpack can serve it to an agent or local model.",
            },
        },
        "warnings": [],
    }
    mock_load_model.assert_not_called()
    mock_get_collection.assert_not_called()
    mock_run_query.assert_not_called()


@pytest.mark.parametrize(
    ("state_setup", "expected_code", "expected_reason"),
    [
        ("new", "pack_not_built", "Build this pack before Brainpack can serve it to an agent or local model."),
        (
            "needs-build",
            "pack_needs_build",
            "Rebuild this pack so agent and local-mode retrieval use the latest indexed changes.",
        ),
        (
            "error",
            "pack_build_failed",
            "Rebuild this pack after the last indexing failure before using it again.",
        ),
    ],
)
def test_query_json_next_action_precondition_errors_lock_onboarding_aligned_reason_text(
    tmp_path,
    state_setup,
    expected_code,
    expected_reason,
):
    """Machine precondition envelopes should lock deliberate lifecycle reason wording."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "reason-pack"
    _write_pack(pack_dir, name="reason-pack", llm="ollama")

    if state_setup == "needs-build":
        _mark_pack_stale(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")
    elif state_setup == "error":
        _mark_pack_failed(pack_dir)

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli._check_ollama_reachable",
        return_value=True,
    ), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ) as mock_load_model, patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ) as mock_get_collection, patch(
        "brainpack.cli.run_query",
    ) as mock_run_query:
        result = runner.invoke(app, ["query", "reason-pack", "What happened?", "--json"])

    payload = _assert_single_machine_document(result, ok=False)

    assert result.exit_code == 3
    assert payload["error"]["code"] == expected_code
    assert payload["error"]["details"]["reason"] == expected_reason
    mock_load_model.assert_not_called()
    mock_get_collection.assert_not_called()
    mock_run_query.assert_not_called()
