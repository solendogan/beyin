"""MCP server tests for Brainpack's machine-safe tool surface."""

import json

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


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    from brainpack.mcp_server import app

    return app


@pytest.mark.anyio
async def test_mcp_server_lists_expected_tools(mcp_app):
    tools = await mcp_app.list_tools()

    assert [tool.name for tool in tools] == [
        "brainpack_list",
        "brainpack_status",
        "brainpack_doctor",
        "brainpack_evidence",
        "brainpack_query",
        "brainpack_chat",
        "brainpack_build",
        "brainpack_add",
        "brainpack_add_sources",
    ]


@pytest.mark.anyio
async def test_mcp_list_packs_returns_machine_safe_envelope(mcp_app, tmp_path):
    packs_root = tmp_path / "brainpacks"
    alpha_pack = packs_root / "alpha-pack"
    _write_pack(alpha_pack, name="alpha-pack")
    _mark_pack_built(alpha_pack, last_build_at="2026-03-13T10:00:00+00:00")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test"},
        clear=False,
    ):
        _, structured = await mcp_app.call_tool("brainpack_list", {})

    assert structured == {
        "ok": True,
        "meta": {
            "schema": "brainpack.cli.v1",
            "command": "list",
            "surface": "mcp",
            "server_version": "0.1.0",
        },
        "data": {
            "packs": [
                {
                    "name": "alpha-pack",
                    "status": "ready",
                    "type": "text",
                    "provider": "openai",
                    "source_count": 1,
                    "recent_summary": "build 2026-03-13",
                    "next_action": 'brainpack query alpha-pack "question"',
                    "blockers": [],
                    "warnings": [],
                    "origin": {"type": "none", "source": ""},
                }
            ]
        },
        "warnings": [],
    }


@pytest.mark.anyio
async def test_mcp_query_pack_returns_structured_retrieval_payload(mcp_app, tmp_path):
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
        _, structured = await mcp_app.call_tool(
            "brainpack_query",
            {"pack": "query-pack", "question": "What happened?"},
        )

    assert structured == {
        "ok": True,
        "meta": {
            "schema": "brainpack.cli.v1",
            "command": "query",
            "pack": "query-pack",
            "surface": "mcp",
            "server_version": "0.1.0",
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


@pytest.mark.anyio
async def test_mcp_evidence_returns_structured_evidence_payload(mcp_app, tmp_path):
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "evidence-pack"
    _write_pack(pack_dir, name="evidence-pack", llm="openai")
    _mark_pack_built(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")

    mock_evidence = [
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ), patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ), patch(
        "brainpack.cli.retrieve_evidence",
        return_value=mock_evidence,
    ):
        _, structured = await mcp_app.call_tool(
            "brainpack_evidence",
            {"pack": "evidence-pack", "question": "What happened?"},
        )

    assert structured == {
        "ok": True,
        "meta": {
            "schema": "brainpack.cli.v1",
            "command": "evidence",
            "pack": "evidence-pack",
            "surface": "mcp",
            "server_version": "0.1.0",
        },
        "data": {
            "question": "What happened?",
            "evidence": [
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
async def test_mcp_evidence_allows_built_ollama_pack_without_reachability_check(mcp_app, tmp_path):
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
    ), patch(
        "brainpack.cli.retrieve_evidence",
        return_value=[],
    ):
        _, structured = await mcp_app.call_tool(
            "brainpack_evidence",
            {"pack": "ollama-pack", "question": "What happened?"},
        )

    assert structured["ok"] is True
    assert structured["data"] == {"question": "What happened?", "evidence": []}
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
            "Pack 'state-pack' changed after its last build and needs a rebuild before evidence retrieval can continue.",
        ),
        (
            "error",
            "pack_build_failed",
            "Pack 'state-pack' needs a successful build before evidence retrieval can continue.",
        ),
    ],
)
async def test_mcp_evidence_blocks_on_pack_state_preconditions(
    mcp_app,
    tmp_path,
    state_setup,
    expected_code,
    expected_message,
):
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "state-pack"

    if state_setup != "missing":
        _write_pack(pack_dir, name="state-pack", llm="openai")
        if state_setup == "needs-build":
            _mark_pack_stale(pack_dir, last_build_at="2026-03-13T10:00:00+00:00")
        elif state_setup == "error":
            _mark_pack_failed(pack_dir)

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        _, structured = await mcp_app.call_tool(
            "brainpack_evidence",
            {"pack": "state-pack", "question": "What happened?"},
        )

    assert structured["ok"] is False
    assert structured["error"]["code"] == expected_code
    assert structured["error"]["message"] == expected_message


@pytest.mark.anyio
async def test_mcp_doctor_returns_structured_statuses(mcp_app, tmp_path):
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "doctor-pack"
    _write_pack(pack_dir, name="doctor-pack", llm="openai")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ",
        {},
        clear=True,
    ):
        _, structured = await mcp_app.call_tool(
            "brainpack_doctor",
            {"pack": "doctor-pack", "operation": "query"},
        )

    assert structured == {
        "ok": True,
        "meta": {
            "schema": "brainpack.cli.v1",
            "command": "doctor",
            "pack": "doctor-pack",
            "surface": "mcp",
            "server_version": "0.1.0",
        },
        "data": {
            "pack": "doctor-pack",
            "operation": "query",
            "statuses": [
                {"label": "Query readiness", "value": "blocked (provider=openai)"},
                {"label": "Query detail", "value": "Error: OPENAI_API_KEY is not set.\nSet it in your shell environment, then retry."},
            ],
        },
        "warnings": [],
    }


@pytest.mark.anyio
async def test_mcp_add_returns_structured_command_result(mcp_app, tmp_path):
    packs_root = tmp_path / "brainpacks"
    source_yaml = tmp_path / "incoming-pack.yaml"
    source_yaml.write_text(
        "name: imported-pack\n"
        "description: Imported test pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        _, structured = await mcp_app.call_tool(
            "brainpack_add",
            {"source": str(source_yaml)},
        )

    assert structured["ok"] is True
    assert structured["meta"] == {
        "schema": "brainpack.cli.v1",
        "command": "add",
        "surface": "mcp",
        "server_version": "0.1.0",
    }
    assert structured["data"]["exit_code"] == 0
    assert "Pack 'imported-pack' added" in structured["data"]["stdout"]
    assert (packs_root / "imported-pack" / "pack.yaml").exists()
    origin = json.loads((packs_root / "imported-pack" / "origin.json").read_text())
    assert origin["type"] == "file"
    assert origin["source"] == str(source_yaml.resolve())
    assert origin["last_update_summary"] == ["initial add"]


@pytest.mark.anyio
async def test_mcp_build_returns_structured_command_result(mcp_app, tmp_path):
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "build-pack"
    _write_pack(pack_dir, name="build-pack", llm="ollama")

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli.load_model",
        return_value=object(),
    ), patch(
        "brainpack.cli.get_collection",
        return_value=object(),
    ), patch(
        "brainpack.cli.fetch_article",
        return_value=("Some article text for chunking.", "Example Article"),
    ), patch(
        "brainpack.cli.embed_and_store",
        return_value=3,
    ):
        _, structured = await mcp_app.call_tool(
            "brainpack_build",
            {"pack": "build-pack"},
        )

    assert structured["ok"] is True
    assert structured["meta"] == {
        "schema": "brainpack.cli.v1",
        "command": "build",
        "pack": "build-pack",
        "surface": "mcp",
        "server_version": "0.1.0",
    }
    assert structured["data"]["exit_code"] == 0
    assert "Build complete." in structured["data"]["stdout"]
    assert "Total: 3 new chunks indexed." in structured["data"]["stdout"]


@pytest.mark.anyio
async def test_mcp_chat_pack_returns_structured_precondition_envelope(mcp_app, tmp_path):
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        _, structured = await mcp_app.call_tool(
            "brainpack_chat",
            {"pack": "missing-pack", "question": "What happened?"},
        )

    assert structured == {
        "ok": False,
        "meta": {
            "schema": "brainpack.cli.v1",
            "command": "chat",
            "pack": "missing-pack",
            "surface": "mcp",
            "server_version": "0.1.0",
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
