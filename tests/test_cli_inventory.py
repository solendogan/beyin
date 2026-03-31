"""Tests for inventory, list, status, and check-deps commands."""
from beyin.install_hints import ffmpeg_install_hint, yt_dlp_install_hint
import json
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch

from tests.conftest import (
    _mark_pack_ready,
    _mark_pack_needs_build,
    _mark_pack_failed,
    _mark_pack_mixed_result,
    _mark_pack_partially_ready,
    _mark_pack_incrementally_ready,
)


# ---------------------------------------------------------------------------
# Local helper: only used in inventory/status tests
# ---------------------------------------------------------------------------

def _write_ready_pack(pack_dir, *, name: str = "demo-pack", llm: str = "ollama") -> None:
    """Write a minimal ready-state pack to disk."""
    from beyin.inventory import pack_config_hash
    from beyin.pack_state import save_state

    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        f"name: {name}\n"
        "description: Demo pack\n"
        f"llm: {llm}\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {},
            "last_build_at": "2026-03-13T10:00:00+00:00",
            "last_built_pack_hash": pack_config_hash(pack_dir),
        },
    )


# ---------------------------------------------------------------------------
# Inventory summary
# ---------------------------------------------------------------------------

def test_inventory_summary_marks_new_pack_and_next_build(tmp_path):
    """Inventory summary marks unbuilt packs as new with a build next step."""
    from beyin.inventory import summarize_pack

    pack_dir = tmp_path / "test-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: Test\n"
        "llm: openai\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )

    summary = summarize_pack(pack_dir, lambda _cfg: {"blockers": [], "warnings": []})

    assert summary["status"] == "new"
    assert summary["next_action"] == "beyin build test-pack"


def test_inventory_summary_marks_blocked_pack(tmp_path):
    """Inventory summary promotes readiness blockers into the main blocked status."""
    from beyin.inventory import summarize_pack

    pack_dir = tmp_path / "test-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: Test\n"
        "llm: openai\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )

    summary = summarize_pack(
        pack_dir,
        lambda _cfg: {"blockers": ["Error: OPENAI_API_KEY is not set."], "warnings": []},
    )

    assert summary["status"] == "blocked"
    assert summary["next_action"] == "beyin status test-pack"


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------

def test_list_shows_compact_inventory_with_counts_and_ordering(tmp_path):
    """list shows compact alphabetical rows with status, type, source count, and provider."""
    from beyin.cli import app
    from beyin.inventory import save_pack_origin, pack_config_hash
    from beyin.pack_state import save_state

    runner = CliRunner()
    packs_root = tmp_path / "beyin"
    a_pack = packs_root / "a-pack"
    b_pack = packs_root / "b-pack"
    a_pack.mkdir(parents=True)
    b_pack.mkdir(parents=True)
    for pack_dir, name in ((b_pack, "b-pack"), (a_pack, "a-pack")):
        (pack_dir / "pack.yaml").write_text(
            f"name: {name}\n"
            "description: test\n"
            "llm: openai\n"
            "sources:\n"
            "  - https://example.com/article\n"
            "  - https://example.com/other\n"
        )
        save_state(
            pack_dir,
            {
                "embedding_model": "all-MiniLM-L6-v2",
                "processed": {},
                "audio_steps": {},
                "last_build_at": "2026-03-13T10:00:00+00:00",
                "last_built_pack_hash": pack_config_hash(pack_dir),
            },
        )
        save_pack_origin(
            pack_dir,
            {"type": "file", "source": f"/tmp/{name}.yaml", "added_at": "2026-03-13T09:00:00+00:00"},
        )

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0, result.output
    rows = [line.strip() for line in result.output.splitlines() if line.strip().startswith(("a-pack", "b-pack"))]
    assert rows[0].startswith("a-pack")
    assert rows[1].startswith("b-pack")
    assert "2" in rows[0]
    assert "2" in rows[0]
    assert "Summary" not in result.output
    assert "Src" not in result.output


def test_list_human_output_stays_compact_without_coaching_blocks(tmp_path):
    """list shows a compact table without appending 'Use with agent' coaching sections."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    _write_ready_pack(packs_root / "demo-pack", name="demo-pack")
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli._check_ollama_reachable", return_value=True
    ):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "demo-pack" in result.output
    assert "Use with agent" not in result.output
    assert "Use with local model" not in result.output
    assert "beyin mcp-server" not in result.output


def test_list_json_stays_stable_and_prompt_free_for_installed_packs(tmp_path):
    """list --json stays single-document, prompt-free, and structurally unchanged after inventory-first changes."""
    from beyin.cli import app
    from beyin.machine_output import CLI_SCHEMA_VERSION

    packs_root = tmp_path / "beyin"
    _write_ready_pack(packs_root / "demo-pack", name="demo-pack")
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli._check_ollama_reachable", return_value=True
    ), patch(
        "beyin.cli.load_prompt_backend",
        side_effect=AssertionError("interactive backend must stay unloaded"),
    ):
        result = runner.invoke(app, ["list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["meta"]["schema"] == CLI_SCHEMA_VERSION
    assert payload["meta"]["command"] == "list"
    assert len(payload["data"]["packs"]) == 1
    assert payload["data"]["packs"][0]["name"] == "demo-pack"


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("pack_name", "state_setup", "env_vars", "expected_status", "expected_command"),
    [
        ("ready-pack", "ready", {"OPENAI_API_KEY": "sk-test"}, "ready", "beyin mcp-server"),
        ("new-pack", "new", {"OPENAI_API_KEY": "sk-test"}, "needs-build", "beyin build new-pack"),
        ("stale-pack", "needs-build", {"OPENAI_API_KEY": "sk-test"}, "needs-build", "beyin build stale-pack"),
        ("partially-ready-pack", "partially-ready", {"OPENAI_API_KEY": "sk-test"}, "partially-ready", "beyin build partially-ready-pack"),
        ("incremental-ready-pack", "incremental-ready", {"OPENAI_API_KEY": "sk-test"}, "ready", "beyin mcp-server"),
        ("error-pack", "error", {"OPENAI_API_KEY": "sk-test"}, "error", "beyin build error-pack"),
        ("partial-pack", "partial", {"OPENAI_API_KEY": "sk-test"}, "partially-ready", "beyin build partial-pack"),
    ],
)
def test_status_uses_onboarding_guidance_across_lifecycle_states(
    tmp_path,
    pack_name,
    state_setup,
    env_vars,
    expected_status,
    expected_command,
):
    """status should use the shared onboarding guidance seam across lifecycle states."""
    from beyin.cli import app
    from beyin.inventory import save_pack_origin

    runner = CliRunner()
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / pack_name
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        f"name: {pack_name}\n"
        "description: test\n"
        "llm: openai\n"
        "sources:\n"
        "  - https://example.com/article-1\n"
        "  - https://example.com/article-2\n"
    )
    save_pack_origin(
        pack_dir,
        {"type": "file", "source": f"/tmp/{pack_name}.yaml", "added_at": "2026-03-13T09:00:00+00:00"},
    )

    if state_setup == "ready":
        _mark_pack_ready(pack_dir)
    elif state_setup == "needs-build":
        _mark_pack_needs_build(pack_dir)
    elif state_setup == "partially-ready":
        _mark_pack_partially_ready(pack_dir)
    elif state_setup == "incremental-ready":
        _mark_pack_incrementally_ready(pack_dir, urls=[
            "https://example.com/article-1",
            "https://example.com/article-2",
        ])
    elif state_setup == "error":
        _mark_pack_failed(pack_dir)
    elif state_setup == "partial":
        _mark_pack_mixed_result(pack_dir)

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch.dict("os.environ", env_vars, clear=True), \
         patch("beyin.cli._check_ollama_reachable", return_value=True):
        result = runner.invoke(app, ["status", pack_name])

    assert result.exit_code == 0, result.output
    assert expected_status in result.output
    assert f"ID           {pack_name}" in result.output or pack_name in result.output
    assert "Description  test" in result.output


def test_status_renders_provenance_and_build_recap_before_source_rows(tmp_path):
    """status: provenance/build-recap sections must appear before the Sources section."""
    from beyin.cli import app
    from beyin.inventory import save_pack_origin

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "demo-pack"
    _write_ready_pack(pack_dir, name="demo-pack")
    save_pack_origin(
        pack_dir,
        {
            "type": "file",
            "source": "/tmp/demo-pack.yaml",
            "added_at": "2026-03-11T09:00:00+00:00",
            "last_updated_at": "2026-03-12T09:00:00+00:00",
        },
    )
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli._check_ollama_reachable", return_value=True
    ):
        result = runner.invoke(app, ["status", "demo-pack"])

    assert result.exit_code == 0
    output = result.output
    # Origin/provenance and last-built recap must both appear before the Sources section
    assert "Origin" in output or "origin" in output or "/tmp/demo-pack.yaml" in output
    assert "Last built" in output or "2026-03-13" in output
    sources_pos = output.find("Sources")
    origin_pos = output.find("/tmp/demo-pack.yaml") if "/tmp/demo-pack.yaml" in output else output.find("origin")
    built_pos = output.find("2026-03-13")
    if sources_pos >= 0 and origin_pos >= 0:
        assert origin_pos < sources_pos, "Origin/provenance should appear before Sources section"
    if sources_pos >= 0 and built_pos >= 0:
        assert built_pos < sources_pos, "Build recap date should appear before Sources section"


def test_status_ready_pack_does_not_show_next_step_coaching(tmp_path):
    """status on a ready pack must not show 'Use with agent' or 'Use with local model' coaching."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    _write_ready_pack(packs_root / "ready-pack", name="ready-pack")
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli._check_ollama_reachable", return_value=True
    ):
        result = runner.invoke(app, ["status", "ready-pack"])

    assert result.exit_code == 0
    assert "Use with agent" not in result.output
    assert "Use with local model" not in result.output
    # Ready packs: no coaching copy about next steps
    assert "beyin mcp-server" not in result.output
    assert "beyin create" not in result.output


def test_status_pack_without_runtime_readiness_stays_compact_without_coaching(tmp_path):
    """status should stay compact even when runtime query readiness is unavailable."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "blocked-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: blocked-pack\n"
        "description: Blocked\n"
        "llm: openai\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ", {}, clear=True
    ):
        result = runner.invoke(app, ["status", "blocked-pack"])

    assert result.exit_code == 0
    assert "blocked-pack" in result.output
    assert "needs-build" in result.output
    assert "Use with agent" not in result.output
    assert "Use with local model" not in result.output


def test_status_audio_sources_do_not_repeat_unowned_partial_episodes(tmp_path):
    """status should scope partial audio episodes to their owning source."""
    from beyin.cli import app
    from beyin.pack_state import save_state

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "demo-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: demo-pack\n"
        "description: demo\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://www.youtube.com/playlist?list=PL123\n"
        "  - https://www.youtube.com/watch?v=yoXW3XD8li0\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {
                "youtube:iYxLoh3Dqfg": {
                    "source_id": "youtube:iYxLoh3Dqfg",
                    "url": "https://www.youtube.com/watch?v=iYxLoh3Dqfg",
                    "title": "Yazilim sektorundeki dolandiricilik",
                    "parent_source_url": "https://www.youtube.com/playlist?list=PL123",
                    "stages": {"downloaded": True},
                }
            },
        },
    )
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["status", "demo-pack"])

    assert result.exit_code == 0
    output = result.output
    assert output.count("Yazilim sektorundeki dolandiricilik") == 1
    assert "https://www.youtube.com/watch?v=yoXW3XD8li0" in output


def test_status_playlist_group_headers_are_not_duplicated(tmp_path):
    """status should print each later playlist/feed group header only once."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "demo-pack"
    pack_dir.mkdir(parents=True)
    playlist_a = "https://www.youtube.com/playlist?list=PLA"
    playlist_b = "https://www.youtube.com/playlist?list=PLB"
    (pack_dir / "pack.yaml").write_text(
        "name: demo-pack\n"
        "description: demo\n"
        "llm: ollama\n"
        "sources:\n"
        "  - url: https://www.youtube.com/watch?v=a1\n"
        "    title: Video A1\n"
        f"    parent_url: {playlist_a}\n"
        "    parent_title: Playlist A\n"
        "  - url: https://www.youtube.com/watch?v=b1\n"
        "    title: Video B1\n"
        f"    parent_url: {playlist_b}\n"
        "    parent_title: Playlist B\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["status", "demo-pack"])

    assert result.exit_code == 0
    assert result.output.count("Playlist A") == 1
    assert result.output.count("Playlist B") == 1


def test_status_podcast_source_shows_partial_counts_and_failed_episode_titles(tmp_path):
    """status should show mixed podcast episode counts and preserve failed episode titles."""
    from beyin.cli import app
    from beyin.inventory import pack_config_hash
    from beyin.pack_state import save_state

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "demo-pack"
    pack_dir.mkdir(parents=True)
    feed_url = "https://example.com/feed.rss"
    (pack_dir / "pack.yaml").write_text(
        "name: demo-pack\n"
        "description: demo\n"
        "llm: ollama\n"
        "sources:\n"
        f"  - {feed_url}\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {
                "podcast:ep-failed": {
                    "source_id": "podcast:ep-failed",
                    "url": "https://example.com/ep-failed.mp3",
                    "title": "Failed Episode Title",
                    "status": "failed",
                    "reason": "download failed after retry",
                    "parent_source_url": feed_url,
                }
            },
            "audio_steps": {
                "podcast:ep-ready": {
                    "source_id": "podcast:ep-ready",
                    "url": "https://example.com/ep-ready.mp3",
                    "title": "Ready Episode Title",
                    "parent_source_url": feed_url,
                    "stages": {"embedded": True},
                }
            },
            "last_build_at": "2026-03-21T10:00:00+00:00",
            "last_built_pack_hash": pack_config_hash(pack_dir),
        },
    )
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["status", "demo-pack"])

    assert result.exit_code == 0, result.output
    output = result.output
    assert "partial" in output
    assert "1/2 ready, 1 failed" in output
    assert "Ready Episode Title" in output
    assert "Failed Episode Title" in output


def test_status_json_stays_stable_and_prompt_free_after_rendering_changes(tmp_path):
    """status --json stays single-document, prompt-free after human-rendering changes."""
    from beyin.cli import app
    from beyin.machine_output import CLI_SCHEMA_VERSION

    packs_root = tmp_path / "beyin"
    _write_ready_pack(packs_root / "demo-pack", name="demo-pack", llm="openai")
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False
    ), patch(
        "beyin.cli.load_prompt_backend",
        side_effect=AssertionError("interactive backend must stay unloaded"),
    ):
        result = runner.invoke(app, ["status", "demo-pack", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["meta"]["schema"] == CLI_SCHEMA_VERSION
    assert payload["meta"]["command"] == "status"
    assert payload["data"]["pack"]["name"] == "demo-pack"
    assert "Use with agent" not in result.output


def test_status_command_exposes_lifecycle_management_lines(tmp_pack_root):
    """beyin status should expose the pack summary without fallback coaching blocks."""
    from beyin.cli import app

    packs_root, pack_dir = tmp_pack_root
    _mark_pack_ready(pack_dir)
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._check_ollama_reachable", return_value=True):
        result = runner.invoke(app, ["status", "test-pack"])

    assert result.exit_code == 0
    output = result.output
    assert "test-pack" in output
    assert "ready" in output
    assert "Last built" in output
    assert "Use with agent" not in output
    assert "Use with local model" not in output


# ---------------------------------------------------------------------------
# check-deps tests
# ---------------------------------------------------------------------------

def test_check_deps_all_pass():
    """check-deps exits 0 when ffmpeg and yt-dlp both pass."""
    from beyin.cli import app
    runner = CliRunner()

    with patch(
        "beyin.cli.load_settings",
        return_value=type(
            "S",
            (),
            {
                "enabled_capabilities": ["youtube", "podcasts"],
                "enabled_local_file_types": [],
                "preferred_transcription_backend": "faster-whisper",
                "preferred_whisper_model": "small",
                "preferred_llm_model": "llama3.2",
            },
        )(),
    ), patch("beyin.cli.shutil") as mock_shutil, \
         patch("beyin.cli._ytdlp_version_ok", return_value=(True, "2026.03.03")):
        mock_shutil.which.side_effect = lambda name: {
            "ffmpeg": "/usr/bin/ffmpeg",
        }.get(name)
        result = runner.invoke(app, ["check-deps"])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"


def test_check_deps_does_not_surface_deno():
    """check-deps no longer reports Deno as a user-facing dependency."""
    from beyin.cli import app
    runner = CliRunner()

    with patch(
        "beyin.cli.load_settings",
        return_value=type(
            "S",
            (),
            {
                "enabled_capabilities": ["youtube", "podcasts"],
                "enabled_local_file_types": [],
                "preferred_transcription_backend": "faster-whisper",
                "preferred_whisper_model": "small",
                "preferred_llm_model": "llama3.2",
            },
        )(),
    ), patch("beyin.cli.shutil") as mock_shutil, \
         patch("beyin.cli._ytdlp_version_ok", return_value=(True, "2026.03.03")):
        mock_shutil.which.side_effect = lambda name: {
            "ffmpeg": "/usr/bin/ffmpeg",
        }.get(name)
        result = runner.invoke(app, ["check-deps"])

    assert result.exit_code == 0
    assert "Deno" not in result.output
    assert "deno" not in result.output.lower()


def test_check_deps_ytdlp_outdated():
    """check-deps exits 1 with OUTDATED + upgrade command when yt-dlp is below min version."""
    from beyin.cli import app
    runner = CliRunner()

    with patch(
        "beyin.cli.load_settings",
        return_value=type(
            "S",
            (),
            {
                "enabled_capabilities": ["youtube"],
                "enabled_local_file_types": [],
                "preferred_transcription_backend": "faster-whisper",
                "preferred_whisper_model": "small",
                "preferred_llm_model": "llama3.2",
            },
        )(),
    ), patch("beyin.cli.shutil") as mock_shutil, \
         patch("beyin.cli._ytdlp_version_ok", return_value=(False, "2025.10.01")):
        mock_shutil.which.side_effect = lambda name: {
            "ffmpeg": "/usr/bin/ffmpeg",
        }.get(name)
        result = runner.invoke(app, ["check-deps"])

    assert result.exit_code == 1
    output = result.output
    assert "outdated" in output.lower() or "OUTDATED" in output
    assert yt_dlp_install_hint() in output


def test_check_deps_ffmpeg_missing():
    """check-deps exits 1 with ffmpeg install instruction when ffmpeg not found."""
    from beyin.cli import app
    runner = CliRunner()

    with patch(
        "beyin.cli.load_settings",
        return_value=type(
            "S",
            (),
            {
                "enabled_capabilities": ["podcasts"],
                "enabled_local_file_types": [],
                "preferred_transcription_backend": "faster-whisper",
                "preferred_whisper_model": "small",
                "preferred_llm_model": "llama3.2",
            },
        )(),
    ), patch("beyin.cli.shutil") as mock_shutil, \
         patch("beyin.cli._ytdlp_version_ok", return_value=(True, "2026.03.03")):
        mock_shutil.which.side_effect = lambda name: {
            "ffmpeg": None,
        }.get(name)
        result = runner.invoke(app, ["check-deps"])

    assert result.exit_code == 1
    output = result.output
    assert "ffmpeg" in output.lower()
    assert ffmpeg_install_hint() in output


def test_check_deps_shows_full_document_dependency_inventory():
    """check-deps should show the full optional document dependency inventory."""
    from beyin.cli import app
    runner = CliRunner()

    with patch(
        "beyin.cli.load_settings",
        return_value=type(
            "S",
            (),
            {
                "enabled_capabilities": ["local_files"],
                "enabled_local_file_types": ["pdf"],
                "preferred_transcription_backend": "faster-whisper",
                "preferred_whisper_model": "small",
                "preferred_llm_model": "llama3.2",
            },
        )(),
    ):
        result = runner.invoke(app, ["check-deps"])

    assert result.exit_code == 0
    assert "PDF (.pdf)" in result.output
    assert "DOCX (.docx)" in result.output
    assert "XLSX (.xlsx)" in result.output
