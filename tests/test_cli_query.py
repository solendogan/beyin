"""Tests for CLI-level query command (distinct from test_query.py which tests the query engine)."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from beyin.config import SourceEntry

from tests.conftest import (
    _make_config,
    _mark_pack_ready,
    _mark_pack_mixed_result,
    _mark_pack_partially_ready,
    _mark_pack_needs_build,
    _mark_pack_failed,
)


def test_query_exits_0_and_prints_answer(tmp_pack_root):
    """query command exits 0 and prints the answer."""
    from beyin.cli import app
    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
    _mark_pack_ready(pack_dir)

    mock_result = {
        "answer": "Test answer here",
        "sources": [{"url": "https://example.com", "title": "Example Article"}],
    }

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._query_provider_error", return_value=None), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.run_query", return_value=mock_result):

        result = runner.invoke(app, ["query", "test-pack", "What is this?"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"
    assert "Test answer here" in result.output


def test_query_allows_mixed_result_pack_with_existing_index(tmp_pack_root):
    """query should work when a pack has indexed content even if some sources failed in the last build."""
    from beyin.cli import app

    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
    _mark_pack_mixed_result(pack_dir)

    mock_result = {
        "answer": "Cloud agents run remotely.",
        "sources": [{"url": "https://example.com", "title": "Example Article"}],
    }

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._query_provider_error", return_value=None), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.run_query", return_value=mock_result):

        result = runner.invoke(app, ["query", "test-pack", "What are cloud agents?"])

    assert result.exit_code == 0, result.output
    assert "Cloud agents run remotely." in result.output


def test_query_prints_sources_section(tmp_pack_root):
    """query prints a Sources: section with URL and title per citation."""
    from beyin.cli import app
    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
    _mark_pack_ready(pack_dir)

    mock_result = {
        "answer": "An answer.",
        "sources": [
            {"url": "https://example.com/a", "title": "Article A"},
            {"url": "https://example.com/b", "title": "Article B"},
        ],
    }

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._query_provider_error", return_value=None), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.run_query", return_value=mock_result):

        result = runner.invoke(app, ["query", "test-pack", "What?"])

    assert "Sources:" in result.output
    assert "Article A" in result.output
    assert "https://example.com/a" in result.output
    assert "Article B" in result.output
    assert "https://example.com/b" in result.output


def test_query_compacts_duplicate_video_sources_by_title_and_url(tmp_pack_root):
    """query groups repeated timestamp hits from the same video into one compact source entry."""
    from beyin.cli import app
    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
    _mark_pack_ready(pack_dir)

    mock_result = {
        "answer": "An answer.",
        "sources": [
            {
                "url": "https://youtu.be/vid123",
                "title": "Episode 123",
                "timestamp_start": 12.0,
                "timestamp_end": 34.0,
            },
            {
                "url": "https://youtu.be/vid123",
                "title": "Episode 123",
                "timestamp_start": 40.0,
                "timestamp_end": 52.0,
            },
        ],
    }

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._query_provider_error", return_value=None), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.run_query", return_value=mock_result):
        result = runner.invoke(app, ["query", "test-pack", "What?"])

    assert result.exit_code == 0
    assert result.output.count("Episode 123") == 1
    assert "00:12-00:34" in result.output
    assert "00:40-00:52" in result.output


def test_query_openai_pack_does_not_require_ollama(tmp_pack_root):
    """OpenAI packs load config first and skip Ollama-specific readiness checks."""
    from beyin.cli import app
    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
    _mark_pack_ready(pack_dir)

    mock_result = {"answer": "OpenAI answer", "sources": []}
    mock_config = _make_config(
        [SourceEntry(url="https://example.com/article")],
        llm="openai",
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli._query_provider_error", return_value=None), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.run_query", return_value=mock_result) as mock_run_query:

        result = runner.invoke(app, ["query", "test-pack", "What is this?"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"
    mock_run_query.assert_called_once()
    assert "OpenAI answer" in result.output


def test_query_openai_without_api_key_fails_cleanly(tmp_pack_root):
    """OpenAI packs fail on OpenAI readiness, not on unrelated Ollama checks."""
    from beyin.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    mock_config = _make_config(
        [SourceEntry(url="https://example.com/article")],
        llm="openai",
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch(
             "beyin.cli._query_provider_error",
             return_value="Error: OPENAI_API_KEY is not set.\nSet it in your shell environment, then retry.",
         ), \
         patch.dict("os.environ", {}, clear=True):

        result = runner.invoke(app, ["query", "test-pack", "What is this?"])

    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.output
    assert "Ollama" not in result.output


def test_query_anthropic_pack_fails_cleanly(tmp_pack_root):
    """Anthropic packs exit cleanly as unsupported in this phase."""
    from beyin.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    mock_config = _make_config(
        [SourceEntry(url="https://example.com/article")],
        llm="anthropic",
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.run_query") as mock_run_query:

        result = runner.invoke(app, ["query", "test-pack", "What is this?"])

    assert result.exit_code == 1
    assert "Anthropic" in result.output
    assert "not supported" in result.output
    mock_run_query.assert_not_called()


def test_query_prints_timestamp_ranges_in_sources(tmp_pack_root):
    """Query output surfaces timestamp ranges when the source metadata has them."""
    from beyin.cli import app
    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
    _mark_pack_ready(pack_dir)

    mock_result = {
        "answer": "Timestamped answer",
        "sources": [
            {
                "url": "https://youtu.be/vid123",
                "title": "Episode 123",
                "timestamp_start": 12.0,
                "timestamp_end": 34.0,
            }
        ],
    }

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._query_provider_error", return_value=None), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.run_query", return_value=mock_result):

        result = runner.invoke(app, ["query", "test-pack", "What happened?"])

    assert result.exit_code == 0
    assert "00:12-00:34" in result.output


def test_query_unbuilt_pack_redirects_to_build(tmp_pack_root):
    """Unbuilt-pack query should reuse onboarding guidance instead of a raw next-step line."""
    from beyin.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._query_provider_error", return_value=None), \
         patch("beyin.cli.load_model") as mock_load_model, \
         patch("beyin.cli.get_collection") as mock_get_collection, \
         patch("beyin.cli.run_query") as mock_run_query:
        result = runner.invoke(app, ["query", "test-pack", "Can I ask now?"])

    assert result.exit_code == 1
    assert "not built" in result.output.lower() or "build" in result.output.lower()
    assert "Use with agent" in result.output
    assert "Use with local model" in result.output
    assert "beyin mcp-server" in result.output
    assert (
        "beyin build test-pack" in result.output
        or "beyin build <pack>" in result.output
    )
    assert "Next step:" not in result.output
    mock_load_model.assert_not_called()
    mock_get_collection.assert_not_called()
    mock_run_query.assert_not_called()


@pytest.mark.parametrize(
    ("command", "status_setup", "expected_command"),
    [
        ("query", "needs-build", "beyin build test-pack"),
        ("query", "error", "beyin build test-pack"),
    ],
)
def test_retrieval_preconditions_share_onboarding_guidance(
    tmp_pack_root,
    command,
    status_setup,
    expected_command,
):
    """Human query preconditions should render the shared onboarding guidance seam."""
    from beyin.cli import app

    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()

    if status_setup == "needs-build":
        _mark_pack_needs_build(pack_dir)
    elif status_setup == "partially-ready":
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\n"
            "description: demo\n"
            "llm: ollama\n"
            "sources:\n"
            "  - https://example.com/article-1\n"
            "  - https://example.com/article-2\n"
            "embedding_model: all-MiniLM-L6-v2\n"
        )
        _mark_pack_partially_ready(pack_dir)
    elif status_setup == "error":
        _mark_pack_failed(pack_dir)

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._query_provider_error", return_value=None), \
         patch("beyin.cli.load_model") as mock_load_model, \
         patch("beyin.cli.get_collection") as mock_get_collection, \
         patch("beyin.cli.run_query") as mock_run_query:
        result = runner.invoke(app, [command, "test-pack", "Can I ask now?"])

    assert result.exit_code == 1
    assert "Use with agent" in result.output
    assert "Use with local model" in result.output
    assert "beyin mcp-server" in result.output
    assert expected_command in result.output or "beyin build <pack>" in result.output
    assert "Next step:" not in result.output
    mock_load_model.assert_not_called()
    mock_get_collection.assert_not_called()
    mock_run_query.assert_not_called()


def test_query_allows_partially_ready_pack_with_warning(tmp_pack_root):
    """query should proceed for partially-ready packs but surface an incomplete-coverage warning."""
    from beyin.cli import app

    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: demo\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article-1\n"
        "  - https://example.com/article-2\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    _mark_pack_partially_ready(pack_dir)

    mock_result = {
        "answer": "Partial answer.",
        "sources": [{"url": "https://example.com/article-1", "title": "Ready source"}],
    }

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._query_provider_error", return_value=None), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.run_query", return_value=mock_result):
        result = runner.invoke(app, ["query", "test-pack", "Can I ask now?"])

    assert result.exit_code == 0, result.output
    assert "Warning: Pack 'test-pack' is only partially built" in result.output
    assert "Partial answer." in result.output


def test_query_ollama_not_running():
    """query exits 1 with 'Ollama is not running' and 'ollama serve' when port closed but binary present."""
    from beyin.cli import app
    runner = CliRunner()
    mock_config = _make_config([SourceEntry(url="https://example.com/article")], llm="ollama")

    with patch("beyin.cli._resolve_pack_dir", return_value=Path("/tmp/mypack")), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch(
             "beyin.cli._query_provider_error",
             return_value="Error: Ollama is not running.\nStart it with: ollama serve",
         ):
        result = runner.invoke(app, ["query", "mypack", "test"])

    assert result.exit_code == 1
    output = result.output
    assert "Ollama is not running" in output
    assert "ollama serve" in output


def test_query_ollama_not_installed():
    """query exits 1 with install guide when ollama binary absent."""
    from beyin.cli import app
    from beyin.install_hints import ollama_install_hint
    runner = CliRunner()
    mock_config = _make_config([SourceEntry(url="https://example.com/article")], llm="ollama")

    with patch("beyin.cli._resolve_pack_dir", return_value=Path("/tmp/mypack")), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch(
             "beyin.cli._query_provider_error",
             return_value=f"Error: Ollama is not installed.\nInstall it with: {ollama_install_hint()}",
         ):
        result = runner.invoke(app, ["query", "mypack", "test"])

    assert result.exit_code == 1
    output = result.output
    assert "not installed" in output.lower() or "Ollama is not installed" in output
    assert ollama_install_hint() in output
