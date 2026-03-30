"""MCP server tests for beyin's machine-safe tool surface."""

import json

from beyin import __version__
from pathlib import Path
from unittest.mock import patch

import pytest


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
    from beyin.inventory import pack_config_hash
    from beyin.pack_state import save_state

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
    from beyin.pack_state import save_state

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
    from beyin.pack_state import save_state

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


def _mark_pack_mixed_result(pack_dir: Path, *, last_build_at: str) -> None:
    from beyin.inventory import pack_config_hash
    from beyin.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {
                "url:done": {"status": "done", "url": "https://example.com/article", "title": "Done"},
                "url:failed": {"status": "failed", "url": "https://example.com/missed", "reason": "download failed"},
            },
            "audio_steps": {},
            "last_build_at": last_build_at,
            "last_built_pack_hash": pack_config_hash(pack_dir),
        },
    )


def _mark_pack_partially_ready(pack_dir: Path, *, last_build_at: str) -> None:
    from beyin.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {
                "https://example.com/article-1": {
                    "status": "done",
                    "url": "https://example.com/article-1",
                    "title": "Done",
                },
            },
            "audio_steps": {},
            "last_build_at": last_build_at,
            "last_built_pack_hash": "outdated-hash",
            "last_build_result": "partial-selection",
        },
    )


def _mark_pack_incrementally_ready(pack_dir: Path) -> None:
    from beyin.pack_state import save_state

    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {
                "https://example.com/article-1": {
                    "status": "done",
                    "url": "https://example.com/article-1",
                    "title": "Done 1",
                },
                "https://example.com/article-2": {
                    "status": "done",
                    "url": "https://example.com/article-2",
                    "title": "Done 2",
                },
            },
            "audio_steps": {},
            "last_build_result": "partial-selection",
        },
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    from beyin.mcp_server import app

    return app


@pytest.mark.anyio
async def test_mcp_server_lists_expected_tools(mcp_app):
    tools = await mcp_app.list_tools()

    assert [tool.name for tool in tools] == [
        "packs",
        "status",
        "retrieve",
        "build",
        "add",
        "add_sources",
        "remove_sources",
        "remove",
        "registry",
    ]


@pytest.mark.anyio
async def test_mcp_list_packs_returns_machine_safe_envelope(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    alpha_pack = packs_root / "alpha-pack"
    _write_pack(alpha_pack, name="alpha-pack")
    _mark_pack_built(alpha_pack, last_build_at="2026-03-13T10:00:00+00:00")

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ):
        _, structured = await mcp_app.call_tool("packs", {})

    assert structured == {
        "ok": True,
        "meta": {
            "schema": "beyin.cli.v1",
            "command": "list",
            "surface": "mcp",
            "server_version": __version__,
        },
        "data": {
            "packs": [
                {
                    "id": "alpha-pack",
                    "name": "alpha-pack",
                    "status": "ready",
                    "provider": "openai",
                    "source_count": 1,
                    "recent_summary": "build 2026-03-13",
                    "next_action": 'beyin query alpha-pack "question"',
                    "blockers": [],
                    "warnings": [],
                    "origin": {"type": "none", "source": ""},
                }
            ]
        },
        "warnings": [],
    }


@pytest.mark.anyio
async def test_mcp_status_exposes_pack_id_and_indexed_sources(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "mobile-marketing"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        "id: mobile-marketing-pack\n"
        "name: Mobile Marketing\n"
        "description: Test pack\n"
        "llm: openai\n"
        "sources:\n"
        "  - url: https://example.com/article\n"
        "    title: Great Article\n"
        f"  - url: {tmp_path / 'notes.md'}\n"
        "    title: Local Notes\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ):
        _, structured = await mcp_app.call_tool("status", {"pack": "mobile-marketing"})

    assert structured["ok"] is True
    pack = structured["data"]["pack"]
    assert pack["id"] == "mobile-marketing-pack"
    assert pack["name"] == "Mobile Marketing"
    assert "provider" not in pack
    assert "next_action" not in pack
    assert pack["sources"][0]["index"] == 1
    assert pack["sources"][0]["source"] == "https://example.com/article"
    assert pack["sources"][1]["index"] == 2




@pytest.mark.anyio
async def test_mcp_retrieve_returns_structured_results_payload(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "retrieve-pack"
    _write_pack(pack_dir, name="retrieve-pack", llm="openai")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    mock_results = [
        {
            "text": "Raw chunk text",
            "url": "https://example.com/article",
            "title": "Example Article",
            "rank": 1,
            "distance": 0.11,
            "timestamp_start": 12.0,
            "timestamp_end": 34.0,
        }
    ]

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ), patch(
        "beyin.cli.load_model",
        return_value=object(),
    ), patch(
        "beyin.cli.get_collection",
        return_value=object(),
    ), patch(
        "beyin.cli.retrieve_evidence",
        return_value=mock_results,
    ):
        _, structured = await mcp_app.call_tool(
            "retrieve",
            {"pack": "retrieve-pack", "queries": ["What happened?"]},
        )

    assert structured == {
        "ok": True,
        "meta": {
            "schema": "beyin.cli.v1",
            "command": "retrieve",
            "pack": "retrieve-pack",
            "surface": "mcp",
            "server_version": __version__,
        },
        "data": {
            "question": "What happened?",
            "results": [
                {
                    "text": "Raw chunk text",
                    "url": "https://example.com/article",
                    "title": "Example Article",
                    "rank": 1,
                    "distance": 0.11,
                    "timestamp_start": 12.0,
                    "timestamp_end": 34.0,
                }
            ],
        },
        "warnings": [],
    }


@pytest.mark.anyio
async def test_mcp_retrieve_allows_built_ollama_pack_without_reachability_check(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "ollama-pack"
    _write_pack(pack_dir, name="ollama-pack", llm="ollama")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli._check_ollama_reachable",
        return_value=False,
    ) as mock_reachable, patch(
        "beyin.cli.load_model",
        return_value=object(),
    ), patch(
        "beyin.cli.get_collection",
        return_value=object(),
    ), patch(
        "beyin.cli.retrieve_evidence",
        return_value=[],
    ):
        _, structured = await mcp_app.call_tool(
            "retrieve",
            {"pack": "ollama-pack", "queries": ["What happened?"]},
        )

    assert structured["ok"] is True
    assert structured["data"] == {"question": "What happened?", "results": []}
    mock_reachable.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("state_setup", "expected_code", "expected_message"),
    [
        ("missing", "pack_not_found", "Pack 'state-pack' is not installed."),
        ("new", "pack_not_built", "Pack 'state-pack' is not built yet."),
        (
            "needs-build",
            "pack_needs_build",
            "Pack 'state-pack' changed after its last build and needs a rebuild before retrieve can continue.",
        ),
        (
            "error",
            "pack_build_failed",
            "Pack 'state-pack' needs a successful build before retrieve can continue.",
        ),
    ],
)
async def test_mcp_retrieve_blocks_on_pack_state_preconditions(
    mcp_app,
    tmp_path,
    state_setup,
    expected_code,
    expected_message,
):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "state-pack"

    if state_setup != "missing":
        _write_pack(
            pack_dir,
            name="state-pack",
            llm="openai",
            sources=["https://example.com/article-1", "https://example.com/article-2"],
        )
        if state_setup == "partially-ready":
            _mark_pack_partially_ready(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")
        if state_setup == "needs-build":
            _mark_pack_stale(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")
        elif state_setup == "error":
            _mark_pack_failed(pack_dir)

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        _, structured = await mcp_app.call_tool(
            "retrieve",
            {"pack": "state-pack", "queries": ["What happened?"]},
        )

    assert structured["ok"] is False
    assert structured["error"]["code"] == expected_code
    assert structured["error"]["message"] == expected_message


@pytest.mark.anyio
async def test_mcp_retrieve_allows_partially_ready_pack_with_warning(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "state-pack"
    _write_pack(
        pack_dir,
        name="state-pack",
        llm="openai",
        sources=["https://example.com/article-1", "https://example.com/article-2"],
    )
    _mark_pack_partially_ready(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ), patch(
        "beyin.cli.load_model",
        return_value=object(),
    ), patch(
        "beyin.cli.get_collection",
        return_value=object(),
    ), patch(
        "beyin.cli.retrieve_evidence",
        return_value=[],
    ):
        _, structured = await mcp_app.call_tool(
            "retrieve",
            {"pack": "state-pack", "queries": ["What happened?"]},
        )

    assert structured["ok"] is True
    assert structured["data"]["coverage_warning"] == (
        "Pack 'state-pack' is only partially built; results may miss some configured sources."
    )
    assert structured["data"]["results"] == []


@pytest.mark.anyio
async def test_mcp_retrieve_allows_mixed_result_pack_with_successful_build(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "mixed-pack"
    _write_pack(pack_dir, name="mixed-pack", llm="openai")
    _mark_pack_mixed_result(pack_dir, last_build_at="2026-03-21T10:00:00+00:00")

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ), patch(
        "beyin.cli.load_model",
        return_value=object(),
    ), patch(
        "beyin.cli.get_collection",
        return_value=object(),
    ), patch(
        "beyin.cli.retrieve_evidence",
        return_value=[{"text": "Cloud agents are remote-running agents.", "url": "https://example.com/article", "title": "Done", "rank": 1}],
    ):
        _, structured = await mcp_app.call_tool(
            "retrieve",
            {"pack": "mixed-pack", "queries": ["What are cloud agents?"]},
        )

    assert structured["ok"] is True
    assert structured["data"]["question"] == "What are cloud agents?"
    assert len(structured["data"]["results"]) == 1


@pytest.mark.anyio
async def test_mcp_add_returns_structured_command_result(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    source_yaml = tmp_path / "incoming-pack.yaml"
    source_yaml.write_text(
        "name: imported-pack\n"
        "description: Imported test pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    with patch("beyin.cli._PACKS_DIR", packs_root):
        _, structured = await mcp_app.call_tool(
            "add",
            {"source": str(source_yaml)},
        )

    assert structured["ok"] is True
    assert structured["meta"] == {
        "schema": "beyin.cli.v1",
        "command": "add",
        "surface": "mcp",
        "server_version": __version__,
    }
    assert structured["data"]["exit_code"] == 0
    assert "Pack 'imported-pack' added" in structured["data"]["stdout"]
    assert (packs_root / "imported-pack" / "pack.yaml").exists()
    origin = json.loads((packs_root / "imported-pack" / "origin.json").read_text())
    assert origin["type"] == "file"
    assert origin["source"] == str(source_yaml.resolve())
    assert origin["last_update_summary"] == ["initial add"]


@pytest.mark.anyio
async def test_mcp_add_accepts_pasted_yaml_content(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    yaml_content = (
        "id: pasted-pack\n"
        "name: pasted-pack\n"
        "description: Added from pasted yaml\n"
        "sources:\n"
        "  - url: https://example.com/article\n"
    )

    with patch("beyin.cli._PACKS_DIR", packs_root):
        _, structured = await mcp_app.call_tool(
            "add",
            {"yaml": yaml_content},
        )

    assert structured["ok"] is True
    assert structured["data"]["exit_code"] == 0
    assert "Pack 'pasted-pack' added" in structured["data"]["stdout"]
    assert (packs_root / "pasted-pack" / "pack.yaml").exists()
    assert not (packs_root / "pasted-pack" / "origin.json").exists()


@pytest.mark.anyio
async def test_mcp_add_rejects_source_and_yaml_together(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    source_yaml = tmp_path / "incoming-pack.yaml"
    source_yaml.write_text(
        "name: imported-pack\n"
        "description: Imported test pack\n"
        "sources:\n"
        "  - url: https://example.com/article\n"
    )

    with patch("beyin.cli._PACKS_DIR", packs_root):
        _, structured = await mcp_app.call_tool(
            "add",
            {"source": str(source_yaml), "yaml": "name: duplicate\nsources:\n  - url: https://example.com\n"},
        )

    assert structured == {
        "ok": False,
        "meta": {
            "schema": "beyin.cli.v1",
            "command": "add",
            "surface": "mcp",
            "server_version": __version__,
        },
        "error": {
            "code": "invalid_add_input",
            "message": "Provide exactly one of 'source' or 'yaml'.",
            "details": {},
        },
        "warnings": [],
    }


@pytest.mark.anyio
async def test_mcp_add_yaml_installs_local_pack_without_temp_origin(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    inline_yaml = (
        "name: inline-pack\n"
        "description: Inline test pack\n"
        "sources:\n"
        "  - url: https://example.com/article\n"
    )

    with patch("beyin.mcp_server.packs_dir", return_value=packs_root), patch(
        "beyin.cli._PACKS_DIR",
        packs_root,
    ):
        _, structured = await mcp_app.call_tool(
            "add",
            {"yaml": inline_yaml},
        )

    pack_dir = packs_root / "inline-pack"
    assert structured["ok"] is True
    assert pack_dir.exists()
    assert (pack_dir / "pack.yaml").exists()
    assert not (pack_dir / "origin.json").exists()
    assert "Run `beyin build inline-pack`" in structured["data"]["stdout"]


@pytest.mark.anyio
async def test_mcp_build_returns_structured_command_result(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "build-pack"
    _write_pack(pack_dir, name="build-pack", llm="ollama")

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli.load_model",
        return_value=object(),
    ), patch(
        "beyin.cli.get_collection",
        return_value=object(),
    ), patch(
        "beyin.cli.resolve_article_ingestion",
        return_value={
            "mode": "article",
            "text": "Some article text for chunking.",
            "title": "Example Article",
            "metadata_url": "https://example.com/article",
        },
    ), patch(
        "beyin.cli.embed_and_store",
        return_value=3,
    ):
        _, structured = await mcp_app.call_tool(
            "build",
            {"pack": "build-pack"},
        )

    assert structured["ok"] is True
    assert structured["meta"] == {
        "schema": "beyin.cli.v1",
        "command": "build",
        "pack": "build-pack",
        "surface": "mcp",
        "server_version": __version__,
    }
    assert structured["data"]["exit_code"] == 0
    # Build complete verdict with new always-on summary table format
    assert "Build complete" in structured["data"]["stdout"]
    assert "3" in structured["data"]["stdout"]  # chunk count appears in table or verdict


@pytest.mark.anyio
async def test_mcp_build_passes_plain_python_defaults_to_cli_function(mcp_app):
    with patch(
        "beyin.mcp_server._cli_build",
        return_value=None,
    ) as mock_build:
        _, structured = await mcp_app.call_tool(
            "build",
            {"pack": "build-pack"},
        )

    assert structured["ok"] is True
    mock_build.assert_called_once_with(
        pack="build-pack",
        sources=None,
        model=None,
        language=None,
        reset=False,
        verbose=False,
    )


@pytest.mark.anyio
async def test_mcp_status_marks_incrementally_built_pack_ready(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "incremental-pack"
    _write_pack(
        pack_dir,
        name="incremental-pack",
        llm="openai",
        sources=["https://example.com/article-1", "https://example.com/article-2"],
    )
    _mark_pack_incrementally_ready(pack_dir)

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ):
        _, structured = await mcp_app.call_tool("status", {"pack": "incremental-pack"})

    assert structured["ok"] is True
    assert structured["data"]["pack"]["status"] == "ready"


@pytest.mark.anyio
async def test_mcp_retrieve_allows_incrementally_ready_pack(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "incremental-pack"
    _write_pack(
        pack_dir,
        name="incremental-pack",
        llm="openai",
        sources=["https://example.com/article-1", "https://example.com/article-2"],
    )
    _mark_pack_incrementally_ready(pack_dir)

    with patch("beyin.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ), patch(
        "beyin.cli.load_model",
        return_value=object(),
    ), patch(
        "beyin.cli.get_collection",
        return_value=object(),
    ), patch(
        "beyin.cli.retrieve_evidence",
        return_value=[],
    ):
        _, structured = await mcp_app.call_tool(
            "retrieve",
            {"pack": "incremental-pack", "queries": ["What happened?"]},
        )

    assert structured["ok"] is True
    assert structured["data"] == {"question": "What happened?", "results": []}


@pytest.mark.anyio
async def test_mcp_remove_sources_removes_by_index_without_rebuild_by_default(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "remove-pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        "name: remove-pack\n"
        "description: Test pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - url: https://example.com/article-1\n"
        "    title: One\n"
        "  - url: https://example.com/article-2\n"
        "    title: Two\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.mcp_server.packs_dir",
        return_value=packs_root,
    ), patch(
        "beyin.mcp_server._cli_build",
    ) as mock_build:
        _, structured = await mcp_app.call_tool(
            "remove_sources",
            {"pack": "remove-pack", "selectors": ["2"]},
        )

    assert structured["ok"] is True
    assert not mock_build.called
    assert "Next step: beyin build remove-pack" in structured["data"]["stdout"]
    raw = (pack_dir / "pack.yaml").read_text()
    assert "article-1" in raw
    assert "article-2" not in raw


@pytest.mark.anyio
async def test_mcp_remove_sources_removes_by_text_match(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "remove-pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        "name: remove-pack\n"
        "description: Test pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - url: https://example.com/paywalls\n"
        "    title: Paywall Strategy\n"
        "  - url: https://example.com/ads\n"
        "    title: Meta Ads Guide\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.mcp_server.packs_dir",
        return_value=packs_root,
    ), patch(
        "beyin.mcp_server._cli_build",
    ):
        _, structured = await mcp_app.call_tool(
            "remove_sources",
            {"pack": "remove-pack", "selectors": ["meta ads"]},
        )

    assert structured["ok"] is True
    raw = (pack_dir / "pack.yaml").read_text()
    assert "Paywall Strategy" in raw
    assert "Meta Ads Guide" not in raw


@pytest.mark.anyio
async def test_mcp_remove_sources_can_rebuild_when_requested(mcp_app, tmp_path):
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "remove-pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        "name: remove-pack\n"
        "description: Test pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - url: https://example.com/article-1\n"
        "    title: One\n"
        "  - url: https://example.com/article-2\n"
        "    title: Two\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.mcp_server.packs_dir",
        return_value=packs_root,
    ), patch(
        "beyin.mcp_server._cli_build",
    ) as mock_build:
        _, structured = await mcp_app.call_tool(
            "remove_sources",
            {"pack": "remove-pack", "selectors": ["2"], "rebuild": True},
        )

    assert structured["ok"] is True
    assert mock_build.called


def test_run_stdio_server_swallows_keyboard_interrupt():
    from beyin.mcp_server import run_stdio_server

    with patch("beyin.mcp_server.app.run", side_effect=KeyboardInterrupt()):
        run_stdio_server()


def test_run_stdio_server_swallows_shutdown_exception_group():
    from beyin.mcp_server import run_stdio_server

    exc = BaseExceptionGroup(
        "shutdown",
        [KeyboardInterrupt(), BrokenPipeError()],
    )

    with patch("beyin.mcp_server.app.run", side_effect=exc):
        run_stdio_server()
