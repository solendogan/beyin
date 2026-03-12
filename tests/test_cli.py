"""Tests for cli.py — covers CLI-01, CLI-02."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock


@pytest.fixture
def tmp_pack_root(tmp_path):
    """Create a ~/.brainpacks-like structure with a 'test-pack' subdirectory."""
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: Test pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    return packs_root, pack_dir


def test_help_lists_build_and_query():
    """brainpack --help exits 0 and lists both commands."""
    from brainpack.cli import app
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "build" in result.output
    assert "query" in result.output


def test_build_exits_0(tmp_pack_root):
    """build command with mocked pipeline exits 0."""
    from brainpack.cli import app
    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()

    mock_model = MagicMock()
    mock_collection = MagicMock()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}) as mock_load_state, \
         patch("brainpack.cli.check_model_provenance") as mock_prov, \
         patch("brainpack.cli.save_state") as mock_save, \
         patch("brainpack.cli.load_model", return_value=mock_model), \
         patch("brainpack.cli.get_collection", return_value=mock_collection), \
         patch("brainpack.cli.is_processed", return_value=False), \
         patch("brainpack.cli.fetch_article", return_value=("Article text", "Article Title")), \
         patch("brainpack.cli.chunk_text", return_value=["chunk one", "chunk two"]), \
         patch("brainpack.cli.embed_and_store", return_value=2), \
         patch("brainpack.cli.mark_processed") as mock_mark, \
         patch("brainpack.cli.mark_failed") as mock_fail:

        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"


def test_build_calls_check_model_provenance_before_embed(tmp_pack_root):
    """build calls check_model_provenance before any embed_and_store call."""
    from brainpack.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    call_order = []

    def mock_prov(state, model, pack_name):
        call_order.append("provenance")

    def mock_embed(collection, model, chunks, metadatas, url):
        call_order.append("embed")
        return 1

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.check_model_provenance", side_effect=mock_prov), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.is_processed", return_value=False), \
         patch("brainpack.cli.fetch_article", return_value=("text", "title")), \
         patch("brainpack.cli.chunk_text", return_value=["chunk"]), \
         patch("brainpack.cli.embed_and_store", side_effect=mock_embed), \
         patch("brainpack.cli.mark_processed"), \
         patch("brainpack.cli.mark_failed"):

        runner.invoke(app, ["build", "test-pack"])

    assert call_order.index("provenance") < call_order.index("embed"), \
        "check_model_provenance must be called before embed_and_store"


def test_build_skips_already_processed_urls(tmp_pack_root):
    """build skips URLs that is_processed returns True for."""
    from brainpack.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": "all-MiniLM-L6-v2", "processed": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.is_processed", return_value=True), \
         patch("brainpack.cli.fetch_article") as mock_fetch, \
         patch("brainpack.cli.embed_and_store") as mock_embed, \
         patch("brainpack.cli.chunk_text"), \
         patch("brainpack.cli.mark_processed"), \
         patch("brainpack.cli.mark_failed"):

        result = runner.invoke(app, ["build", "test-pack"])

    mock_fetch.assert_not_called()
    mock_embed.assert_not_called()
    assert "skip" in result.output


def test_build_warns_and_marks_failed_when_fetch_returns_none(tmp_pack_root):
    """build logs warning and calls mark_failed when fetch_article returns None."""
    from brainpack.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.is_processed", return_value=False), \
         patch("brainpack.cli.fetch_article", return_value=None), \
         patch("brainpack.cli.embed_and_store") as mock_embed, \
         patch("brainpack.cli.chunk_text"), \
         patch("brainpack.cli.mark_processed") as mock_mark, \
         patch("brainpack.cli.mark_failed") as mock_fail:

        result = runner.invoke(app, ["build", "test-pack"], catch_exceptions=False)

    mock_embed.assert_not_called()
    mock_mark.assert_not_called()
    mock_fail.assert_called_once()
    # Warning output (stderr is merged into output by CliRunner by default)
    assert "warn" in result.output.lower()


def test_query_exits_0_and_prints_answer(tmp_pack_root):
    """query command exits 0 and prints the answer."""
    from brainpack.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    mock_result = {
        "answer": "Test answer here",
        "sources": [{"url": "https://example.com", "title": "Example Article"}],
    }

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", return_value=mock_result):

        result = runner.invoke(app, ["query", "test-pack", "What is this?"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"
    assert "Test answer here" in result.output


def test_query_prints_sources_section(tmp_pack_root):
    """query prints a Sources: section with URL and title per citation."""
    from brainpack.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    mock_result = {
        "answer": "An answer.",
        "sources": [
            {"url": "https://example.com/a", "title": "Article A"},
            {"url": "https://example.com/b", "title": "Article B"},
        ],
    }

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", return_value=mock_result):

        result = runner.invoke(app, ["query", "test-pack", "What?"])

    assert "Sources:" in result.output
    assert "Article A" in result.output
    assert "https://example.com/a" in result.output
    assert "Article B" in result.output
    assert "https://example.com/b" in result.output
