"""Tests for cli.py — covers CLI-01, CLI-02."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock, call

from brainpack.config import SourceEntry


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


def _make_config(sources, embedding_model="all-MiniLM-L6-v2", episode_limit=20):
    """Helper to build a mock PackConfig with SourceEntry objects."""
    cfg = MagicMock()
    cfg.sources = sources
    cfg.embedding_model = embedding_model
    cfg.name = "test-pack"
    cfg.episode_limit = episode_limit
    return cfg


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
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}) as mock_load_state, \
         patch("brainpack.cli.check_model_provenance") as mock_prov, \
         patch("brainpack.cli.save_state") as mock_save, \
         patch("brainpack.cli.load_model", return_value=mock_model), \
         patch("brainpack.cli.get_collection", return_value=mock_collection), \
         patch("brainpack.cli.detect_source_type", return_value="article"), \
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
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    call_order = []

    def mock_prov(state, model, pack_name):
        call_order.append("provenance")

    def mock_embed(collection, model, chunks, metadatas, url):
        call_order.append("embed")
        return 1

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.check_model_provenance", side_effect=mock_prov), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="article"), \
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
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": "all-MiniLM-L6-v2", "processed": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="article"), \
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
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="article"), \
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


class TestAudioBuild:
    """Tests for audio source routing in the build command (Phase 2)."""

    def _base_patches(self, packs_root, extra_patches=None):
        """Return common patch context for audio build tests."""
        patches = {
            "brainpack.cli._PACKS_DIR": packs_root,
            "brainpack.cli.load_state": {"embedding_model": None, "processed": {}, "audio_steps": {}},
            "brainpack.cli.check_model_provenance": MagicMock(),
            "brainpack.cli.save_state": MagicMock(),
            "brainpack.cli.load_model": MagicMock(),
            "brainpack.cli.get_collection": MagicMock(),
            "brainpack.cli.embed_and_store": 1,
            "brainpack.cli.chunk_text": ["chunk1"],
            "brainpack.cli.mark_audio_step": MagicMock(),
            "brainpack.cli.is_audio_step_done": False,
            "brainpack.cli.get_audio_step": {},
            "brainpack.cli.mark_failed": MagicMock(),
            "brainpack.cli.check_deno_available": True,
        }
        if extra_patches:
            patches.update(extra_patches)
        return patches

    def test_build_youtube_source(self, tmp_path):
        """build routes youtube source through list_youtube_episodes + download_audio + transcribe_audio."""
        from brainpack.cli import app
        packs_root = tmp_path / "brainpacks"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
            "  - https://www.youtube.com/@channel\nembedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"x" * 20_000)

        episode = {"id": "vid123", "title": "Test Video", "url": "https://youtu.be/vid123"}
        segments = [{"start": 0.0, "end": 5.0, "text": "Hello world"}]
        mock_config = _make_config([SourceEntry(url="https://www.youtube.com/@channel")])

        mock_embed = MagicMock(return_value=1)
        mock_transcribe = MagicMock(return_value=segments)
        mock_download = MagicMock(return_value=audio_file)

        with patch("brainpack.cli._PACKS_DIR", packs_root), \
             patch("brainpack.cli.load_config", return_value=mock_config), \
             patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("brainpack.cli.check_model_provenance"), \
             patch("brainpack.cli.save_state"), \
             patch("brainpack.cli.load_model", return_value=MagicMock()), \
             patch("brainpack.cli.get_collection", return_value=MagicMock()), \
             patch("brainpack.cli.detect_source_type", return_value="youtube"), \
             patch("brainpack.cli.check_deno_available", return_value=True), \
             patch("brainpack.cli.list_youtube_episodes", return_value=[episode]), \
             patch("brainpack.cli.download_audio", mock_download), \
             patch("brainpack.cli.transcribe_audio", mock_transcribe), \
             patch("brainpack.cli.chunk_text", return_value=["chunk1"]), \
             patch("brainpack.cli.embed_and_store", mock_embed), \
             patch("brainpack.cli.is_audio_step_done", return_value=False), \
             patch("brainpack.cli.get_audio_step", return_value={}), \
             patch("brainpack.cli.mark_audio_step"), \
             patch("brainpack.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        assert "[done]" in result.output
        mock_download.assert_called_once()
        mock_transcribe.assert_called_once()
        mock_embed.assert_called_once()

    def test_build_podcast_source(self, tmp_path):
        """build routes podcast source through list_podcast_episodes + download_podcast_audio + transcribe_audio."""
        from brainpack.cli import app
        packs_root = tmp_path / "brainpacks"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
            "  - https://example.com/feed.rss\nembedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        audio_file = tmp_path / "episode.mp3"
        audio_file.write_bytes(b"x" * 20_000)

        episode = {"guid": "ep001", "title": "Podcast Episode 1", "url": "https://example.com/ep1.mp3"}
        segments = [{"start": 0.0, "end": 10.0, "text": "Podcast content here"}]
        mock_config = _make_config([SourceEntry(url="https://example.com/feed.rss")])

        mock_transcribe = MagicMock(return_value=segments)
        mock_download = MagicMock(return_value=audio_file)

        with patch("brainpack.cli._PACKS_DIR", packs_root), \
             patch("brainpack.cli.load_config", return_value=mock_config), \
             patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("brainpack.cli.check_model_provenance"), \
             patch("brainpack.cli.save_state"), \
             patch("brainpack.cli.load_model", return_value=MagicMock()), \
             patch("brainpack.cli.get_collection", return_value=MagicMock()), \
             patch("brainpack.cli.detect_source_type", return_value="podcast"), \
             patch("brainpack.cli.list_podcast_episodes", return_value=[episode]), \
             patch("brainpack.cli.download_podcast_audio", mock_download), \
             patch("brainpack.cli.transcribe_audio", mock_transcribe), \
             patch("brainpack.cli.chunk_text", return_value=["chunk1"]), \
             patch("brainpack.cli.embed_and_store", return_value=1), \
             patch("brainpack.cli.is_audio_step_done", return_value=False), \
             patch("brainpack.cli.get_audio_step", return_value={}), \
             patch("brainpack.cli.mark_audio_step"), \
             patch("brainpack.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        mock_download.assert_called_once()
        mock_transcribe.assert_called_once()

    def test_build_model_flag_passed_to_transcribe(self, tmp_path):
        """build --model medium passes model_size='medium' to transcribe_audio."""
        from brainpack.cli import app
        packs_root = tmp_path / "brainpacks"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
            "  - https://www.youtube.com/@channel\nembedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"x" * 20_000)

        episode = {"id": "vid123", "title": "Test Video", "url": "https://youtu.be/vid123"}
        segments = [{"start": 0.0, "end": 5.0, "text": "Content"}]
        mock_config = _make_config([SourceEntry(url="https://www.youtube.com/@channel")])
        mock_transcribe = MagicMock(return_value=segments)

        with patch("brainpack.cli._PACKS_DIR", packs_root), \
             patch("brainpack.cli.load_config", return_value=mock_config), \
             patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("brainpack.cli.check_model_provenance"), \
             patch("brainpack.cli.save_state"), \
             patch("brainpack.cli.load_model", return_value=MagicMock()), \
             patch("brainpack.cli.get_collection", return_value=MagicMock()), \
             patch("brainpack.cli.detect_source_type", return_value="youtube"), \
             patch("brainpack.cli.check_deno_available", return_value=True), \
             patch("brainpack.cli.list_youtube_episodes", return_value=[episode]), \
             patch("brainpack.cli.download_audio", return_value=audio_file), \
             patch("brainpack.cli.transcribe_audio", mock_transcribe), \
             patch("brainpack.cli.chunk_text", return_value=["chunk1"]), \
             patch("brainpack.cli.embed_and_store", return_value=1), \
             patch("brainpack.cli.is_audio_step_done", return_value=False), \
             patch("brainpack.cli.get_audio_step", return_value={}), \
             patch("brainpack.cli.mark_audio_step"), \
             patch("brainpack.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack", "--model", "medium"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        mock_transcribe.assert_called_once()
        _, kwargs = mock_transcribe.call_args
        assert kwargs.get("model_size") == "medium", f"Expected model_size='medium', got: {mock_transcribe.call_args}"

    def test_build_language_flag_passed_to_transcribe(self, tmp_path):
        """build --language tr passes language='tr' to transcribe_audio."""
        from brainpack.cli import app
        packs_root = tmp_path / "brainpacks"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
            "  - https://www.youtube.com/@channel\nembedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"x" * 20_000)

        episode = {"id": "vid123", "title": "Test Video", "url": "https://youtu.be/vid123"}
        segments = [{"start": 0.0, "end": 5.0, "text": "Icerik"}]
        mock_config = _make_config([SourceEntry(url="https://www.youtube.com/@channel")])
        mock_transcribe = MagicMock(return_value=segments)

        with patch("brainpack.cli._PACKS_DIR", packs_root), \
             patch("brainpack.cli.load_config", return_value=mock_config), \
             patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("brainpack.cli.check_model_provenance"), \
             patch("brainpack.cli.save_state"), \
             patch("brainpack.cli.load_model", return_value=MagicMock()), \
             patch("brainpack.cli.get_collection", return_value=MagicMock()), \
             patch("brainpack.cli.detect_source_type", return_value="youtube"), \
             patch("brainpack.cli.check_deno_available", return_value=True), \
             patch("brainpack.cli.list_youtube_episodes", return_value=[episode]), \
             patch("brainpack.cli.download_audio", return_value=audio_file), \
             patch("brainpack.cli.transcribe_audio", mock_transcribe), \
             patch("brainpack.cli.chunk_text", return_value=["chunk1"]), \
             patch("brainpack.cli.embed_and_store", return_value=1), \
             patch("brainpack.cli.is_audio_step_done", return_value=False), \
             patch("brainpack.cli.get_audio_step", return_value={}), \
             patch("brainpack.cli.mark_audio_step"), \
             patch("brainpack.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack", "--language", "tr"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        mock_transcribe.assert_called_once()
        _, kwargs = mock_transcribe.call_args
        assert kwargs.get("language") == "tr", f"Expected language='tr', got: {mock_transcribe.call_args}"

    def test_build_article_source_unchanged(self, tmp_path):
        """Article source still calls fetch_article; transcribe_audio NOT called."""
        from brainpack.cli import app
        packs_root = tmp_path / "brainpacks"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
            "  - https://example.com/article\nembedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        mock_config = _make_config([SourceEntry(url="https://example.com/article")])
        mock_fetch = MagicMock(return_value=("Article text", "Article Title"))
        mock_transcribe = MagicMock()

        with patch("brainpack.cli._PACKS_DIR", packs_root), \
             patch("brainpack.cli.load_config", return_value=mock_config), \
             patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("brainpack.cli.check_model_provenance"), \
             patch("brainpack.cli.save_state"), \
             patch("brainpack.cli.load_model", return_value=MagicMock()), \
             patch("brainpack.cli.get_collection", return_value=MagicMock()), \
             patch("brainpack.cli.detect_source_type", return_value="article"), \
             patch("brainpack.cli.is_processed", return_value=False), \
             patch("brainpack.cli.fetch_article", mock_fetch), \
             patch("brainpack.cli.transcribe_audio", mock_transcribe), \
             patch("brainpack.cli.chunk_text", return_value=["chunk1"]), \
             patch("brainpack.cli.embed_and_store", return_value=1), \
             patch("brainpack.cli.mark_processed"), \
             patch("brainpack.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        mock_fetch.assert_called_once_with("https://example.com/article")
        mock_transcribe.assert_not_called()

    def test_build_help_shows_model_and_language_flags(self):
        """build --help shows --model and --language options."""
        from brainpack.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.output
        assert "--language" in result.output
