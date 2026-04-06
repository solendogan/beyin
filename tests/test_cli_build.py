"""Tests for the build command including audio build flows (TestAudioBuild class)."""
import json
import sys
from collections.abc import Callable
import pytest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from beyin.config import SourceEntry, load_config

from tests.conftest import _make_config, _save_global_settings


@pytest.fixture(autouse=True)
def _default_punkt_tab_ready():
    """Keep build tests focused on build flow unless a test overrides punkt_tab readiness."""
    def _sent_tokenize(text: str):
        return [line.strip() for line in text.splitlines() if line.strip()]

    with patch("beyin.cli._punkt_tab_build_issue", return_value=None), \
         patch("beyin.chunker.nltk.sent_tokenize", side_effect=_sent_tokenize):
        yield


# ---------------------------------------------------------------------------
# Local helper: only used in build tests
# ---------------------------------------------------------------------------

def _p12_article_patches(packs_root, mock_config, *,
                          fetch_side_effects=None,
                          fetch_return=None,
                          is_processed_return=False,
                          embed_return=1,
                          detect_side_effects=None,
                          save_state_mock=True,
                          extra=None):
    """Build an ExitStack of CLI patches for article-based build tests (Phase 12)."""
    stack = ExitStack()
    fetch_return = fetch_return or ("Article text", "Article title")
    stack.enter_context(patch("beyin.cli._PACKS_DIR", packs_root))
    stack.enter_context(patch("beyin.cli.load_config", return_value=mock_config))
    stack.enter_context(patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}))
    stack.enter_context(patch("beyin.cli.check_model_provenance"))
    if save_state_mock:
        stack.enter_context(patch("beyin.cli.save_state"))
    stack.enter_context(patch("beyin.cli.load_model", return_value=MagicMock()))
    stack.enter_context(patch("beyin.cli.get_collection", return_value=MagicMock()))
    if detect_side_effects:
        stack.enter_context(patch("beyin.cli.detect_source_type", side_effect=detect_side_effects))
    else:
        stack.enter_context(patch("beyin.cli.detect_source_type", return_value="article"))
    stack.enter_context(patch("beyin.cli.is_processed", return_value=is_processed_return))
    if fetch_side_effects is not None:
        fetch_sequence = None
        fetch_callable = None
        if isinstance(fetch_side_effects, Callable):
            fetch_callable = fetch_side_effects
        else:
            fetch_sequence = iter(fetch_side_effects)

        def _resolve(url: str):
            result = fetch_callable(url) if fetch_callable else next(fetch_sequence)
            if result is None:
                return None
            text, title = result
            return {
                "mode": "article",
                "text": text,
                "title": title,
                "metadata_url": url,
            }
        stack.enter_context(
            patch(
                "beyin.cli.resolve_article_ingestion",
                side_effect=_resolve,
            )
        )
    else:
        stack.enter_context(
            patch(
                "beyin.cli.resolve_article_ingestion",
                return_value={
                    "mode": "article",
                    "text": fetch_return[0],
                    "title": fetch_return[1],
                    "metadata_url": "https://example.com/article",
                },
            )
        )
    stack.enter_context(patch("beyin.cli.chunk_text", return_value=["chunk"]))
    stack.enter_context(patch("beyin.cli.embed_and_store", return_value=embed_return))
    stack.enter_context(patch("beyin.cli.mark_processed"))
    stack.enter_context(patch("beyin.cli.mark_failed"))
    if extra:
        for name, kwargs in extra.items():
            stack.enter_context(patch(name, **kwargs))
    return stack


# ---------------------------------------------------------------------------
# Podcast episode ingestion test
# ---------------------------------------------------------------------------

def test_list_podcast_episodes_keeps_transcript_only_entries(monkeypatch):
    """RSS entries with substantial transcript text should be ingested even without audio enclosures."""
    from beyin.downloader import list_podcast_episodes

    class _Entry(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

    entry = _Entry(
        id="ep-1",
        title="Transcript-first episode",
        link="https://example.com/posts/ep-1",
        content=[{"value": "<p>" + ("hello world " * 80) + "</p>"}],
        links=[],
        enclosures=[],
    )

    fake_feed = SimpleNamespace(entries=[entry])
    monkeypatch.setitem(sys.modules, "feedparser", SimpleNamespace(parse=lambda _url: fake_feed))

    episodes = list_podcast_episodes("https://example.com/feed.rss", limit=None)

    assert len(episodes) == 1
    assert episodes[0]["title"] == "Transcript-first episode"
    assert episodes[0]["guid"] == "ep-1"
    assert episodes[0]["entry_url"] == "https://example.com/posts/ep-1"
    assert "transcript_text" in episodes[0]


# ---------------------------------------------------------------------------
# Basic build tests
# ---------------------------------------------------------------------------

def test_build_help_shows_source_selector_flag():
    """build --help should advertise the non-destructive source selector flag."""
    from beyin.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["build", "--help"])

    assert result.exit_code == 0
    assert "--source" in result.output


def test_build_exits_cleanly_when_punkt_tab_is_missing(tmp_pack_root):
    """build should stop with a clear dependency message instead of an NLTK traceback."""
    from beyin.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch(
             "beyin.cli._punkt_tab_build_issue",
             return_value="NLTK sentence tokenizer data 'punkt_tab' is required for builds. Install it with: beyin check-deps --fix",
         ):
        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 1
    assert "punkt_tab" in result.output
    assert "beyin check-deps --fix" in result.output


def test_build_exits_0(tmp_pack_root):
    """build command with mocked pipeline exits 0."""
    from beyin.cli import app
    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()

    mock_model = MagicMock()
    mock_collection = MagicMock()
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}) as mock_load_state, \
         patch("beyin.cli.check_model_provenance") as mock_prov, \
         patch("beyin.cli.save_state") as mock_save, \
         patch("beyin.cli.load_model", return_value=mock_model), \
         patch("beyin.cli.get_collection", return_value=mock_collection), \
         patch("beyin.cli.detect_source_type", return_value="article"), \
         patch("beyin.cli.is_processed", return_value=False), \
         patch("beyin.cli.resolve_article_ingestion", return_value={"mode": "article", "text": "Article text", "title": "Article Title", "metadata_url": "https://example.com/article"}), \
         patch("beyin.cli.chunk_text", return_value=["chunk one", "chunk two"]), \
         patch("beyin.cli.embed_and_store", return_value=2), \
         patch("beyin.cli.mark_processed") as mock_mark, \
         patch("beyin.cli.mark_failed") as mock_fail:

        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"


def test_build_calls_check_model_provenance_before_embed(tmp_pack_root):
    """build calls check_model_provenance before any embed_and_store call."""
    from beyin.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    call_order = []

    def mock_prov(state, model, pack_name):
        call_order.append("provenance")

    def mock_embed(collection, model, chunks, metadatas, url):
        call_order.append("embed")
        return 1

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.check_model_provenance", side_effect=mock_prov), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="article"), \
         patch("beyin.cli.is_processed", return_value=False), \
         patch("beyin.cli.resolve_article_ingestion", return_value={"mode": "article", "text": "text", "title": "title", "metadata_url": "https://example.com/article"}), \
         patch("beyin.cli.chunk_text", return_value=["chunk"]), \
         patch("beyin.cli.embed_and_store", side_effect=mock_embed), \
         patch("beyin.cli.mark_processed"), \
         patch("beyin.cli.mark_failed"):

        runner.invoke(app, ["build", "test-pack"])

    assert call_order.index("provenance") < call_order.index("embed"), \
        "check_model_provenance must be called before embed_and_store"


def test_build_skips_already_processed_urls(tmp_pack_root):
    """build skips URLs that is_processed returns True for."""
    from beyin.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": "all-MiniLM-L6-v2", "processed": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="article"), \
         patch("beyin.cli.is_processed", return_value=True), \
         patch("beyin.cli.resolve_article_ingestion") as mock_resolve, \
         patch("beyin.cli.fetch_article") as mock_fetch, \
         patch("beyin.cli.embed_and_store") as mock_embed, \
         patch("beyin.cli.chunk_text"), \
         patch("beyin.cli.mark_processed"), \
         patch("beyin.cli.mark_failed"):

        result = runner.invoke(app, ["build", "test-pack"])

    mock_resolve.assert_not_called()
    mock_fetch.assert_not_called()
    mock_embed.assert_not_called()
    assert "skip" in result.output


def test_build_retries_previously_failed_source_in_state(tmp_path):
    """build should retry sources with cached failed state instead of skipping them."""
    from beyin.cli import app
    from beyin.pack_state import save_state
    from beyin.source_ids import canonical_source_id

    packs_root = tmp_path / "beyin"
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
    save_state(
        pack_dir,
        {
            "embedding_model": None,
            "processed": {
                canonical_source_id("https://example.com/article"): {
                    "status": "failed",
                    "url": "https://example.com/article",
                    "reason": "missing dependency",
                }
            },
            "audio_steps": {},
        },
    )

    runner = CliRunner()
    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.detect_source_type", return_value="article"), \
         patch(
             "beyin.cli.resolve_article_ingestion",
             return_value={
                 "mode": "article",
                 "text": "Article text",
                 "title": "Article title",
                 "metadata_url": "https://example.com/article",
             },
         ) as mock_resolve, \
         patch("beyin.cli.chunk_text", return_value=["chunk"]), \
         patch("beyin.cli.embed_and_store", return_value=1) as mock_embed:
        result = runner.invoke(app, ["build", "test-pack"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    mock_resolve.assert_called_once_with("https://example.com/article")
    mock_embed.assert_called_once()
    assert "[skip]" not in result.output


def test_build_warns_and_marks_failed_when_fetch_returns_none(tmp_pack_root):
    """build logs warning and calls mark_failed when fetch_article returns None."""
    from beyin.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="article"), \
         patch("beyin.cli.is_processed", return_value=False), \
         patch("beyin.cli.resolve_article_ingestion", return_value=None), \
         patch("beyin.cli.embed_and_store") as mock_embed, \
         patch("beyin.cli.chunk_text"), \
         patch("beyin.cli.mark_processed") as mock_mark, \
         patch("beyin.cli.mark_failed") as mock_fail:

        result = runner.invoke(app, ["build", "test-pack"], catch_exceptions=False)

    mock_embed.assert_not_called()
    mock_mark.assert_not_called()
    mock_fail.assert_called_once()
    # Warning output (stderr is merged into output by CliRunner by default)
    assert "warn" in result.output.lower()


def test_build_local_path_reads_text_without_remote_fetch(tmp_path):
    """build ingests a local text-like path through the narrow local loader."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "local-pack"
    pack_dir.mkdir(parents=True)
    source = tmp_path / "notes.md"
    source.write_text("# Notes\n\nLocal build content.\n", encoding="utf-8")
    (pack_dir / "pack.yaml").write_text(
        "name: local-pack\n"
        "description: Local source pack\n"
        "llm: ollama\n"
        "sources:\n"
        f"  - {source}\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.fetch_article") as mock_fetch, \
         patch("beyin.cli.chunk_text", return_value=["chunk one"]), \
         patch("beyin.cli.embed_and_store", return_value=1), \
         patch("beyin.cli.mark_processed") as mock_mark, \
         patch("beyin.cli.mark_failed") as mock_fail:
        result = runner.invoke(app, ["build", "local-pack"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"
    mock_fetch.assert_not_called()
    mock_mark.assert_called_once()
    mock_fail.assert_not_called()
    assert "done" in result.output.lower()


def test_build_local_path_missing_file_fails_clearly(tmp_path):
    """build marks missing local text-like sources failed without treating them as remote articles."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "missing-local-pack"
    pack_dir.mkdir(parents=True)
    missing = tmp_path / "missing.md"
    (pack_dir / "pack.yaml").write_text(
        "name: missing-local-pack\n"
        "description: Missing local source pack\n"
        "llm: ollama\n"
        "sources:\n"
        f"  - {missing}\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.fetch_article") as mock_fetch, \
         patch("beyin.cli.chunk_text") as mock_chunk, \
         patch("beyin.cli.embed_and_store") as mock_embed, \
         patch("beyin.cli.mark_processed") as mock_mark, \
         patch("beyin.cli.mark_failed") as mock_fail:
        result = runner.invoke(app, ["build", "missing-local-pack"])

    # Failed sources exit non-zero (plan 12-03 spec: unresolved failures return non-zero)
    assert result.exit_code == 1, f"Exit code {result.exit_code}, output: {result.output}"
    mock_fetch.assert_not_called()
    mock_chunk.assert_not_called()
    mock_embed.assert_not_called()
    mock_mark.assert_not_called()
    mock_fail.assert_called_once()
    assert "missing local source" in result.output.lower()


def test_build_local_path_unsupported_suffix_fails_clearly(tmp_path):
    """build keeps local-file support narrow and rejects unsupported local suffixes."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "binary-pack"
    pack_dir.mkdir(parents=True)
    source = tmp_path / "recording.bin"
    source.write_bytes(b"binary")
    (pack_dir / "pack.yaml").write_text(
        "name: binary-pack\n"
        "description: Unsupported local source pack\n"
        "llm: ollama\n"
        "sources:\n"
        f"  - {source}\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.fetch_article") as mock_fetch, \
         patch("beyin.cli.chunk_text") as mock_chunk, \
         patch("beyin.cli.embed_and_store") as mock_embed, \
         patch("beyin.cli.mark_processed") as mock_mark, \
         patch("beyin.cli.mark_failed") as mock_fail:
        result = runner.invoke(app, ["build", "binary-pack"])

    # Failed sources exit non-zero (plan 12-03 spec: unresolved failures return non-zero)
    assert result.exit_code == 1, f"Exit code {result.exit_code}, output: {result.output}"
    mock_fetch.assert_not_called()
    mock_chunk.assert_not_called()
    mock_embed.assert_not_called()
    mock_mark.assert_not_called()
    mock_fail.assert_called_once()
    assert "unsupported local source type" in result.output.lower()


def test_build_local_document_missing_parser_points_to_selected_support(tmp_path):
    """build should explain missing document parser support in terms of the selected local file type."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "pdf-pack"
    pack_dir.mkdir(parents=True)
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%stub\n")
    (pack_dir / "pack.yaml").write_text(
        "name: pdf-pack\n"
        "description: Local pdf source pack\n"
        "llm: ollama\n"
        "sources:\n"
        f"  - {pdf_path}\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    runner = CliRunner()
    fake_settings = type(
        "S",
        (),
        {
            "enabled_capabilities": ["local_files"],
            "enabled_local_file_types": ["pdf"],
            "preferred_transcription_backend": "faster-whisper",
            "preferred_whisper_model": "small",
            "preferred_llm_model": "llama3.2",
        },
    )()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_settings", return_value=fake_settings), \
         patch(
             "beyin.cli.load_document_source",
             side_effect=ImportError(
                 ".pdf support requires 'pdfplumber'. Install the matching Python package in the same environment as beyin, then rerun the build. Run `beyin check-deps` for details."
             ),
         ), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.mark_processed") as mock_mark, \
         patch("beyin.cli.mark_failed") as mock_fail:
        result = runner.invoke(app, ["build", "pdf-pack"])

    assert result.exit_code == 1, f"Exit code {result.exit_code}, output: {result.output}"
    mock_mark.assert_not_called()
    mock_fail.assert_called_once()
    assert "pdf support is selected in your beyin settings" in result.output.lower()
    assert "same environment as beyin" in result.output.lower()
    assert "beyin check-deps" in result.output
    assert "beyin build pdf-pack" in result.output


def test_build_can_limit_to_selected_source_indexes_without_mutating_pack(tmp_path):
    """build --source should process only the selected current sources and keep pack.yaml unchanged."""
    from beyin.cli import app
    from beyin.config import PackConfig, write_config

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    original_sources = [
        SourceEntry(url="https://example.com/article-1", title="Article One"),
        SourceEntry(url="https://example.com/article-2", title="Article Two"),
        SourceEntry(url="https://example.com/article-3", title="Article Three"),
    ]
    write_config(
        PackConfig(
            id="test-pack",
            name="test-pack",
            description="Test pack",
            llm="ollama",
            sources=original_sources,
        ),
        pack_dir / "pack.yaml",
    )

    runner = CliRunner()
    fetch_calls: list[str] = []

    def _fetch(url: str):
        fetch_calls.append(url)
        return f"content for {url}", f"title for {url}"

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli._has_audio_sources", return_value=False), \
         patch("beyin.cli.detect_source_type", return_value="article"), \
         patch("beyin.cli.is_processed", return_value=False), \
         patch(
             "beyin.cli.resolve_article_ingestion",
             side_effect=lambda url: (
                 lambda content, title: {
                     "mode": "article",
                     "text": content,
                     "title": title,
                     "metadata_url": url,
                 }
             )(*_fetch(url)),
         ), \
         patch("beyin.cli.chunk_text", return_value=["chunk1"]), \
         patch("beyin.cli.embed_and_store", return_value=1):
        result = runner.invoke(app, ["build", "test-pack", "--source", "1-2"])

    config = load_config(pack_dir)
    state = json.loads((pack_dir / "meta.json").read_text())

    assert result.exit_code == 0, result.output
    assert "Building 2 selected source(s)" in result.output
    assert fetch_calls == [
        "https://example.com/article-1",
        "https://example.com/article-2",
    ]
    assert [source.url for source in config.sources] == [source.url for source in original_sources]
    assert state["last_build_result"] == "partial-selection"
    assert state.get("last_built_pack_hash") is None
    assert state.get("last_build_at") is None


@pytest.mark.parametrize(
    ("pack_yaml", "settings_model", "build_args", "expected_model"),
    [
        (
            "name: test-pack\n"
            "description: Test\n"
            "llm: ollama\n"
            "sources:\n"
            "  - https://www.youtube.com/@channel\n"
            "embedding_model: all-MiniLM-L6-v2\n"
            "whisper_model: large\n",
            "small",
            ["--model", "medium"],
            "medium",
        ),
        (
            "name: test-pack\n"
            "description: Test\n"
            "llm: ollama\n"
            "sources:\n"
            "  - https://www.youtube.com/@channel\n"
            "embedding_model: all-MiniLM-L6-v2\n"
            "whisper_model: large\n",
            "medium",
            [],
            "medium",
        ),
        (
            "name: test-pack\n"
            "description: Test\n"
            "llm: ollama\n"
            "sources:\n"
            "  - https://www.youtube.com/@channel\n"
            "embedding_model: all-MiniLM-L6-v2\n",
            "medium",
            [],
            "medium",
        ),
        (
            "name: test-pack\n"
            "description: Test\n"
            "llm: ollama\n"
            "sources:\n"
            "  - https://www.youtube.com/@channel\n"
            "embedding_model: all-MiniLM-L6-v2\n",
            "small",
            ["--model", "small.en"],
            "small.en",
        ),
    ],
)
def test_build_whisper_settings_precedence_for_audio_sources(
    monkeypatch,
    tmp_path,
    pack_yaml,
    settings_model,
    build_args,
    expected_model,
):
    """build resolves whisper defaults as CLI > pack config > global settings > fallback."""
    from beyin.cli import app

    monkeypatch.setenv("HOME", str(tmp_path))
    _save_global_settings(tmp_path, preferred_whisper_model=settings_model)

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(pack_yaml, encoding="utf-8")

    runner = CliRunner()
    audio_file = tmp_path / "audio.m4a"
    audio_file.write_bytes(b"x" * 20_000)
    episode = {"id": "vid123", "title": "Test Video", "url": "https://youtu.be/vid123"}
    segments = [{"start": 0.0, "end": 5.0, "text": "Content"}]
    mock_transcribe = MagicMock(return_value=segments)

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli._youtube_build_issue", return_value=None), \
         patch("beyin.cli._check_ffmpeg_available", return_value=True), \
         patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
         patch("beyin.cli.download_audio", return_value=audio_file), \
         patch("beyin.cli.transcribe_audio", mock_transcribe), \
         patch("beyin.cli.chunk_text", return_value=["chunk1"]), \
         patch("beyin.cli.embed_and_store", return_value=1), \
         patch("beyin.cli.is_audio_step_done", return_value=False), \
         patch("beyin.cli.get_audio_step", return_value={}), \
         patch("beyin.cli.mark_audio_step"), \
         patch("beyin.cli.mark_failed"):
        result = runner.invoke(app, ["build", "test-pack", *build_args])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
    _, kwargs = mock_transcribe.call_args
    assert kwargs.get("model_size") == expected_model


def test_build_local_media_source_transcribes_without_download(tmp_path):
    """build should route local media sources through transcription without downloader calls."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    local_video = tmp_path / "demo.mp4"
    local_video.write_bytes(b"x" * 20_000)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: Test\n"
        "llm: ollama\n"
        "sources:\n"
        f"  - url: {local_video}\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    runner = CliRunner()
    segments = [{"start": 0.0, "end": 5.0, "text": "Content"}]
    mock_transcribe = MagicMock(return_value=segments)

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.check_transcription_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli._check_ffmpeg_available", return_value=True), \
         patch("beyin.cli.download_audio") as mock_download_audio, \
         patch("beyin.cli.download_podcast_audio") as mock_download_podcast_audio, \
         patch("beyin.cli.transcribe_audio", mock_transcribe), \
         patch("beyin.cli.chunk_text", return_value=["chunk1"]), \
         patch("beyin.cli.embed_and_store", return_value=1), \
         patch("beyin.cli.is_audio_step_done", return_value=False), \
         patch("beyin.cli.get_audio_step", return_value={}), \
         patch("beyin.cli.mark_audio_step"), \
         patch("beyin.cli.mark_failed"):
        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 0, result.output
    mock_download_audio.assert_not_called()
    mock_download_podcast_audio.assert_not_called()
    mock_transcribe.assert_called_once()
    transcribe_path = mock_transcribe.call_args.args[0]
    assert transcribe_path == local_video
    assert transcribe_path.suffix == ".mp4"


def test_build_persists_structured_transcripts_with_timestamps(tmp_path):
    """Fresh audio transcripts persist structured segments and chunk timestamp metadata."""
    from beyin.cli import app
    from beyin.source_ids import artifact_stem, canonical_source_id

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: Test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://www.youtube.com/@channel\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    runner = CliRunner()
    audio_dir = pack_dir / "audio"
    audio_dir.mkdir()
    transcripts_dir = pack_dir / "transcripts"
    transcripts_dir.mkdir()

    episode = {"id": "vid123", "title": "Test Video", "url": "https://youtu.be/vid123"}
    source_id = canonical_source_id(episode, source_type="youtube")
    audio_path = audio_dir / f"{artifact_stem(source_id)}.m4a"
    audio_path.write_bytes(b"x" * 20_000)
    segments = [
        {"start": 0.0, "end": 5.0, "text": "Hello world."},
        {"start": 5.0, "end": 9.0, "text": "Second segment."},
    ]
    captured = {}
    mock_config = _make_config([SourceEntry(url="https://www.youtube.com/@channel")])

    def _capture_embed(_collection, _model, chunks, metadatas, url):
        captured["chunks"] = chunks
        captured["metadatas"] = metadatas
        captured["url"] = url
        return len(chunks)

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="youtube"), \
         patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
         patch("beyin.cli._check_ffmpeg_available", return_value=True), \
         patch("beyin.cli._youtube_build_issue", return_value=None), \
         patch("beyin.cli.download_audio", return_value=audio_path), \
         patch("beyin.cli.transcribe_audio", return_value=segments), \
         patch("beyin.cli.embed_and_store", side_effect=_capture_embed):

        result = runner.invoke(app, ["build", "test-pack"])

    transcript_path = transcripts_dir / f"{artifact_stem(source_id)}.json"
    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
    assert transcript_path.exists()
    assert json.loads(transcript_path.read_text()) == segments
    assert captured["metadatas"][0]["timestamp_start"] == 0.0
    assert captured["metadatas"][0]["timestamp_end"] == 9.0
    assert captured["url"] == source_id


def test_build_resume_reuses_structured_transcript_segments(tmp_path):
    """Resumed audio builds reload structured transcripts instead of collapsing timestamps."""
    from beyin.cli import app
    from beyin.pack_state import save_state
    from beyin.source_ids import artifact_stem, canonical_source_id

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: Test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://www.youtube.com/@channel\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    runner = CliRunner()
    audio_dir = pack_dir / "audio"
    audio_dir.mkdir()
    transcripts_dir = pack_dir / "transcripts"
    transcripts_dir.mkdir()

    episode = {"id": "vid123", "title": "Test Video", "url": "https://youtu.be/vid123"}
    source_id = canonical_source_id(episode, source_type="youtube")
    audio_path = audio_dir / f"{artifact_stem(source_id)}.m4a"
    audio_path.write_bytes(b"x" * 20_000)
    transcript_path = transcripts_dir / f"{artifact_stem(source_id)}.json"
    segments = [
        {"start": 12.0, "end": 15.0, "text": "Recovered segment one."},
        {"start": 15.0, "end": 21.0, "text": "Recovered segment two."},
    ]
    transcript_path.write_text(json.dumps(segments))
    save_state(
        pack_dir,
        {
            "embedding_model": "all-MiniLM-L6-v2",
            "processed": {},
            "audio_steps": {
                source_id: {
                    "source_id": source_id,
                    "url": episode["url"],
                    "title": episode["title"],
                    "stages": {"downloaded": True, "transcribed": True},
                }
            },
        },
    )

    captured = {}
    mock_config = _make_config([SourceEntry(url="https://www.youtube.com/@channel")])

    def _capture_embed(_collection, _model, chunks, metadatas, url):
        captured["chunks"] = chunks
        captured["metadatas"] = metadatas
        captured["url"] = url
        return len(chunks)

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="youtube"), \
         patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
         patch("beyin.cli._check_ffmpeg_available", return_value=True), \
         patch("beyin.cli._youtube_build_issue", return_value=None), \
         patch("beyin.cli.download_audio") as mock_download, \
         patch("beyin.cli.transcribe_audio") as mock_transcribe, \
         patch("beyin.cli.embed_and_store", side_effect=_capture_embed):

        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
    mock_download.assert_not_called()
    mock_transcribe.assert_not_called()
    assert captured["metadatas"][0]["timestamp_start"] == 12.0
    assert captured["metadatas"][0]["timestamp_end"] == 21.0


def test_build_youtube_source_fails_when_ytdlp_unavailable(tmp_path):
    """YouTube builds fail cleanly when yt-dlp is missing or outdated."""
    from beyin.cli import app
    from beyin.install_hints import yt_dlp_install_hint
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: Test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://www.youtube.com/@channel\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    runner = CliRunner()
    mock_config = _make_config([SourceEntry(url="https://www.youtube.com/@channel")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli._youtube_build_issue", return_value=f"yt-dlp is not installed. Install or upgrade with: {yt_dlp_install_hint()}"), \
         patch("beyin.cli._check_ffmpeg_available", return_value=True), \
         patch("beyin.cli.list_youtube_episodes") as mock_list:
        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 1
    assert "yt-dlp is not installed" in result.output
    mock_list.assert_not_called()


def test_build_mixed_pack_keeps_articles_when_audio_is_blocked(tmp_path):
    """Mixed packs still build article sources when audio work is blocked by ffmpeg."""
    from beyin.cli import app
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\n"
        "description: Test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "  - https://www.youtube.com/@channel\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    runner = CliRunner()
    mock_config = _make_config(
        [
            SourceEntry(url="https://example.com/article"),
            SourceEntry(url="https://www.youtube.com/@channel"),
        ]
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", side_effect=["article", "youtube"]), \
         patch("beyin.cli.resolve_article_ingestion", return_value={"mode": "article", "text": "Article text", "title": "Article Title", "metadata_url": "https://example.com/article"}), \
         patch("beyin.cli.chunk_text", return_value=["chunk one"]), \
         patch("beyin.cli.embed_and_store", return_value=1), \
         patch("beyin.cli._check_ffmpeg_available", return_value=False), \
         patch("beyin.cli._youtube_build_issue", return_value=None):
        result = runner.invoke(app, ["build", "test-pack", "--verbose"])

    assert result.exit_code == 1
    assert "[embed] Article Title" in result.output
    assert "blocked" in result.output
    assert "ffmpeg" in result.output.lower()


# ---------------------------------------------------------------------------
# Phase 12 Plan 03: Build output polish
# ---------------------------------------------------------------------------

def test_build_always_prints_summary_table_for_zero_new_run(tmp_path):
    """build must print a compact summary table even when all sources are already up-to-date."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    with _p12_article_patches(packs_root, mock_config, is_processed_return=True):
        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 0
    output = result.output
    # Even for all-up-to-date builds, a summary table must appear
    assert "Source" in output or "Status" in output
    # And the result line should mention the count
    assert "0 new" in output or "up to date" in output


def test_build_mixed_result_prints_completed_with_issues_verdict(tmp_path):
    """build with a mix of success and failure sources must print 'completed with issues' verdict."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://example.com/good\n"
        "  - https://example.com/bad\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    mock_config = _make_config([
        SourceEntry(url="https://example.com/good"),
        SourceEntry(url="https://example.com/bad"),
    ])

    with _p12_article_patches(
        packs_root, mock_config,
        fetch_side_effects=[("Article text", "Good Article"), None],
        embed_return=1,
    ):
        result = runner.invoke(app, ["build", "test-pack"])

    output = result.output
    # Must show a clear "completed with issues" verdict (not just silent partial success)
    assert "issue" in output.lower() or "warning" in output.lower() or "failed" in output.lower()
    # Must still show the successful count
    assert "1" in output
    # Exit code should be non-zero because there were unresolved failures
    assert result.exit_code != 0


def test_build_blocked_result_prints_completed_with_issues_and_exit_nonzero(tmp_path):
    """build with blocked audio source exits non-zero and prints an explicit verdict."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "  - https://youtube.com/@channel\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    mock_config = _make_config([
        SourceEntry(url="https://example.com/article"),
        SourceEntry(url="https://youtube.com/@channel"),
    ])

    with _p12_article_patches(
        packs_root, mock_config,
        fetch_return=("Text", "Title"),
        detect_side_effects=["article", "youtube"],
        embed_return=2,
        extra={
            "beyin.cli._check_ffmpeg_available": {"return_value": False},
            "beyin.cli._youtube_build_issue": {"return_value": None},
        },
    ):
        result = runner.invoke(app, ["build", "test-pack"])

    output = result.output
    assert result.exit_code != 0
    # Blocked verdict must be explicit, not just a warning line
    assert "issue" in output.lower() or "blocked" in output.lower() or "completed with" in output.lower()
    # Successful work must still be visible in final output
    assert "Title" in output or "2" in output


def test_build_blocker_warnings_repeated_in_final_recap(tmp_path):
    """build repeats warning/blocker lines in a short recap at the end, not just inline."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://example.com/good\n"
        "  - https://example.com/bad\n"
        "  - https://example.com/also-bad\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    mock_config = _make_config([
        SourceEntry(url="https://example.com/good"),
        SourceEntry(url="https://example.com/bad"),
        SourceEntry(url="https://example.com/also-bad"),
    ])

    with _p12_article_patches(
        packs_root, mock_config,
        fetch_side_effects=[("Article text", "Good Article"), None, None],
        embed_return=1,
    ):
        result = runner.invoke(app, ["build", "test-pack"])

    output = result.output
    # The failed sources must appear somewhere in the output (inline or recap)
    # Count how many times "bad" or "failed" appears -- recap at end means it should appear at least twice
    # (once inline, once in recap)
    failed_mentions = output.lower().count("fail") + output.lower().count("bad")
    assert failed_mentions >= 2, (
        f"Expected failed sources to appear multiple times (inline + recap), "
        f"got {failed_mentions} in: {output!r}"
    )


def test_build_persists_last_build_recap_for_mixed_result(tmp_path):
    """build persists last_build_result and last_build_summary into state for mixed outcomes."""
    from beyin.cli import app
    from beyin.pack_state import load_state
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://example.com/good\n"
        "  - https://example.com/bad\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    mock_config = _make_config([
        SourceEntry(url="https://example.com/good"),
        SourceEntry(url="https://example.com/bad"),
    ])

    # Don't mock save_state -- we need real disk writes to verify persistence
    with _p12_article_patches(
        packs_root, mock_config,
        fetch_side_effects=[("Article text", "Good Article"), None],
        embed_return=1,
        save_state_mock=False,
        extra={"beyin.cli._youtube_build_issue": {"return_value": None}},
    ):
        result = runner.invoke(app, ["build", "test-pack"])

    # Load actual state from disk (not mocked) to verify persistence
    final_state = load_state(pack_dir)
    assert final_state.get("last_build_result") in ("mixed", "failed", "completed_with_issues"), (
        f"Expected a non-None recap result, got: {final_state.get('last_build_result')!r}"
    )
    assert final_state.get("last_build_summary") is not None, (
        "last_build_summary must be persisted for mixed builds"
    )


def test_build_persists_last_build_recap_for_clean_success(tmp_path):
    """build persists last_build_result='success' into state for clean builds."""
    from beyin.cli import app
    from beyin.pack_state import load_state
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    # Don't mock save_state -- we need real disk writes to verify persistence
    with _p12_article_patches(
        packs_root, mock_config,
        fetch_return=("Article text", "Good Article"),
        embed_return=2,
        save_state_mock=False,
        extra={"beyin.cli._youtube_build_issue": {"return_value": None}},
    ):
        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 0
    final_state = load_state(pack_dir)
    assert final_state.get("last_build_result") in ("success", "ok", "done"), (
        f"Expected success result, got: {final_state.get('last_build_result')!r}"
    )
    assert final_state.get("last_build_summary") is not None


def test_build_audio_shows_episode_progress_with_counter(tmp_path):
    """build shows 'Episode N/Total' counter for each audio episode being processed."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "testpack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: testpack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://youtube.com/watch?v=abc\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"x" * 11_000)

    episodes = [
        {"url": "https://youtube.com/watch?v=1", "title": "Ep 1", "id": "1"},
        {"url": "https://youtube.com/watch?v=2", "title": "Ep 2", "id": "2"},
    ]
    mock_config = _make_config([SourceEntry(url="https://youtube.com/watch?v=abc")])

    stack = ExitStack()
    stack.enter_context(patch("beyin.cli._PACKS_DIR", packs_root))
    stack.enter_context(patch("beyin.cli.load_config", return_value=mock_config))
    stack.enter_context(patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}))
    stack.enter_context(patch("beyin.cli.check_model_provenance"))
    stack.enter_context(patch("beyin.cli.save_state"))
    stack.enter_context(patch("beyin.cli.load_model", return_value=MagicMock()))
    stack.enter_context(patch("beyin.cli.get_collection", return_value=MagicMock()))
    stack.enter_context(patch("beyin.cli.detect_source_type", return_value="youtube"))
    stack.enter_context(patch("beyin.cli.check_deno_available", return_value=True))
    stack.enter_context(patch("beyin.cli._youtube_build_issue", return_value=None))
    stack.enter_context(patch("beyin.cli._check_ffmpeg_available", return_value=True))
    stack.enter_context(patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)))
    stack.enter_context(patch("beyin.cli.is_audio_step_done", return_value=False))
    stack.enter_context(patch("beyin.cli.get_audio_step", return_value={}))
    stack.enter_context(patch("beyin.cli.download_audio", return_value=audio_file))
    stack.enter_context(patch("beyin.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]))
    stack.enter_context(patch("beyin.cli.embed_and_store", return_value=3))
    stack.enter_context(patch("beyin.cli.mark_audio_step"))
    stack.enter_context(patch("beyin.cli._canonical_audio_path", return_value=audio_file))
    stack.enter_context(patch("beyin.cli._save_transcript_segments"))
    stack.enter_context(patch("beyin.cli._chunk_transcript_segments", return_value=(["chunk"], [{}])))

    with stack:
        result = runner.invoke(app, ["build", "testpack", "--verbose"])

    output = result.output
    # Episode-level progress with counter should appear
    assert "1/2" in output or "Episode 1" in output, (
        f"Expected episode progress counter, got: {output!r}"
    )
    assert "2/2" in output or "Episode 2" in output, (
        f"Expected episode 2 progress, got: {output!r}"
    )


def test_build_quiet_audio_shows_stage_progress_lines(tmp_path):
    """Non-verbose audio builds still show coarse download/transcribe/embed progress."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "testpack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: testpack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://youtube.com/watch?v=abc\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"x" * 11_000)

    episode = {"url": "https://youtube.com/watch?v=1", "title": "Ep 1", "id": "1"}
    mock_config = _make_config([SourceEntry(url="https://youtube.com/watch?v=abc")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="youtube"), \
         patch("beyin.cli._youtube_build_issue", return_value=None), \
         patch("beyin.cli._check_ffmpeg_available", return_value=True), \
         patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
         patch("beyin.cli.is_audio_step_done", return_value=False), \
         patch("beyin.cli.get_audio_step", return_value={}), \
         patch("beyin.cli.download_audio", return_value=audio_file), \
         patch("beyin.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]), \
         patch("beyin.cli.embed_and_store", return_value=3), \
         patch("beyin.cli.mark_audio_step"), \
         patch("beyin.cli._canonical_audio_path", return_value=audio_file), \
         patch("beyin.cli._save_transcript_segments"), \
         patch("beyin.cli._chunk_transcript_segments", return_value=(["chunk"], [{}])):
        result = runner.invoke(app, ["build", "testpack"])

    output = result.output
    assert "[download] Episode 1/1: Ep 1" in output
    assert "[transcribe] Episode 1/1: Ep 1" in output
    assert "[transcribe] Episode 1/1: Ep 1 —" in output
    assert "[embed] Episode 1/1: Ep 1" in output
    assert "[embed] Loading embedding model:" in output


def test_transcription_progress_reporter_renders_single_line_tty_updates():
    """TTY mode should rewrite one transcription line instead of printing stacked percentages."""
    from beyin.cli import _TranscriptionProgressReporter

    stdout = MagicMock()
    stdout.isatty.return_value = True

    with patch("beyin.cli.sys.stdout", stdout):
        reporter = _TranscriptionProgressReporter("Episode 1/1: Ep 1", verbose=False)
        reporter.start()
        reporter.callback(12.0, 100.0)
        reporter.callback(55.0, 100.0)
        reporter.finish(183.4)

    writes = "".join(call.args[0] for call in stdout.write.call_args_list)
    assert "[transcribe] Episode 1/1: Ep 1 [----------]   0%" in writes
    assert "[transcribe] Episode 1/1: Ep 1 [#---------]  10%" in writes
    assert "[transcribe] Episode 1/1: Ep 1 [#####-----]  50%" in writes
    assert "[transcribe] Episode 1/1: Ep 1 [##########] 100% in 3m 3.4s" in writes


def test_build_quiet_audio_shows_download_and_embed_elapsed_time(tmp_path):
    """Non-verbose audio builds should show elapsed time for download and embed stages."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "testpack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: testpack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://youtube.com/watch?v=abc\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"x" * 11_000)

    episode = {"url": "https://youtube.com/watch?v=1", "title": "Ep 1", "id": "1"}
    mock_config = _make_config([SourceEntry(url="https://youtube.com/watch?v=abc")])

    stack = ExitStack()
    stack.enter_context(patch("beyin.cli._PACKS_DIR", packs_root))
    stack.enter_context(patch("beyin.cli.load_config", return_value=mock_config))
    stack.enter_context(patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}))
    stack.enter_context(patch("beyin.cli.check_model_provenance"))
    stack.enter_context(patch("beyin.cli.save_state"))
    stack.enter_context(patch("beyin.cli.load_model", return_value=MagicMock()))
    stack.enter_context(patch("beyin.cli.get_collection", return_value=MagicMock()))
    stack.enter_context(patch("beyin.cli.detect_source_type", return_value="youtube"))
    stack.enter_context(patch("beyin.cli._youtube_build_issue", return_value=None))
    stack.enter_context(patch("beyin.cli._check_ffmpeg_available", return_value=True))
    stack.enter_context(patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])))
    stack.enter_context(patch("beyin.cli.is_audio_step_done", return_value=False))
    stack.enter_context(patch("beyin.cli.get_audio_step", return_value={}))
    stack.enter_context(patch("beyin.cli.download_audio", return_value=audio_file))
    stack.enter_context(patch("beyin.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]))
    stack.enter_context(patch("beyin.cli.embed_and_store", return_value=3))
    stack.enter_context(patch("beyin.cli.mark_audio_step"))
    stack.enter_context(patch("beyin.cli._canonical_audio_path", return_value=audio_file))
    stack.enter_context(patch("beyin.cli._save_transcript_segments"))
    stack.enter_context(patch("beyin.cli._chunk_transcript_segments", return_value=(["chunk"], [{}])))
    stack.enter_context(patch("beyin.cli.time.perf_counter", side_effect=[0.0, 1.2, 2.0, 3.7, 4.0, 5.7]))

    with stack:
        result = runner.invoke(app, ["build", "testpack"])

    output = result.output
    assert result.exit_code == 0, output
    assert "[download] Episode 1/1: Ep 1 — 1.2s" in output
    assert "[embed] Episode 1/1: Ep 1 — 3 chunks in 1.7s" in output


def test_build_quiet_audio_shows_transcription_elapsed_time(tmp_path):
    """Non-interactive quiet output should show final transcription elapsed time."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "testpack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: testpack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://youtube.com/watch?v=abc\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"x" * 11_000)
    episode = {"url": "https://youtube.com/watch?v=1", "title": "Ep 1", "id": "1"}
    mock_config = _make_config([SourceEntry(url="https://youtube.com/watch?v=abc")])

    stack = ExitStack()
    stack.enter_context(patch("beyin.cli._PACKS_DIR", packs_root))
    stack.enter_context(patch("beyin.cli.load_config", return_value=mock_config))
    stack.enter_context(patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}))
    stack.enter_context(patch("beyin.cli.check_model_provenance"))
    stack.enter_context(patch("beyin.cli.save_state"))
    stack.enter_context(patch("beyin.cli.load_model", return_value=MagicMock()))
    stack.enter_context(patch("beyin.cli.get_collection", return_value=MagicMock()))
    stack.enter_context(patch("beyin.cli.detect_source_type", return_value="youtube"))
    stack.enter_context(patch("beyin.cli._youtube_build_issue", return_value=None))
    stack.enter_context(patch("beyin.cli._check_ffmpeg_available", return_value=True))
    stack.enter_context(patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])))
    stack.enter_context(patch("beyin.cli.is_audio_step_done", return_value=False))
    stack.enter_context(patch("beyin.cli.get_audio_step", return_value={}))
    stack.enter_context(patch("beyin.cli.download_audio", return_value=audio_file))
    stack.enter_context(patch("beyin.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]))
    stack.enter_context(patch("beyin.cli.embed_and_store", return_value=3))
    stack.enter_context(patch("beyin.cli.mark_audio_step"))
    stack.enter_context(patch("beyin.cli._canonical_audio_path", return_value=audio_file))
    stack.enter_context(patch("beyin.cli._save_transcript_segments"))
    stack.enter_context(patch("beyin.cli._chunk_transcript_segments", return_value=(["chunk"], [{}])))
    stack.enter_context(patch("beyin.cli.time.perf_counter", side_effect=[0.0, 1.2, 2.0, 185.4, 186.0, 187.2]))

    with stack:
        result = runner.invoke(app, ["build", "testpack"])

    assert "[transcribe] Episode 1/1: Ep 1 — 3m 3.4s" in result.output


def test_build_clean_success_exits_0_and_shows_summary(tmp_path):
    """Clean build (no failures) exits 0 and always shows a final summary table."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    with _p12_article_patches(
        packs_root, mock_config,
        fetch_return=("Article text", "Article Title"),
        embed_return=2,
    ):
        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 0
    output = result.output
    # Always-on summary table: header must appear
    assert "Source" in output
    assert "Status" in output
    # Verdict line
    assert "complete" in output.lower() or "success" in output.lower() or "2 new" in output.lower()


def test_build_reset_flag_clears_runtime_artifacts_before_rebuild(tmp_path):
    """beyin build <pack> --reset clears runtime artifacts and then runs the normal build path."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    # Create runtime artifacts that should be cleared
    chroma_dir = pack_dir / "chroma"
    chroma_dir.mkdir()
    (chroma_dir / "data.bin").write_bytes(b"chroma")
    meta_file = pack_dir / "meta.json"
    meta_file.write_text('{"schema_version": 2}')

    mock_config = _make_config([SourceEntry(url="https://example.com/article")])
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="article"), \
         patch("beyin.cli.is_processed", return_value=False), \
         patch("beyin.cli.resolve_article_ingestion", return_value={"mode": "article", "text": "Article text", "title": "Article Title", "metadata_url": "https://example.com/article"}), \
         patch("beyin.cli.chunk_text", return_value=["chunk"]), \
         patch("beyin.cli.embed_and_store", return_value=1), \
         patch("beyin.cli.mark_processed"), \
         patch("beyin.cli.mark_failed"):
        result = runner.invoke(app, ["build", "test-pack", "--reset"])

    assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
    assert not chroma_dir.exists(), "--reset should have removed the chroma directory"


def test_build_reset_preserves_pack_yaml_and_origin_json(tmp_path):
    """beyin build <pack> --reset must not remove pack.yaml or origin.json."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    pack_yaml_text = (
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    (pack_dir / "pack.yaml").write_text(pack_yaml_text)
    origin_text = '{"source": "https://example.com/pack.yaml"}'
    (pack_dir / "origin.json").write_text(origin_text)

    mock_config = _make_config([SourceEntry(url="https://example.com/article")])
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="article"), \
         patch("beyin.cli.is_processed", return_value=False), \
         patch("beyin.cli.resolve_article_ingestion", return_value={"mode": "article", "text": "Article text", "title": "Article Title", "metadata_url": "https://example.com/article"}), \
         patch("beyin.cli.chunk_text", return_value=["chunk"]), \
         patch("beyin.cli.embed_and_store", return_value=1), \
         patch("beyin.cli.mark_processed"), \
         patch("beyin.cli.mark_failed"):
        result = runner.invoke(app, ["build", "test-pack", "--reset"])

    assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
    assert (pack_dir / "pack.yaml").read_text() == pack_yaml_text, "pack.yaml must survive --reset"
    assert (pack_dir / "origin.json").read_text() == origin_text, "origin.json must survive --reset"


def test_model_mismatch_remediation_points_to_build_reset(tmp_path):
    """Embedding model mismatch error message must point to `beyin build <pack> --reset`."""
    from beyin.pack_state import check_model_provenance

    state = {"embedding_model": "all-MiniLM-L6-v2"}
    import typer as _typer

    with pytest.raises(_typer.BadParameter) as exc_info:
        check_model_provenance(state, "paraphrase-multilingual-MiniLM-L12-v2", "my-pack")

    message = str(exc_info.value)
    assert "build" in message.lower() and "reset" in message.lower(), (
        f"Mismatch remediation should mention `build --reset`, got: {message!r}"
    )
    assert "delete" not in message.lower() and "chroma/" not in message, (
        f"Mismatch should not instruct manual deletion, got: {message!r}"
    )


def test_transcription_model_mismatch_remediation_points_to_build_reset():
    """Whisper model mismatch error message must point to `beyin build <pack> --reset`."""
    from beyin.pack_state import check_transcription_provenance

    state = {
        "transcription_model": "medium",
        "transcription_language": None,
        "audio_steps": {
            "youtube:abc": {
                "source_id": "youtube:abc",
                "url": "https://www.youtube.com/watch?v=abc",
                "stages": {"embedded": True},
            }
        },
    }
    import typer as _typer

    with pytest.raises(_typer.BadParameter) as exc_info:
        check_transcription_provenance(state, "small", None, "my-pack")

    message = str(exc_info.value)
    assert "build" in message.lower() and "reset" in message.lower()
    assert "medium" in message and "small" in message


def test_build_blocks_audio_pack_when_whisper_model_changes_without_reset(tmp_path):
    """Audio packs must not silently mix transcripts built with different Whisper models."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://youtube.com/watch?v=abc\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    mock_config = _make_config([SourceEntry(url="https://youtube.com/watch?v=abc")])
    state = {
        "embedding_model": "all-MiniLM-L6-v2",
        "transcription_model": "medium",
        "transcription_language": None,
        "processed": {},
        "audio_steps": {
            "youtube:abc": {
                "source_id": "youtube:abc",
                "url": "https://youtube.com/watch?v=abc",
                "stages": {"embedded": True},
            }
        },
    }

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value=state), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli._has_audio_sources", return_value=True):
        result = runner.invoke(app, ["build", "test-pack", "--model", "small"])

    assert result.exit_code == 2
    assert "Transcription model mismatch" in result.output
    assert "--reset" in result.output


# ---------------------------------------------------------------------------
# TestAudioBuild class
# ---------------------------------------------------------------------------

class TestAudioBuild:
    """Tests for audio source routing in the build command (Phase 2)."""

    def _base_patches(self, packs_root, extra_patches=None):
        """Return common patch context for audio build tests."""
        patches = {
            "beyin.cli._PACKS_DIR": packs_root,
            "beyin.cli.load_state": {"embedding_model": None, "processed": {}, "audio_steps": {}},
            "beyin.cli.check_model_provenance": MagicMock(),
            "beyin.cli.save_state": MagicMock(),
            "beyin.cli.load_model": MagicMock(),
            "beyin.cli.get_collection": MagicMock(),
            "beyin.cli.embed_and_store": 1,
            "beyin.cli.chunk_text": ["chunk1"],
            "beyin.cli.mark_audio_step": MagicMock(),
            "beyin.cli.is_audio_step_done": False,
            "beyin.cli.get_audio_step": {},
            "beyin.cli.mark_failed": MagicMock(),
            "beyin.cli.check_deno_available": True,
        }
        if extra_patches:
            patches.update(extra_patches)
        return patches

    def test_build_youtube_source(self, tmp_path):
        """build routes youtube source through list_youtube_episodes + download_audio + transcribe_audio."""
        from beyin.cli import app
        packs_root = tmp_path / "beyin"
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

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="youtube"), \
             patch("beyin.cli.check_deno_available", return_value=True), \
             patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
             patch("beyin.cli.download_audio", mock_download), \
             patch("beyin.cli.transcribe_audio", mock_transcribe), \
             patch("beyin.cli.chunk_text", return_value=["chunk1"]), \
             patch("beyin.cli.embed_and_store", mock_embed), \
             patch("beyin.cli.is_audio_step_done", return_value=False), \
             patch("beyin.cli.get_audio_step", return_value={}), \
             patch("beyin.cli.mark_audio_step"), \
             patch("beyin.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack", "--verbose"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        assert "[embed]" in result.output
        mock_download.assert_called_once()
        mock_transcribe.assert_called_once()
        mock_embed.assert_called_once()

    def test_build_podcast_source(self, tmp_path):
        """build routes podcast source through list_podcast_episodes + download_podcast_audio + transcribe_audio."""
        from beyin.cli import app
        packs_root = tmp_path / "beyin"
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

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="podcast"), \
             patch("beyin.cli.list_podcast_episodes", return_value=[episode]), \
             patch("beyin.cli.download_podcast_audio", mock_download), \
             patch("beyin.cli.transcribe_audio", mock_transcribe), \
             patch("beyin.cli.chunk_text", return_value=["chunk1"]), \
             patch("beyin.cli.embed_and_store", return_value=1), \
             patch("beyin.cli.is_audio_step_done", return_value=False), \
             patch("beyin.cli.get_audio_step", return_value={}), \
             patch("beyin.cli.mark_audio_step"), \
             patch("beyin.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        mock_download.assert_called_once()
        mock_transcribe.assert_called_once()

    def test_build_podcast_page_can_fallback_to_direct_audio(self, tmp_path):
        """Podcast-like episode pages should fall back to page resolution when feed parsing yields no episodes."""
        from beyin.cli import app

        packs_root = tmp_path / "beyin"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
            "  - https://example.com/episode\nembedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        audio_file = tmp_path / "episode.mp3"
        audio_file.write_bytes(b"x" * 20_000)

        mock_config = _make_config([SourceEntry(url="https://example.com/episode")])
        segments = [{"start": 0.0, "end": 10.0, "text": "Podcast content here"}]

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.check_transcription_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="podcast"), \
             patch("beyin.cli.list_podcast_episodes", return_value=[]), \
             patch("beyin.cli.resolve_article_ingestion", return_value={"mode": "podcast_audio", "audio_url": "https://cdn.example.com/episode.mp3", "title": "Episode 1", "metadata_url": "https://example.com/episode"}), \
             patch("beyin.cli._check_ffmpeg_available", return_value=True), \
             patch("beyin.cli.download_podcast_audio", return_value=audio_file) as mock_download, \
             patch("beyin.cli.transcribe_audio", return_value=segments) as mock_transcribe, \
             patch("beyin.cli.embed_and_store", return_value=1) as mock_embed, \
             patch("beyin.cli.is_audio_step_done", return_value=False), \
             patch("beyin.cli.get_audio_step", return_value={}), \
             patch("beyin.cli.mark_audio_step"), \
             patch("beyin.cli.mark_failed"):
            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 0, result.output
        mock_download.assert_called_once()
        mock_transcribe.assert_called_once()
        mock_embed.assert_called_once()

    def test_build_podcast_source_uses_feed_transcript_without_audio(self, tmp_path):
        """Podcast entries with transcript text should bypass download/transcription and not require ffmpeg."""
        from beyin.cli import app
        packs_root = tmp_path / "beyin"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
            "  - https://example.com/feed.rss\nembedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        episode = {
            "guid": "ep001",
            "title": "Podcast Episode 1",
            "url": "https://example.com/posts/ep1",
            "entry_url": "https://example.com/posts/ep1",
            "transcript_text": "podcast transcript " * 80,
        }
        mock_config = _make_config([SourceEntry(url="https://example.com/feed.rss")])

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.check_transcription_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="podcast"), \
             patch("beyin.cli.list_podcast_episodes", return_value=[episode]), \
             patch("beyin.cli._check_ffmpeg_available", return_value=False), \
             patch("beyin.cli.download_podcast_audio") as mock_download, \
             patch("beyin.cli.transcribe_audio") as mock_transcribe, \
             patch("beyin.cli.chunk_text", return_value=["chunk1"]), \
             patch("beyin.cli.embed_and_store", return_value=1), \
             patch("beyin.cli.is_audio_step_done", return_value=False), \
             patch("beyin.cli.get_audio_step", return_value={}), \
             patch("beyin.cli.mark_audio_step"), \
             patch("beyin.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        assert "[ingest] Episode 1/1: Podcast Episode 1" in result.output
        mock_download.assert_not_called()
        mock_transcribe.assert_not_called()

    def test_build_podcast_transcript_text_persists_real_chunks(self, tmp_path):
        """Transcript-aware RSS should split long transcript text into indexable chunks instead of saving one oversized segment."""
        from beyin.cli import app

        packs_root = tmp_path / "beyin"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\n"
            "description: Test\n"
            "llm: ollama\n"
            "sources:\n"
            "  - https://example.com/feed.rss\n"
            "embedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        episode = {
            "guid": "ep001",
            "title": "Podcast Episode 1",
            "url": "https://example.com/posts/ep1",
            "entry_url": "https://example.com/posts/ep1",
            "transcript_text": "\n".join(
                [f"Sentence {i}. This is a realistic podcast transcript paragraph." for i in range(1, 80)]
            ),
        }
        mock_config = _make_config([SourceEntry(url="https://example.com/feed.rss")])
        captured = {}

        def _capture_embed(collection, model, chunks, metadatas, url):
            captured["chunks"] = chunks
            captured["metadatas"] = metadatas
            captured["url"] = url
            return len(chunks)

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.check_transcription_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="podcast"), \
             patch("beyin.cli.list_podcast_episodes", return_value=[episode]), \
             patch("beyin.cli._check_ffmpeg_available", return_value=False), \
             patch("beyin.cli.download_podcast_audio") as mock_download, \
             patch("beyin.cli.transcribe_audio") as mock_transcribe, \
             patch("beyin.cli.embed_and_store", side_effect=_capture_embed), \
             patch("beyin.cli.is_audio_step_done", return_value=False), \
             patch("beyin.cli.get_audio_step", return_value={}), \
             patch("beyin.cli.mark_audio_step"), \
             patch("beyin.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 0, result.output
        assert captured["chunks"]
        assert all(chunk.strip() for chunk in captured["chunks"])
        mock_download.assert_not_called()
        mock_transcribe.assert_not_called()

    def test_build_model_flag_passed_to_transcribe(self, tmp_path):
        """build --model medium passes model_size='medium' to transcribe_audio."""
        from beyin.cli import app
        packs_root = tmp_path / "beyin"
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

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="youtube"), \
             patch("beyin.cli.check_deno_available", return_value=True), \
             patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
             patch("beyin.cli.download_audio", return_value=audio_file), \
             patch("beyin.cli.transcribe_audio", mock_transcribe), \
             patch("beyin.cli.chunk_text", return_value=["chunk1"]), \
             patch("beyin.cli.embed_and_store", return_value=1), \
             patch("beyin.cli.is_audio_step_done", return_value=False), \
             patch("beyin.cli.get_audio_step", return_value={}), \
             patch("beyin.cli.mark_audio_step"), \
             patch("beyin.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack", "--model", "medium"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        mock_transcribe.assert_called_once()
        _, kwargs = mock_transcribe.call_args
        assert kwargs.get("model_size") == "medium", f"Expected model_size='medium', got: {mock_transcribe.call_args}"

    def test_build_language_flag_passed_to_transcribe(self, tmp_path):
        """build --language tr passes language='tr' to transcribe_audio."""
        from beyin.cli import app
        packs_root = tmp_path / "beyin"
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

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="youtube"), \
             patch("beyin.cli.check_deno_available", return_value=True), \
             patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
             patch("beyin.cli.download_audio", return_value=audio_file), \
             patch("beyin.cli.transcribe_audio", mock_transcribe), \
             patch("beyin.cli.chunk_text", return_value=["chunk1"]), \
             patch("beyin.cli.embed_and_store", return_value=1), \
             patch("beyin.cli.is_audio_step_done", return_value=False), \
             patch("beyin.cli.get_audio_step", return_value={}), \
             patch("beyin.cli.mark_audio_step"), \
             patch("beyin.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack", "--language", "tr"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        mock_transcribe.assert_called_once()
        _, kwargs = mock_transcribe.call_args
        assert kwargs.get("language") == "tr", f"Expected language='tr', got: {mock_transcribe.call_args}"

    def test_build_article_source_unchanged(self, tmp_path):
        """Article source still calls fetch_article; transcribe_audio NOT called."""
        from beyin.cli import app
        packs_root = tmp_path / "beyin"
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

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="article"), \
             patch("beyin.cli.is_processed", return_value=False), \
             patch("beyin.cli.resolve_article_ingestion", return_value={"mode": "article", "text": "Article text", "title": "Article Title", "metadata_url": "https://example.com/article"}), \
             patch("beyin.cli.transcribe_audio", mock_transcribe), \
             patch("beyin.cli.chunk_text", return_value=["chunk1"]), \
             patch("beyin.cli.embed_and_store", return_value=1), \
             patch("beyin.cli.mark_processed"), \
             patch("beyin.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
        mock_transcribe.assert_not_called()

    def test_build_article_source_can_fallback_to_podcast_audio(self, tmp_path):
        """Article-like episode pages should download/transcribe direct audio instead of indexing landing-page text."""
        from beyin.cli import app

        packs_root = tmp_path / "beyin"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
            "  - https://example.com/episode\nembedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        mock_config = _make_config([SourceEntry(url="https://example.com/episode")])
        audio_file = tmp_path / "episode.mp3"
        audio_file.write_bytes(b"x" * 20_000)
        segments = [{"start": 0.0, "end": 10.0, "text": "Podcast content here"}]

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.check_transcription_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="article"), \
             patch("beyin.cli.is_processed", return_value=False), \
             patch("beyin.cli.resolve_article_ingestion", return_value={"mode": "podcast_audio", "audio_url": "https://cdn.example.com/episode.mp3", "title": "Episode 1", "metadata_url": "https://example.com/episode"}), \
             patch("beyin.cli._check_ffmpeg_available", return_value=True), \
             patch("beyin.cli.download_podcast_audio", return_value=audio_file) as mock_download, \
             patch("beyin.cli.transcribe_audio", return_value=segments) as mock_transcribe, \
             patch("beyin.cli.embed_and_store", return_value=1) as mock_embed, \
             patch("beyin.cli.mark_audio_step"), \
             patch("beyin.cli.mark_failed"):
            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 0, result.output
        mock_download.assert_called_once()
        mock_transcribe.assert_called_once()
        mock_embed.assert_called_once()

    def test_build_article_source_rejects_podcast_page_without_transcript_or_audio(self, tmp_path):
        """Podcast-like article pages should fail instead of indexing shallow landing-page show notes."""
        from beyin.cli import app

        packs_root = tmp_path / "beyin"
        pack_dir = packs_root / "test-pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.yaml").write_text(
            "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
            "  - https://example.com/episode\nembedding_model: all-MiniLM-L6-v2\n"
        )

        runner = CliRunner()
        mock_config = _make_config([SourceEntry(url="https://example.com/episode")])

        with patch("beyin.cli._PACKS_DIR", packs_root), \
             patch("beyin.cli.load_config", return_value=mock_config), \
             patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
             patch("beyin.cli.check_model_provenance"), \
             patch("beyin.cli.save_state"), \
             patch("beyin.cli.load_model", return_value=MagicMock()), \
             patch("beyin.cli.get_collection", return_value=MagicMock()), \
             patch("beyin.cli.detect_source_type", return_value="article"), \
             patch("beyin.cli.is_processed", return_value=False), \
             patch("beyin.cli.resolve_article_ingestion", return_value={"mode": "podcast_unresolved", "title": "Episode 1", "reason": "no transcript or audio found for podcast episode page: https://example.com/episode"}), \
             patch("beyin.cli.embed_and_store") as mock_embed, \
             patch("beyin.cli.mark_processed") as mock_mark, \
             patch("beyin.cli.mark_failed") as mock_fail:
            result = runner.invoke(app, ["build", "test-pack"])

        assert result.exit_code == 1, result.output
        mock_embed.assert_not_called()
        mock_mark.assert_not_called()
        mock_fail.assert_called_once()
        assert "no transcript or audio found" in result.output.lower()

    def test_build_help_shows_model_and_language_flags(self):
        """build --help shows --model and --language options."""
        from beyin.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.output
        assert "--language" in result.output


# ---------------------------------------------------------------------------
# Progress reporting tests (TDD RED phase)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False)
def test_build_transcribe_counter(tmp_path):
    """build shows '[transcribe] Episode N/Total: title' for each episode."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "testpack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: testpack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://youtube.com/watch?v=abc\n"
    )

    # Create a dummy audio file large enough to pass the size check
    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"x" * 11_000)

    episodes = [
        {"url": "https://youtube.com/watch?v=1", "title": "Ep 1", "id": "1"},
        {"url": "https://youtube.com/watch?v=2", "title": "Ep 2", "id": "2"},
        {"url": "https://youtube.com/watch?v=3", "title": "Ep 3", "id": "3"},
    ]
    mock_config = _make_config([SourceEntry(url="https://youtube.com/watch?v=abc")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="youtube"), \
         patch("beyin.cli.check_deno_available", return_value=True), \
         patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)), \
         patch("beyin.cli.is_audio_step_done", return_value=False), \
         patch("beyin.cli.get_audio_step", return_value={}), \
         patch("beyin.cli.download_audio", return_value=audio_file), \
         patch("beyin.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]), \
         patch("beyin.cli.embed_and_store", return_value=5), \
         patch("beyin.cli.mark_audio_step"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.check_model_provenance"):
        result = runner.invoke(app, ["build", "testpack"])

    assert "[transcribe] Episode 1/3:" in result.output
    assert "[transcribe] Episode 2/3:" in result.output
    assert "[transcribe] Episode 3/3:" in result.output


@pytest.mark.xfail(strict=False)
def test_build_embed_label(tmp_path):
    """build shows '[embed] title - N chunks' after embed_and_store call."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "testpack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: testpack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://youtube.com/watch?v=abc\n"
    )

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"x" * 11_000)

    episodes = [
        {"url": "https://youtube.com/watch?v=1", "title": "Ep 1", "id": "1"},
    ]
    mock_config = _make_config([SourceEntry(url="https://youtube.com/watch?v=abc")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="youtube"), \
         patch("beyin.cli.check_deno_available", return_value=True), \
         patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)), \
         patch("beyin.cli.is_audio_step_done", return_value=False), \
         patch("beyin.cli.get_audio_step", return_value={}), \
         patch("beyin.cli.download_audio", return_value=audio_file), \
         patch("beyin.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]), \
         patch("beyin.cli.embed_and_store", return_value=5), \
         patch("beyin.cli.mark_audio_step"), \
         patch("beyin.cli.check_model_provenance"):
        result = runner.invoke(app, ["build", "testpack"])

    assert "[embed]" in result.output
    assert "5 chunks" in result.output


@pytest.mark.xfail(strict=False)
def test_build_final_summary_table(tmp_path):
    """build prints a summary table with Source/Status/Chunks columns when new chunks processed."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "testpack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: testpack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://youtube.com/watch?v=abc\n"
    )

    audio_file = tmp_path / "audio.mp3"
    audio_file.write_bytes(b"x" * 11_000)

    episodes = [
        {"url": "https://youtube.com/watch?v=1", "title": "Ep 1", "id": "1"},
    ]
    mock_config = _make_config([SourceEntry(url="https://youtube.com/watch?v=abc")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="youtube"), \
         patch("beyin.cli.check_deno_available", return_value=True), \
         patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)), \
         patch("beyin.cli.is_audio_step_done", return_value=False), \
         patch("beyin.cli.get_audio_step", return_value={}), \
         patch("beyin.cli.download_audio", return_value=audio_file), \
         patch("beyin.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]), \
         patch("beyin.cli.embed_and_store", return_value=3), \
         patch("beyin.cli.mark_audio_step"), \
         patch("beyin.cli.check_model_provenance"):
        result = runner.invoke(app, ["build", "testpack"])

    output = result.output
    # Check for table header columns
    assert "Source" in output or "Status" in output or "Chunks" in output or "New" in output


@pytest.mark.xfail(strict=False)
def test_build_all_up_to_date(tmp_path):
    """build prints '0 new chunks -- all sources up to date' when all episodes already embedded."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "testpack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: testpack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://youtube.com/watch?v=abc\n"
    )

    episodes = [
        {"url": "https://youtube.com/watch?v=1", "title": "Ep 1", "id": "1"},
        {"url": "https://youtube.com/watch?v=2", "title": "Ep 2", "id": "2"},
    ]
    mock_config = _make_config([SourceEntry(url="https://youtube.com/watch?v=abc")])

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("beyin.cli.check_model_provenance"), \
         patch("beyin.cli.save_state"), \
         patch("beyin.cli.load_model", return_value=MagicMock()), \
         patch("beyin.cli.get_collection", return_value=MagicMock()), \
         patch("beyin.cli.detect_source_type", return_value="youtube"), \
         patch("beyin.cli.check_deno_available", return_value=True), \
         patch("beyin.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)), \
         patch("beyin.cli.is_audio_step_done", return_value=True), \
         patch("beyin.cli.get_audio_step", return_value={}), \
         patch("beyin.cli.embed_and_store", return_value=0), \
         patch("beyin.cli.mark_audio_step"), \
         patch("beyin.cli.check_model_provenance"):
        result = runner.invoke(app, ["build", "testpack"])

    assert "0 new chunks" in result.output
    assert "up to date" in result.output
