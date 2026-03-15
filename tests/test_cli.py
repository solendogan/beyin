"""Tests for cli.py — covers CLI-01, CLI-02."""
import importlib
import json
import sys
import pytest
import yaml
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock, call

from brainpack.config import SourceEntry, load_config


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


def _make_config(
    sources,
    embedding_model="all-MiniLM-L6-v2",
    episode_limit=20,
    llm="ollama",
):
    """Helper to build a mock PackConfig with SourceEntry objects."""
    cfg = MagicMock()
    cfg.sources = sources
    cfg.embedding_model = embedding_model
    cfg.name = "test-pack"
    cfg.episode_limit = episode_limit
    cfg.llm = llm
    return cfg


def _mark_pack_ready(pack_dir: Path, *, last_build_at: str = "2026-03-13T10:00:00+00:00"):
    """Persist the minimal ready state needed for query/chat command tests."""
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


def _mark_pack_needs_build(
    pack_dir: Path,
    *,
    last_build_at: str = "2026-03-13T10:00:00+00:00",
):
    """Persist a stale build state so lifecycle tests hit needs-build paths."""
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


def _mark_pack_failed(pack_dir: Path):
    """Persist a failed build state so lifecycle tests hit error paths."""
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


def test_help_frames_agent_and_local_modes():
    """brainpack --help should frame the product around agent and local-model use."""
    from brainpack.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "agent" in result.output.lower()
    assert "local model" in result.output.lower()
    assert "build" in result.output
    assert "query" in result.output


def test_help_command_alias_shows_top_level_framing():
    """brainpack help should preserve the same top-level onboarding framing."""
    from brainpack.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["help"])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "agent" in result.output.lower()
    assert "local model" in result.output.lower()


def test_local_mode_command_help_and_agent_server_help_use_new_positioning():
    """Command help should position query/chat as local mode and mcp-server for agents."""
    from brainpack.cli import app

    runner = CliRunner()

    query_help = runner.invoke(app, ["query", "--help"])
    chat_help = runner.invoke(app, ["chat", "--help"])
    mcp_help = runner.invoke(app, ["mcp-server", "--help"])

    assert query_help.exit_code == 0
    assert "local mode" in query_help.output.lower()
    assert chat_help.exit_code == 0
    assert "local mode" in chat_help.output.lower()
    assert mcp_help.exit_code == 0
    assert "agent" in mcp_help.output.lower()
    assert "stdio" in mcp_help.output.lower()


def test_no_arg_home_screen_guides_first_run(tmp_path):
    """No-arg invocation on a fresh machine shows a guided home screen."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Brainpack v0.1.0" in result.output
    assert "No packs installed yet." in result.output
    assert "Use with agent" in result.output
    assert "recommended" in result.output.lower()
    assert "brainpack finds evidence" in result.output
    assert "brainpack mcp-server" in result.output
    assert "Codex" in result.output
    assert "connect agent" in result.output.lower()
    assert "set up pack" in result.output.lower()
    assert "build" in result.output.lower()
    assert "Use with local model" in result.output
    assert "install local runtime" in result.output.lower()
    assert "brainpack doctor" in result.output
    assert "brainpack create" in result.output
    assert "brainpack add <path-or-url-or-id>" in result.output
    assert "brainpack build <pack>" in result.output


def test_no_arg_home_screen_orients_around_existing_inventory(tmp_pack_root):
    """No-arg invocation with installed packs keeps onboarding ahead of local shortcuts."""
    from brainpack.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Installed packs" in result.output
    assert "Pack" in result.output
    assert "Status" in result.output
    assert "Type" in result.output
    assert "test-pack" in result.output
    assert "needs-build" in result.output
    assert "Use with agent" in result.output
    assert "Use with local model" in result.output
    assert "brainpack mcp-server" in result.output
    assert "brainpack chat test-pack \"question\"" in result.output
    assert "brainpack status test-pack" in result.output
    assert result.output.index("Use with agent") < result.output.index('brainpack chat test-pack "question"')
    assert "next:" not in result.output


def test_no_arg_home_screen_is_not_plain_help_text(tmp_pack_root):
    """No-arg invocation renders product copy instead of the default help screen."""
    from brainpack.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True):
        home_result = runner.invoke(app, [])

    help_result = runner.invoke(app, ["--help"])

    assert home_result.exit_code == 0
    assert help_result.exit_code == 0
    assert "Usage:" not in home_result.output
    assert "Commands:" not in home_result.output
    assert "Turn your favorite content into local queryable packs." in home_result.output
    assert home_result.output != help_result.output


def test_no_arg_tty_first_run_routes_to_the_setup_seam_before_home_screen():
    """No-subcommand first-run setup is only considered on the interactive TTY path."""
    from brainpack.cli import app

    runner = CliRunner()

    with patch("brainpack.cli.needs_initial_setup", return_value=True) as needs_mock, patch(
        "brainpack.cli.is_interactive_session",
        return_value=True,
    ) as tty_mock, patch(
        "brainpack.cli._run_initial_setup_flow",
        return_value=True,
    ) as setup_mock, patch(
        "brainpack.cli._render_home_screen"
    ) as home_mock:
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    needs_mock.assert_called_once_with()
    tty_mock.assert_called_once_with()
    setup_mock.assert_called_once_with()
    home_mock.assert_not_called()


def test_no_arg_non_tty_first_run_falls_back_to_current_home_screen():
    """Fresh non-TTY runs should not try to prompt and should keep the current guidance."""
    from brainpack.cli import app

    runner = CliRunner()

    with patch("brainpack.cli.needs_initial_setup", return_value=True), patch(
        "brainpack.cli.is_interactive_session",
        return_value=False,
    ) as tty_mock, patch(
        "brainpack.cli._run_initial_setup_flow"
    ) as setup_mock, patch(
        "brainpack.cli._render_home_screen"
    ) as home_mock:
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    tty_mock.assert_called_once_with()
    setup_mock.assert_not_called()
    home_mock.assert_called_once_with()


def test_explicit_subcommands_skip_the_initial_setup_gate(tmp_path):
    """Explicit commands stay scriptable and do not consult the first-run setup gate."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli.needs_initial_setup",
        side_effect=AssertionError("setup gate should not run"),
    ), patch(
        "brainpack.cli.is_interactive_session",
        side_effect=AssertionError("TTY detection should not run"),
    ):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "No packs installed." in result.output


def test_plain_module_import_does_not_import_inquirerpy():
    """Interactive dependencies should stay unloaded on normal module import."""
    removed = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "InquirerPy" or name.startswith("InquirerPy.")
    }

    try:
        module = importlib.import_module("brainpack.interactive")
        importlib.reload(module)
        assert not any(
            name == "InquirerPy" or name.startswith("InquirerPy.")
            for name in sys.modules
        )
    finally:
        sys.modules.update(removed)


@pytest.mark.parametrize("exc_type", [KeyboardInterrupt, EOFError])
def test_interactive_abort_normalizes_cancellation(exc_type):
    """Interactive cancellation should collapse into one reusable abort type."""
    from brainpack.interactive import InteractiveAbort, normalize_prompt_abort

    def _raise_abort():
        raise exc_type()

    with pytest.raises(InteractiveAbort):
        normalize_prompt_abort(_raise_abort)


def test_create_wizard_asks_source_type_first(tmp_path):
    """create begins by asking the user which source family they want to use."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    prompts = []
    answers = iter(
        [
            "article",
            "guided-pack",
            "Guided pack",
            "https://example.com/article",
        ]
    )

    def fake_prompt(text, **kwargs):
        prompts.append(text)
        return next(answers)

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.typer.prompt", side_effect=fake_prompt):
        result = runner.invoke(app, ["create"])

    assert result.exit_code == 0
    assert prompts
    assert prompts[0] == "Source type (article/youtube/podcast)"


def test_create_wizard_writes_canonical_pack_yaml(tmp_path):
    """create writes canonical pack.yaml into the managed pack directory."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    answers = iter(
        [
            "youtube",
            "creator-pack",
            "Creator notes",
            "https://youtube.com/@creator",
        ]
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.typer.prompt", side_effect=lambda text, **kwargs: next(answers)):
        result = runner.invoke(app, ["create"])

    assert result.exit_code == 0

    pack_dir = packs_root / "creator-pack"
    raw = yaml.safe_load((pack_dir / "pack.yaml").read_text())
    config = load_config(pack_dir)

    assert raw == {
        "name": "creator-pack",
        "description": "Creator notes",
        "llm": "ollama",
        "embedding_model": "all-MiniLM-L6-v2",
        "whisper_model": "small",
        "episode_limit": 20,
        "sources": [{"url": "https://youtube.com/@creator"}],
    }
    assert config.name == "creator-pack"
    assert config.sources == [SourceEntry(url="https://youtube.com/@creator")]


def test_create_wizard_handles_one_source_family_and_ends_with_build_guidance(tmp_path):
    """create writes one source family per run and points the user to build next."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    answers = iter(
        [
            "podcast",
            "pod-pack",
            "Podcast notes",
            "https://example.com/feed.xml",
        ]
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.typer.prompt", side_effect=lambda text, **kwargs: next(answers)):
        result = runner.invoke(app, ["create"])

    assert result.exit_code == 0

    config = load_config(packs_root / "pod-pack")

    assert [source.url for source in config.sources] == ["https://example.com/feed.xml"]
    assert "One source family per pack keeps the first run simple." in result.output
    assert "Next step: brainpack build pod-pack" in result.output
    assert result.output.count("Next step:") == 1
    assert "pack.yaml" not in result.output


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
    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
    _mark_pack_ready(pack_dir)

    mock_result = {
        "answer": "Test answer here",
        "sources": [{"url": "https://example.com", "title": "Example Article"}],
    }

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", return_value=mock_result):

        result = runner.invoke(app, ["query", "test-pack", "What is this?"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"
    assert "Test answer here" in result.output


def test_query_prints_sources_section(tmp_pack_root):
    """query prints a Sources: section with URL and title per citation."""
    from brainpack.cli import app
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", return_value=mock_result):

        result = runner.invoke(app, ["query", "test-pack", "What?"])

    assert "Sources:" in result.output
    assert "Article A" in result.output
    assert "https://example.com/a" in result.output
    assert "Article B" in result.output
    assert "https://example.com/b" in result.output


def test_query_compacts_duplicate_video_sources_by_title_and_url(tmp_pack_root):
    """query groups repeated timestamp hits from the same video into one compact source entry."""
    from brainpack.cli import app
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", return_value=mock_result):
        result = runner.invoke(app, ["query", "test-pack", "What?"])

    assert result.exit_code == 0
    assert result.output.count("Episode 123") == 1
    assert "00:12-00:34" in result.output
    assert "00:40-00:52" in result.output


def test_query_openai_pack_does_not_require_ollama(tmp_pack_root):
    """OpenAI packs load config first and skip Ollama-specific readiness checks."""
    from brainpack.cli import app
    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
    _mark_pack_ready(pack_dir)

    mock_result = {"answer": "OpenAI answer", "sources": []}
    mock_config = _make_config(
        [SourceEntry(url="https://example.com/article")],
        llm="openai",
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli._check_ollama_reachable", return_value=False), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", return_value=mock_result) as mock_run_query:

        result = runner.invoke(app, ["query", "test-pack", "What is this?"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"
    mock_run_query.assert_called_once()
    assert "OpenAI answer" in result.output


def test_query_openai_without_api_key_fails_cleanly(tmp_pack_root):
    """OpenAI packs fail on OpenAI readiness, not on unrelated Ollama checks."""
    from brainpack.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    mock_config = _make_config(
        [SourceEntry(url="https://example.com/article")],
        llm="openai",
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli._check_ollama_reachable", return_value=False), \
         patch.dict("os.environ", {}, clear=True):

        result = runner.invoke(app, ["query", "test-pack", "What is this?"])

    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.output
    assert "Ollama" not in result.output


def test_query_anthropic_pack_fails_cleanly(tmp_pack_root):
    """Anthropic packs exit cleanly as unsupported in this phase."""
    from brainpack.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    mock_config = _make_config(
        [SourceEntry(url="https://example.com/article")],
        llm="anthropic",
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.run_query") as mock_run_query:

        result = runner.invoke(app, ["query", "test-pack", "What is this?"])

    assert result.exit_code == 1
    assert "Anthropic" in result.output
    assert "not supported" in result.output
    mock_run_query.assert_not_called()


def test_query_prints_timestamp_ranges_in_sources(tmp_pack_root):
    """Query output surfaces timestamp ranges when the source metadata has them."""
    from brainpack.cli import app
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", return_value=mock_result):

        result = runner.invoke(app, ["query", "test-pack", "What happened?"])

    assert result.exit_code == 0
    assert "00:12-00:34" in result.output


def test_chat_one_shot_uses_existing_query_path_and_shows_sources(tmp_pack_root):
    """chat one-shot delegates through run_query and prints answer sources."""
    from brainpack.cli import app
    from brainpack.inventory import pack_config_hash
    from brainpack.pack_state import save_state

    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
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

    mock_result = {
        "answer": "One-shot answer",
        "sources": [{"url": "https://example.com/chat", "title": "Chat Source"}],
    }

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", return_value=mock_result) as mock_run_query:

        result = runner.invoke(app, ["chat", "test-pack", "What is new?"])

    assert result.exit_code == 0
    mock_run_query.assert_called_once()
    assert "One-shot answer" in result.output
    assert "Sources:" in result.output
    assert "Chat Source" in result.output
    assert "https://example.com/chat" in result.output


def test_chat_interactive_keeps_session_memory_only_for_current_process(tmp_pack_root):
    """Interactive chat reuses in-memory history during one run and starts fresh next run."""
    from brainpack.cli import app
    from brainpack.inventory import pack_config_hash
    from brainpack.pack_state import save_state

    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()
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

    first_session_calls = []

    def first_session_run_query(**kwargs):
        first_session_calls.append(kwargs)
        return {
            "answer": f"Answer {len(first_session_calls)}",
            "sources": [{"url": "https://example.com/chat", "title": "Chat Source"}],
        }

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", side_effect=first_session_run_query):
        first_result = runner.invoke(
            app,
            ["chat", "test-pack"],
            input="First question?\nSecond question?\nexit\n",
        )

    assert first_result.exit_code == 0
    assert len(first_session_calls) == 2
    assert first_session_calls[0].get("history") in (None, [])
    assert first_session_calls[1]["history"] == [
        {"question": "First question?", "answer": "Answer 1"}
    ]
    assert first_result.output.count("Sources:") == 2

    second_session_calls = []

    def second_session_run_query(**kwargs):
        second_session_calls.append(kwargs)
        return {
            "answer": "Fresh session answer",
            "sources": [{"url": "https://example.com/chat", "title": "Chat Source"}],
        }

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.run_query", side_effect=second_session_run_query):
        second_result = runner.invoke(app, ["chat", "test-pack"], input="Fresh question?\nquit\n")

    assert second_result.exit_code == 0
    assert len(second_session_calls) == 1
    assert second_session_calls[0].get("history") in (None, [])


def test_chat_missing_pack_redirects_to_create_or_add(tmp_path):
    """Missing-pack chat should redirect to an actionable onboarding command."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["chat", "missing-pack", "Where do I start?"])

    assert result.exit_code == 1
    assert "missing-pack" in result.output
    assert "Next step: brainpack create" in result.output
    assert "brainpack add <path-or-url-or-id>" in result.output
    assert "mkdir -p" not in result.output


def test_chat_unbuilt_pack_redirects_to_build(tmp_pack_root):
    """Unbuilt-pack chat should reuse onboarding guidance instead of a raw next-step line."""
    from brainpack.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model") as mock_load_model, \
         patch("brainpack.cli.get_collection") as mock_get_collection, \
         patch("brainpack.cli.run_query") as mock_run_query:
        result = runner.invoke(app, ["chat", "test-pack", "Can I ask now?"])

    assert result.exit_code == 1
    assert "not built" in result.output.lower() or "build" in result.output.lower()
    assert "Use with agent" in result.output
    assert "Use with local model" in result.output
    assert "brainpack mcp-server" in result.output
    assert "brainpack build test-pack" in result.output
    assert "Next step:" not in result.output
    mock_load_model.assert_not_called()
    mock_get_collection.assert_not_called()
    mock_run_query.assert_not_called()


def test_chat_blocked_pack_redirects_to_doctor(tmp_pack_root):
    """Blocked-pack chat should reuse onboarding guidance instead of stale chat-first copy."""
    from brainpack.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=False), \
         patch("brainpack.cli.shutil.which", return_value="/usr/local/bin/ollama"), \
         patch("brainpack.cli.load_model") as mock_load_model, \
         patch("brainpack.cli.get_collection") as mock_get_collection, \
         patch("brainpack.cli.run_query") as mock_run_query:
        result = runner.invoke(app, ["chat", "test-pack", "Can I ask now?"])

    assert result.exit_code == 1
    assert "blocked" in result.output.lower()
    assert "Use with agent" in result.output
    assert "Use with local model" in result.output
    assert "brainpack mcp-server" in result.output
    assert "brainpack doctor test-pack" in result.output
    assert "try chat again" not in result.output
    assert "Next step:" not in result.output
    mock_load_model.assert_not_called()
    mock_get_collection.assert_not_called()
    mock_run_query.assert_not_called()


def test_query_unbuilt_pack_redirects_to_build(tmp_pack_root):
    """Unbuilt-pack query should reuse onboarding guidance instead of a raw next-step line."""
    from brainpack.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model") as mock_load_model, \
         patch("brainpack.cli.get_collection") as mock_get_collection, \
         patch("brainpack.cli.run_query") as mock_run_query:
        result = runner.invoke(app, ["query", "test-pack", "Can I ask now?"])

    assert result.exit_code == 1
    assert "not built" in result.output.lower() or "build" in result.output.lower()
    assert "Use with agent" in result.output
    assert "Use with local model" in result.output
    assert "brainpack mcp-server" in result.output
    assert "brainpack build test-pack" in result.output
    assert "Next step:" not in result.output
    mock_load_model.assert_not_called()
    mock_get_collection.assert_not_called()
    mock_run_query.assert_not_called()


@pytest.mark.parametrize(
    ("command", "status_setup", "expected_command"),
    [
        ("query", "needs-build", "brainpack build test-pack"),
        ("query", "error", "brainpack build test-pack"),
        ("chat", "needs-build", "brainpack build test-pack"),
        ("chat", "error", "brainpack build test-pack"),
    ],
)
def test_retrieval_preconditions_share_onboarding_guidance(
    tmp_pack_root,
    command,
    status_setup,
    expected_command,
):
    """Human query/chat preconditions should render the shared onboarding guidance seam."""
    from brainpack.cli import app

    packs_root, pack_dir = tmp_pack_root
    runner = CliRunner()

    if status_setup == "needs-build":
        _mark_pack_needs_build(pack_dir)
    elif status_setup == "error":
        _mark_pack_failed(pack_dir)

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True), \
         patch("brainpack.cli.load_model") as mock_load_model, \
         patch("brainpack.cli.get_collection") as mock_get_collection, \
         patch("brainpack.cli.run_query") as mock_run_query:
        result = runner.invoke(app, [command, "test-pack", "Can I ask now?"])

    assert result.exit_code == 1
    assert "Use with agent" in result.output
    assert "Use with local model" in result.output
    assert "brainpack mcp-server" in result.output
    assert expected_command in result.output
    assert "Next step:" not in result.output
    mock_load_model.assert_not_called()
    mock_get_collection.assert_not_called()
    mock_run_query.assert_not_called()


def test_build_persists_structured_transcripts_with_timestamps(tmp_path):
    """Fresh audio transcripts persist structured segments and chunk timestamp metadata."""
    from brainpack.cli import app
    from brainpack.source_ids import artifact_stem, canonical_source_id

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="youtube"), \
         patch("brainpack.cli.list_youtube_episodes", return_value=[episode]), \
         patch("brainpack.cli._check_ffmpeg_available", return_value=True), \
         patch("brainpack.cli._youtube_build_issue", return_value=None), \
         patch("brainpack.cli.download_audio", return_value=audio_path), \
         patch("brainpack.cli.transcribe_audio", return_value=segments), \
         patch("brainpack.cli.embed_and_store", side_effect=_capture_embed):

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
    from brainpack.cli import app
    from brainpack.pack_state import save_state
    from brainpack.source_ids import artifact_stem, canonical_source_id

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="youtube"), \
         patch("brainpack.cli.list_youtube_episodes", return_value=[episode]), \
         patch("brainpack.cli._check_ffmpeg_available", return_value=True), \
         patch("brainpack.cli._youtube_build_issue", return_value=None), \
         patch("brainpack.cli.download_audio") as mock_download, \
         patch("brainpack.cli.transcribe_audio") as mock_transcribe, \
         patch("brainpack.cli.embed_and_store", side_effect=_capture_embed):

        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
    mock_download.assert_not_called()
    mock_transcribe.assert_not_called()
    assert captured["metadatas"][0]["timestamp_start"] == 12.0
    assert captured["metadatas"][0]["timestamp_end"] == 21.0


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
        assert "[embed]" in result.output
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


# ---------------------------------------------------------------------------
# SAF-02: Ollama guard tests (Task 1 — RED phase)
# ---------------------------------------------------------------------------

def test_query_ollama_not_running():
    """query exits 1 with 'Ollama is not running' and 'ollama serve' when port closed but binary present."""
    from brainpack.cli import app
    runner = CliRunner()
    mock_config = _make_config([SourceEntry(url="https://example.com/article")], llm="ollama")

    with patch("brainpack.cli._resolve_pack_dir", return_value=Path("/tmp/mypack")), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli._check_ollama_reachable", return_value=False), \
         patch("brainpack.cli.shutil") as mock_shutil:
        mock_shutil.which.return_value = "/usr/local/bin/ollama"
        result = runner.invoke(app, ["query", "mypack", "test"])

    assert result.exit_code == 1
    output = result.output
    assert "Ollama is not running" in output
    assert "ollama serve" in output


def test_query_ollama_not_installed():
    """query exits 1 with install guide when ollama binary absent."""
    from brainpack.cli import app
    runner = CliRunner()
    mock_config = _make_config([SourceEntry(url="https://example.com/article")], llm="ollama")

    with patch("brainpack.cli._resolve_pack_dir", return_value=Path("/tmp/mypack")), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli._check_ollama_reachable", return_value=False), \
         patch("brainpack.cli.shutil") as mock_shutil:
        mock_shutil.which.return_value = None
        result = runner.invoke(app, ["query", "mypack", "test"])

    assert result.exit_code == 1
    output = result.output
    assert "not installed" in output.lower() or "Ollama is not installed" in output
    # Should contain an install guide (brew or curl)
    assert "brew install ollama" in output or "curl" in output


# ---------------------------------------------------------------------------
# CLI-05 + SAF-03: check-deps tests
# ---------------------------------------------------------------------------

def test_check_deps_all_pass():
    """check-deps exits 0 when ffmpeg and yt-dlp both pass."""
    from brainpack.cli import app
    runner = CliRunner()

    with patch("brainpack.cli.shutil") as mock_shutil, \
         patch("brainpack.cli._ytdlp_version_ok", return_value=(True, "2026.03.03")):
        mock_shutil.which.side_effect = lambda name: {
            "ffmpeg": "/usr/bin/ffmpeg",
        }.get(name)
        result = runner.invoke(app, ["check-deps"])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"


def test_check_deps_does_not_surface_deno():
    """check-deps no longer reports Deno as a user-facing dependency."""
    from brainpack.cli import app
    runner = CliRunner()

    with patch("brainpack.cli.shutil") as mock_shutil, \
         patch("brainpack.cli._ytdlp_version_ok", return_value=(True, "2026.03.03")):
        mock_shutil.which.side_effect = lambda name: {
            "ffmpeg": "/usr/bin/ffmpeg",
        }.get(name)
        result = runner.invoke(app, ["check-deps"])

    assert result.exit_code == 0
    assert "Deno" not in result.output
    assert "deno" not in result.output.lower()


def test_check_deps_ytdlp_outdated():
    """check-deps exits 1 with OUTDATED + upgrade command when yt-dlp is below min version."""
    from brainpack.cli import app
    runner = CliRunner()

    with patch("brainpack.cli.shutil") as mock_shutil, \
         patch("brainpack.cli._ytdlp_version_ok", return_value=(False, "2025.10.01")):
        mock_shutil.which.side_effect = lambda name: {
            "ffmpeg": "/usr/bin/ffmpeg",
        }.get(name)
        result = runner.invoke(app, ["check-deps"])

    assert result.exit_code == 1
    output = result.output
    assert "outdated" in output.lower() or "OUTDATED" in output
    assert "pip install --upgrade yt-dlp" in output


def test_check_deps_ffmpeg_missing():
    """check-deps exits 1 with ffmpeg install instruction when ffmpeg not found."""
    from brainpack.cli import app
    runner = CliRunner()

    with patch("brainpack.cli.shutil") as mock_shutil, \
         patch("brainpack.cli._ytdlp_version_ok", return_value=(True, "2026.03.03")):
        mock_shutil.which.side_effect = lambda name: {
            "ffmpeg": None,
        }.get(name)
        result = runner.invoke(app, ["check-deps"])

    assert result.exit_code == 1
    output = result.output
    assert "ffmpeg" in output.lower()
    # Should include install instruction
    assert "brew install ffmpeg" in output or "ffmpeg.org" in output


def test_doctor_reports_openai_query_readiness(tmp_pack_root):
    """doctor reports query readiness using the selected pack provider."""
    from brainpack.cli import app
    packs_root, _ = tmp_pack_root
    runner = CliRunner()
    mock_config = _make_config(
        [SourceEntry(url="https://example.com/article")],
        llm="openai",
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
        result = runner.invoke(app, ["doctor", "test-pack", "--operation", "query"])

    assert result.exit_code == 0
    assert "Query readiness: ready" in result.output
    assert "provider=openai" in result.output
    assert "Ollama" not in result.output


def test_build_youtube_source_fails_when_ytdlp_unavailable(tmp_path):
    """YouTube builds fail cleanly when yt-dlp is missing or outdated."""
    from brainpack.cli import app
    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli._youtube_build_issue", return_value="yt-dlp is not installed. Install or upgrade with: pip install --upgrade yt-dlp"), \
         patch("brainpack.cli._check_ffmpeg_available", return_value=True), \
         patch("brainpack.cli.list_youtube_episodes") as mock_list:
        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 1
    assert "yt-dlp is not installed" in result.output
    mock_list.assert_not_called()


def test_build_mixed_pack_keeps_articles_when_audio_is_blocked(tmp_path):
    """Mixed packs still build article sources when audio work is blocked by ffmpeg."""
    from brainpack.cli import app
    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", side_effect=["article", "youtube"]), \
         patch("brainpack.cli.fetch_article", return_value=("Article text", "Article Title")), \
         patch("brainpack.cli.chunk_text", return_value=["chunk one"]), \
         patch("brainpack.cli.embed_and_store", return_value=1), \
         patch("brainpack.cli._check_ffmpeg_available", return_value=False), \
         patch("brainpack.cli._youtube_build_issue", return_value=None):
        result = runner.invoke(app, ["build", "test-pack"])

    assert result.exit_code == 1
    assert "[embed] Article Title" in result.output
    assert "blocked" in result.output
    assert "ffmpeg" in result.output.lower()


def test_inventory_summary_marks_new_pack_and_next_build(tmp_path):
    """Inventory summary marks unbuilt packs as new with a build next step."""
    from brainpack.inventory import summarize_pack

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
    assert summary["next_action"] == "brainpack build test-pack"


def test_inventory_summary_marks_blocked_pack(tmp_path):
    """Inventory summary promotes readiness blockers into the main blocked status."""
    from brainpack.inventory import summarize_pack

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
    assert summary["next_action"] == "brainpack doctor test-pack"


def test_add_local_pack_stores_origin_metadata(tmp_path):
    """add stores local-file provenance next to the installed pack."""
    from brainpack.cli import app
    from brainpack.inventory import load_pack_origin

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    yaml_file = tmp_path / "pack.yaml"
    yaml_file.write_text(
        "name: added-pack\n"
        "description: test\n"
        "llm: openai\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
        result = runner.invoke(app, ["add", str(yaml_file)])

    assert result.exit_code == 0, result.output
    origin = load_pack_origin(packs_root / "added-pack")
    assert origin["type"] == "file"
    assert origin["source"] == str(yaml_file.resolve())


def test_add_marketplace_id_uses_local_mapping(tmp_path):
    """add resolves marketplace-style ids through the local mapping file."""
    from brainpack.cli import app
    from brainpack.inventory import load_pack_origin, marketplace_mapping_path

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    packs_root.mkdir()
    yaml_file = tmp_path / "remote-pack.yaml"
    yaml_file.write_text(
        "name: mapped-pack\n"
        "description: mapped\n"
        "llm: openai\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )
    marketplace_mapping_path(packs_root).write_text(
        json.dumps({"starter-pack": str(yaml_file.resolve())})
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
        result = runner.invoke(app, ["add", "starter-pack"])

    assert result.exit_code == 0, result.output
    origin = load_pack_origin(packs_root / "mapped-pack")
    assert origin["type"] == "id"
    assert origin["source"] == "starter-pack"


def test_list_shows_compact_inventory_with_counts_and_ordering(tmp_path):
    """list shows compact alphabetical rows with status, type, source count, and provider."""
    from brainpack.cli import app
    from brainpack.inventory import save_pack_origin, pack_config_hash
    from brainpack.pack_state import save_state

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0, result.output
    rows = [line for line in result.output.splitlines() if line.startswith(("a-pack", "b-pack"))]
    assert rows[0].startswith("a-pack")
    assert rows[1].startswith("b-pack")
    assert "text" in rows[0]
    assert "openai" in rows[0]
    assert "      2" in rows[0]
    assert "Summary" not in result.output
    assert "Src" not in result.output


@pytest.mark.parametrize(
    ("pack_name", "state_setup", "env_vars", "expected_status", "expected_command"),
    [
        ("ready-pack", "ready", {"OPENAI_API_KEY": "sk-test"}, "ready", "brainpack mcp-server"),
        ("blocked-pack", "blocked", {}, "blocked", "brainpack doctor blocked-pack"),
        ("new-pack", "new", {"OPENAI_API_KEY": "sk-test"}, "needs-build", "brainpack build new-pack"),
        ("stale-pack", "needs-build", {"OPENAI_API_KEY": "sk-test"}, "needs-build", "brainpack build stale-pack"),
        ("error-pack", "error", {"OPENAI_API_KEY": "sk-test"}, "error", "brainpack build error-pack"),
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
    from brainpack.cli import app
    from brainpack.inventory import save_pack_origin

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / pack_name
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        f"name: {pack_name}\n"
        "description: test\n"
        "llm: openai\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )
    save_pack_origin(
        pack_dir,
        {"type": "file", "source": f"/tmp/{pack_name}.yaml", "added_at": "2026-03-13T09:00:00+00:00"},
    )

    if state_setup == "ready":
        _mark_pack_ready(pack_dir)
    elif state_setup == "needs-build":
        _mark_pack_needs_build(pack_dir)
    elif state_setup == "error":
        _mark_pack_failed(pack_dir)

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch.dict("os.environ", env_vars, clear=True), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True):
        result = runner.invoke(app, ["status", pack_name])

    assert result.exit_code == 0, result.output
    assert f"Status: {expected_status}" in result.output
    assert "Type: text" in result.output
    assert f"Origin: file: /tmp/{pack_name}.yaml" in result.output
    assert "Use with agent" in result.output
    assert "Use with local model" in result.output
    assert "brainpack mcp-server" in result.output
    assert expected_command in result.output
    assert "Next:" not in result.output
    if state_setup == "ready":
        assert result.output.index("Use with agent") < result.output.index(f'brainpack query {pack_name} "question"')
    if state_setup == "blocked":
        assert "OPENAI_API_KEY" in result.output


def test_update_uses_remembered_origin_and_shows_change_summary(tmp_path):
    """update reloads pack.yaml from the remembered origin and prints config changes."""
    from brainpack.cli import app
    from brainpack.inventory import load_pack_origin

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "sync-pack"
    pack_dir.mkdir(parents=True)
    source_yaml = tmp_path / "sync-pack.yaml"
    source_yaml.write_text(
        "name: sync-pack\n"
        "description: test\n"
        "llm: openai\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )
    (pack_dir / "pack.yaml").write_text(source_yaml.read_text())
    (pack_dir / "origin.json").write_text(
        json.dumps(
            {
                "type": "file",
                "source": str(source_yaml.resolve()),
                "resolved": str(source_yaml.resolve()),
                "added_at": "2026-03-13T09:00:00+00:00",
            }
        )
    )
    source_yaml.write_text(
        "name: sync-pack\n"
        "description: test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "  - https://example.com/new\n"
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "sync-pack"])

    assert result.exit_code == 0, result.output
    assert "Updating pack definition:" in result.output
    assert "provider: openai -> ollama" in result.output
    assert "sources: 1 -> 2" in result.output
    mock_build.assert_called_once()
    origin = load_pack_origin(pack_dir)
    assert "provider: openai -> ollama" in origin["last_update_summary"]


# ---------------------------------------------------------------------------
# PCK-02 + CLI-03: install command tests (TDD RED phase)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False)
def test_install_local_success(tmp_path):
    """install <local-path> copies pack.yaml to ~/.brainpacks/<name>/pack.yaml and exits 0."""
    from brainpack.cli import app
    runner = CliRunner()

    # Create a real pack.yaml
    yaml_file = tmp_path / "pack.yaml"
    yaml_file.write_text(
        "name: test-pack\n"
        "description: test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.shutil") as mock_shutil:
        mock_shutil.copy2 = MagicMock()
        result = runner.invoke(app, ["install", str(yaml_file)])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
    assert "test-pack" in result.output


@pytest.mark.xfail(strict=False)
def test_install_already_exists(tmp_path):
    """install exits 1 with 'already installed' and 'brainpack update' suggestion when dest exists."""
    from brainpack.cli import app
    runner = CliRunner()

    yaml_file = tmp_path / "pack.yaml"
    yaml_file.write_text(
        "name: test-pack\n"
        "description: test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )
    # Make the dest dir already exist
    packs_root = tmp_path / "brainpacks"
    dest_dir = packs_root / "test-pack"
    dest_dir.mkdir(parents=True)

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["install", str(yaml_file)])

    assert result.exit_code == 1
    assert "already installed" in result.output
    assert "brainpack update" in result.output


@pytest.mark.xfail(strict=False)
def test_install_remote_url(tmp_path):
    """install https://example.com/pack.yaml downloads, validates, and exits 0."""
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
    valid_yaml = (
        "name: remote-pack\n"
        "description: remote\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )

    def fake_urlretrieve(url, tmp_file):
        Path(tmp_file).write_text(valid_yaml)

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.urllib.request.urlretrieve", side_effect=fake_urlretrieve), \
         patch("brainpack.cli.shutil") as mock_shutil:
        mock_shutil.copy2 = MagicMock()
        result = runner.invoke(app, ["install", "https://example.com/pack.yaml"])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"


@pytest.mark.xfail(strict=False)
def test_install_file_not_found(tmp_path):
    """install exits 1 with 'not found' for a nonexistent local path."""
    from brainpack.cli import app
    runner = CliRunner()

    result = runner.invoke(app, ["install", "/nonexistent/path/pack.yaml"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# PCK-03 + CLI-04: update command tests (TDD RED phase)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False)
def test_update_existing_pack(tmp_path):
    """update <pack> delegates to build and exits 0 when pack dir exists."""
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "mypack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: mypack\ndescription: x\nllm: ollama\nsources:\n  - https://example.com\n"
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.build") as mock_build:
        mock_build.return_value = None
        result = runner.invoke(app, ["update", "mypack"])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
    mock_build.assert_called_once()


@pytest.mark.xfail(strict=False)
def test_update_pack_not_found(tmp_path):
    """update exits 1 with 'not found' and 'brainpack install' when pack dir missing."""
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
    # Do NOT create the pack dir

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["update", "nonexistent"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()
    assert "brainpack install" in result.output


# ---------------------------------------------------------------------------
# CLI-06: Progress reporting tests (TDD RED phase)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False)
def test_build_transcribe_counter(tmp_path):
    """build shows '[transcribe] Episode N/Total: title' for each episode."""
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="youtube"), \
         patch("brainpack.cli.check_deno_available", return_value=True), \
         patch("brainpack.cli.list_youtube_episodes", return_value=episodes), \
         patch("brainpack.cli.is_audio_step_done", return_value=False), \
         patch("brainpack.cli.get_audio_step", return_value={}), \
         patch("brainpack.cli.download_audio", return_value=audio_file), \
         patch("brainpack.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]), \
         patch("brainpack.cli.embed_and_store", return_value=5), \
         patch("brainpack.cli.mark_audio_step"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.check_model_provenance"):
        result = runner.invoke(app, ["build", "testpack"])

    assert "[transcribe] Episode 1/3:" in result.output
    assert "[transcribe] Episode 2/3:" in result.output
    assert "[transcribe] Episode 3/3:" in result.output


@pytest.mark.xfail(strict=False)
def test_build_embed_label(tmp_path):
    """build shows '[embed] title — N chunks' after embed_and_store call."""
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="youtube"), \
         patch("brainpack.cli.check_deno_available", return_value=True), \
         patch("brainpack.cli.list_youtube_episodes", return_value=episodes), \
         patch("brainpack.cli.is_audio_step_done", return_value=False), \
         patch("brainpack.cli.get_audio_step", return_value={}), \
         patch("brainpack.cli.download_audio", return_value=audio_file), \
         patch("brainpack.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]), \
         patch("brainpack.cli.embed_and_store", return_value=5), \
         patch("brainpack.cli.mark_audio_step"), \
         patch("brainpack.cli.check_model_provenance"):
        result = runner.invoke(app, ["build", "testpack"])

    assert "[embed]" in result.output
    assert "5 chunks" in result.output


@pytest.mark.xfail(strict=False)
def test_build_final_summary_table(tmp_path):
    """build prints a summary table with Source/Status/Chunks columns when new chunks processed."""
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="youtube"), \
         patch("brainpack.cli.check_deno_available", return_value=True), \
         patch("brainpack.cli.list_youtube_episodes", return_value=episodes), \
         patch("brainpack.cli.is_audio_step_done", return_value=False), \
         patch("brainpack.cli.get_audio_step", return_value={}), \
         patch("brainpack.cli.download_audio", return_value=audio_file), \
         patch("brainpack.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]), \
         patch("brainpack.cli.embed_and_store", return_value=3), \
         patch("brainpack.cli.mark_audio_step"), \
         patch("brainpack.cli.check_model_provenance"):
        result = runner.invoke(app, ["build", "testpack"])

    output = result.output
    # Check for table header columns
    assert "Source" in output or "Status" in output or "Chunks" in output or "New" in output


@pytest.mark.xfail(strict=False)
def test_build_all_up_to_date(tmp_path):
    """build prints '0 new chunks — all sources up to date' when all episodes already embedded."""
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="youtube"), \
         patch("brainpack.cli.check_deno_available", return_value=True), \
         patch("brainpack.cli.list_youtube_episodes", return_value=episodes), \
         patch("brainpack.cli.is_audio_step_done", return_value=True), \
         patch("brainpack.cli.get_audio_step", return_value={}), \
         patch("brainpack.cli.embed_and_store", return_value=0), \
         patch("brainpack.cli.mark_audio_step"), \
         patch("brainpack.cli.check_model_provenance"):
        result = runner.invoke(app, ["build", "testpack"])

    assert "0 new chunks" in result.output
    assert "up to date" in result.output
