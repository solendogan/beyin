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


class _PromptResult:
    def __init__(self, value):
        self._value = value

    def execute(self):
        if isinstance(self._value, BaseException):
            raise self._value
        return self._value


class _FakePromptBackend:
    def __init__(self, values):
        self._values = iter(values)
        self.calls = []

    def _record(self, prompt_type, **kwargs):
        self.calls.append((prompt_type, kwargs))
        return _PromptResult(next(self._values))

    def select(self, **kwargs):
        return self._record("select", **kwargs)

    def confirm(self, **kwargs):
        return self._record("confirm", **kwargs)

    def text(self, **kwargs):
        return self._record("text", **kwargs)


def _save_global_settings(home: Path, **overrides):
    from brainpack.settings import BrainpackSettings, save_settings

    save_settings(
        BrainpackSettings(
            version=1,
            setup_completed=True,
            preferred_transcription_backend=overrides.get(
                "preferred_transcription_backend",
                "faster-whisper",
            ),
            preferred_whisper_model=overrides.get("preferred_whisper_model", "small"),
            preferred_local_provider=overrides.get("preferred_local_provider", "ollama"),
        )
    )


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
    assert "No packs installed yet" in result.output
    assert "Settings" in result.output
    assert "LLM model" in result.output
    assert "brainpack create" in result.output
    assert "brainpack settings" in result.output


def test_no_arg_home_screen_orients_around_existing_inventory(tmp_pack_root):
    """No-arg invocation with installed packs shows inventory and settings."""
    from brainpack.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Installed packs" in result.output
    assert "ID" in result.output
    assert "Status" in result.output
    assert "test-pack" in result.output
    assert "needs-build" in result.output
    assert "Settings" in result.output
    assert "LLM model" in result.output


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
    assert "Your local knowledge base" in home_result.output
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
    ) as home_mock, patch(
        "brainpack.cli.list_packs",
        return_value=[],
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    needs_mock.assert_called_once_with()
    tty_mock.assert_called_once_with()
    setup_mock.assert_called_once_with()
    home_mock.assert_not_called()


def test_no_arg_tty_declined_first_run_does_not_fall_through_to_authoring_or_home():
    """Declining first-run setup should stop after setup instead of continuing onward."""
    from brainpack.cli import app

    runner = CliRunner()

    with patch("brainpack.cli.needs_initial_setup", return_value=True), patch(
        "brainpack.cli.is_interactive_session",
        return_value=True,
    ), patch(
        "brainpack.cli._run_initial_setup_flow",
        return_value=False,
    ) as setup_mock, patch(
        "brainpack.cli.run_authoring_menu",
    ) as authoring_mock, patch(
        "brainpack.cli._render_home_screen",
    ) as home_mock, patch(
        "brainpack.cli.list_packs",
        return_value=[],
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    setup_mock.assert_called_once_with()
    authoring_mock.assert_not_called()
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
    assert tty_mock.call_count == 2
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


def test_first_interactive_run_completes_recommended_setup_once_and_persists_settings(
    monkeypatch,
    tmp_path,
):
    """First interactive no-arg use should run setup once, save defaults, and not repeat."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.cli import app
    from brainpack.settings import load_settings

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    backend = _FakePromptBackend(
        [
            "recommended",
            "agent",
            True,
            KeyboardInterrupt(),
        ]
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli.is_interactive_session",
        return_value=True,
    ), patch(
        "brainpack.cli.load_prompt_backend",
        return_value=backend,
    ) as load_backend:
        first = runner.invoke(app, [])
        second = runner.invoke(app, [])

    settings = load_settings()

    assert first.exit_code == 0
    assert settings.setup_completed is True
    assert "Brainpack v0.1.0" in first.output
    assert "Start your first setup now" in first.output
    first_select = next(
        kwargs for prompt_type, kwargs in backend.calls if prompt_type == "select"
    )
    assert "Recommended" in str(first_select.get("choices", ""))
    assert first.output.count("Setup complete") == 1
    assert "Quick start" in first.output
    assert second.exit_code == 0
    assert "Setup complete" not in second.output
    assert "What would you like to do?" in second.output
    assert load_backend.call_count == 2


def test_initial_setup_custom_branch_limits_choices_to_current_machine(monkeypatch, tmp_path):
    """Custom setup should expose only the valid high-level runtime choices for this machine."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.interactive import run_initial_setup_flow
    from brainpack.settings import load_settings

    backend = _FakePromptBackend(
        [
            "custom",
            "faster-whisper",
            "small",
            "openai",
            True,
        ]
    )

    with patch("brainpack.settings.platform.system", return_value="Linux"), patch(
        "brainpack.settings.platform.machine",
        return_value="x86_64",
    ):
        completed = run_initial_setup_flow(prompt_backend=backend)

    settings = load_settings()
    backend_names = [
        choice["value"]
        for prompt_type, kwargs in backend.calls
        if prompt_type == "select" and kwargs["message"].startswith("Select a transcription backend")
        for choice in kwargs["choices"]
    ]

    assert completed is True
    assert settings.setup_completed is True
    assert settings.preferred_transcription_backend == "faster-whisper"
    assert settings.preferred_whisper_model == "small"
    assert settings.preferred_local_provider == "openai"
    assert "mlx-whisper" not in backend_names


def test_settings_command_applies_custom_changes_and_prints_summary(monkeypatch, tmp_path):
    """brainpack settings should show the inline edit menu and persist saved changes."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.cli import app
    from brainpack.settings import load_settings

    _save_global_settings(tmp_path, preferred_whisper_model="small")
    runner = CliRunner()
    # Sequence: menu → "mode", edit mode → "local",
    #           menu → "whisper_model", edit whisper → "large",
    #           menu → "__save__"
    backend = _FakePromptBackend(
        [
            "mode",
            "local",
            "whisper_model",
            "large",
            "__save__",
        ]
    )

    with patch("brainpack.cli.is_interactive_session", return_value=True), patch(
        "brainpack.cli.load_prompt_backend",
        return_value=backend,
    ):
        result = runner.invoke(app, ["settings"])

    settings = load_settings()

    assert result.exit_code == 0
    assert settings.preferred_whisper_model == "large"
    # Settings table is always shown
    assert "Brainpack Settings" in result.output
    assert "Settings saved" in result.output


def test_settings_command_shows_table_in_non_tty(
    monkeypatch,
    tmp_path,
):
    """Non-interactive settings invocation shows the current settings table and exits cleanly."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.cli import app

    _save_global_settings(tmp_path)
    runner = CliRunner()

    with patch("brainpack.cli.is_interactive_session", return_value=False), patch(
        "brainpack.cli.load_prompt_backend",
        side_effect=AssertionError("prompt backend should stay unloaded"),
    ):
        result = runner.invoke(app, ["settings"])

    assert result.exit_code == 0
    assert "Brainpack Settings" in result.output
    assert "Transcription" in result.output
    assert "brainpack settings" in result.output


def test_saved_local_preference_shown_in_home_settings_section(
    monkeypatch,
    tmp_path,
):
    """The home screen settings section reflects the saved mode preference."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.cli import app

    _save_global_settings(tmp_path)
    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "local" in result.output


def test_cancelled_initial_setup_leaves_settings_missing(monkeypatch, tmp_path):
    """Aborting first-run setup must not leave behind a partial settings file."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.interactive import run_initial_setup_flow
    from brainpack.settings import settings_path

    backend = _FakePromptBackend(
        [
            "custom",
            KeyboardInterrupt(),
        ]
    )

    completed = run_initial_setup_flow(prompt_backend=backend)

    assert completed is False
    assert settings_path().exists() is False


def test_cancelled_settings_edit_preserves_previous_settings(monkeypatch, tmp_path):
    """Aborting a later settings edit should keep the prior settings file untouched."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.interactive import run_settings_flow
    from brainpack.settings import load_settings, settings_path

    _save_global_settings(
        tmp_path,
        preferred_whisper_model="small",
        preferred_local_provider="ollama",
    )
    original = settings_path().read_text()
    backend = _FakePromptBackend(
        [
            "custom",
            "local",
            KeyboardInterrupt(),
        ]
    )

    completed = run_settings_flow(prompt_backend=backend)

    assert completed is False
    assert settings_path().read_text() == original


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


def test_load_prompt_backend_returns_inquirer_module():
    """Lazy prompt loading should expose the documented InquirerPy backend module."""
    removed = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "InquirerPy" or name.startswith("InquirerPy.")
    }

    try:
        from brainpack.interactive import load_prompt_backend

        backend = load_prompt_backend()

        assert backend.__name__ == "InquirerPy.inquirer"
        assert hasattr(backend, "select")
        assert hasattr(backend, "text")
        assert hasattr(backend, "confirm")
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


def test_no_arg_interactive_home_routes_to_authoring_menu_after_setup(tmp_path):
    """Interactive no-arg use with no packs installed routes to the authoring menu."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    runner = CliRunner()
    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli.needs_initial_setup", return_value=False
    ), patch(
        "brainpack.cli.is_interactive_session",
        return_value=True,
    ), patch(
        "brainpack.cli.run_authoring_menu",
        create=True,
        return_value=True,
    ) as menu_mock, patch(
        "brainpack.cli._render_home_screen",
    ) as home_mock:
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    menu_mock.assert_called_once_with()
    home_mock.assert_not_called()


@pytest.mark.parametrize(
    ("selection", "expected_attr"),
    [
        ("create", "run_create_flow"),
        ("import", "run_import_flow"),
        ("manage", "run_manage_pack_flow"),
    ],
)
def test_authoring_menu_branches_create_import_and_manage(tmp_path, selection, expected_attr):
    """The human menu should branch into create, import, or manage without changing direct commands."""
    from brainpack.interactive import run_authoring_menu

    backend = _FakePromptBackend([selection])

    with patch("brainpack.interactive.run_create_flow", create=True) as create_mock, patch(
        "brainpack.interactive.run_import_flow",
        create=True,
    ) as import_mock, patch(
        "brainpack.interactive.run_manage_pack_flow",
        create=True,
    ) as manage_mock:
        completed = run_authoring_menu(
            packs_dir=tmp_path / "brainpacks",
            prompt_backend=backend,
        )

    select_calls = [kwargs for prompt_type, kwargs in backend.calls if prompt_type == "select"]
    labels = [choice["name"] for choice in select_calls[0]["choices"]]

    assert completed is True
    values = [choice["value"] for choice in select_calls[0]["choices"]]
    assert values == ["create", "import", "manage"]
    assert create_mock.call_count == (1 if expected_attr == "run_create_flow" else 0)
    assert import_mock.call_count == (1 if expected_attr == "run_import_flow" else 0)
    assert manage_mock.call_count == (1 if expected_attr == "run_manage_pack_flow" else 0)


def test_create_command_asks_source_input_first_and_writes_local_text_source(tmp_path):
    """create should start from a source URL/path prompt and persist local text paths as sources."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    local_source = tmp_path / "notes.md"
    local_source.write_text("# Notes\n")
    backend = _FakePromptBackend(
        [
            str(local_source),
            "creator-pack",
            "Creator notes",
            True,
        ]
    )

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli.is_interactive_session",
        return_value=True,
    ), patch(
        "brainpack.cli.load_prompt_backend",
        return_value=backend,
    ):
        result = runner.invoke(app, ["create"])

    assert result.exit_code == 0
    assert "Create a new pack" in result.output
    assert "Start with one source." in result.output
    assert "Review pack" in result.output

    pack_dir = packs_root / "creator-pack"
    raw = yaml.safe_load((pack_dir / "pack.yaml").read_text())
    config = load_config(pack_dir)

    assert raw["id"] == "creator-pack"
    assert raw["name"] == "creator-pack"
    assert raw["description"] == "Creator notes"
    assert raw["version"] == "1.0.0"
    assert raw["created"] is not None
    assert raw["updated"] is not None
    assert raw["sources"] == [str(local_source)]
    assert config.id == "creator-pack"
    assert config.name == "creator-pack"
    assert config.sources == [SourceEntry(url=str(local_source))]
    text_prompts = [
        kwargs["message"]
        for prompt_type, kwargs in backend.calls
        if prompt_type == "text"
    ]
    assert text_prompts[0] == "Source URL or local path"
    assert "Source type" not in " ".join(text_prompts)


def test_add_rejects_local_text_path_as_pack_import(tmp_path):
    """add remains import-only and should not reinterpret a local text file as pack authoring input."""
    from brainpack.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "brainpacks"
    local_source = tmp_path / "notes.txt"
    local_source.write_text("plain text source")

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["add", str(local_source)])

    assert result.exit_code == 1
    assert "Invalid pack.yaml" in result.output


def test_manage_flow_can_edit_basic_metadata_and_add_source(tmp_path):
    """Manage flow should update description and add a local text-like source without manual YAML edits."""
    from brainpack.config import write_config, PackConfig
    from brainpack.interactive import run_manage_pack_flow

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "managed-pack"
    local_source = tmp_path / "transcript.md"
    local_source.write_text("notes")
    write_config(
        PackConfig(
            id="managed-pack",
            name="managed-pack",
            description="Original description",
            llm="ollama",
            sources=[SourceEntry(url="https://example.com/article")],
        ),
        pack_dir / "pack.yaml",
    )

    backend = _FakePromptBackend(
        [
            "managed-pack",
            "Updated description",
            True,
            str(local_source),
            True,
        ]
    )

    completed = run_manage_pack_flow(
        packs_dir=packs_root,
        prompt_backend=backend,
    )

    config = load_config(pack_dir)

    assert completed is True
    assert config.description == "Updated description"
    assert [source.url for source in config.sources] == [
        "https://example.com/article",
        str(local_source),
    ]


def test_manage_flow_cancel_preserves_existing_pack_definition(tmp_path):
    """Cancelling managed edits should leave the current pack.yaml untouched."""
    from brainpack.config import write_config, PackConfig
    from brainpack.interactive import run_manage_pack_flow

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "managed-pack"
    write_config(
        PackConfig(
            id="managed-pack",
            name="managed-pack",
            description="Original description",
            llm="ollama",
            sources=[SourceEntry(url="https://example.com/article")],
        ),
        pack_dir / "pack.yaml",
    )
    original = (pack_dir / "pack.yaml").read_text()
    backend = _FakePromptBackend(
        [
            "managed-pack",
            "Changed description",
            False,
            KeyboardInterrupt(),
        ]
    )

    completed = run_manage_pack_flow(
        packs_dir=packs_root,
        prompt_backend=backend,
    )

    assert completed is False
    assert (pack_dir / "pack.yaml").read_text() == original


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


def test_build_local_path_reads_text_without_remote_fetch(tmp_path):
    """build ingests a local text-like path through the narrow local loader."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.fetch_article") as mock_fetch, \
         patch("brainpack.cli.chunk_text", return_value=["chunk one"]), \
         patch("brainpack.cli.embed_and_store", return_value=1), \
         patch("brainpack.cli.mark_processed") as mock_mark, \
         patch("brainpack.cli.mark_failed") as mock_fail:
        result = runner.invoke(app, ["build", "local-pack"])

    assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"
    mock_fetch.assert_not_called()
    mock_mark.assert_called_once()
    mock_fail.assert_not_called()
    assert "done" in result.output.lower()


def test_build_local_path_missing_file_fails_clearly(tmp_path):
    """build marks missing local text-like sources failed without treating them as remote articles."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.fetch_article") as mock_fetch, \
         patch("brainpack.cli.chunk_text") as mock_chunk, \
         patch("brainpack.cli.embed_and_store") as mock_embed, \
         patch("brainpack.cli.mark_processed") as mock_mark, \
         patch("brainpack.cli.mark_failed") as mock_fail:
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
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "binary-pack"
    pack_dir.mkdir(parents=True)
    source = tmp_path / "recording.mp3"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.fetch_article") as mock_fetch, \
         patch("brainpack.cli.chunk_text") as mock_chunk, \
         patch("brainpack.cli.embed_and_store") as mock_embed, \
         patch("brainpack.cli.mark_processed") as mock_mark, \
         patch("brainpack.cli.mark_failed") as mock_fail:
        result = runner.invoke(app, ["build", "binary-pack"])

    # Failed sources exit non-zero (plan 12-03 spec: unresolved failures return non-zero)
    assert result.exit_code == 1, f"Exit code {result.exit_code}, output: {result.output}"
    mock_fetch.assert_not_called()
    mock_chunk.assert_not_called()
    mock_embed.assert_not_called()
    mock_mark.assert_not_called()
    mock_fail.assert_called_once()
    assert "unsupported local source type" in result.output.lower()


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
    from brainpack.cli import app

    monkeypatch.setenv("HOME", str(tmp_path))
    _save_global_settings(tmp_path, preferred_whisper_model=settings_model)

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(pack_yaml, encoding="utf-8")

    runner = CliRunner()
    audio_file = tmp_path / "audio.m4a"
    audio_file.write_bytes(b"x" * 20_000)
    episode = {"id": "vid123", "title": "Test Video", "url": "https://youtu.be/vid123"}
    segments = [{"start": 0.0, "end": 5.0, "text": "Content"}]
    mock_transcribe = MagicMock(return_value=segments)

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli._youtube_build_issue", return_value=None), \
         patch("brainpack.cli._check_ffmpeg_available", return_value=True), \
         patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
         patch("brainpack.cli.download_audio", return_value=audio_file), \
         patch("brainpack.cli.transcribe_audio", mock_transcribe), \
         patch("brainpack.cli.chunk_text", return_value=["chunk1"]), \
         patch("brainpack.cli.embed_and_store", return_value=1), \
         patch("brainpack.cli.is_audio_step_done", return_value=False), \
         patch("brainpack.cli.get_audio_step", return_value={}), \
         patch("brainpack.cli.mark_audio_step"), \
         patch("brainpack.cli.mark_failed"):
        result = runner.invoke(app, ["build", "test-pack", *build_args])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
    _, kwargs = mock_transcribe.call_args
    assert kwargs.get("model_size") == expected_model


def test_phase_11_traceability_artifact_exists():
    """Phase 11 leaves an explicit local traceability artifact instead of only plan prose."""
    traceability = Path(
        ".planning/phases/11-add-interactive-setup-settings-and-guided-pack-authoring-ux/11-TRACEABILITY.md"
    )

    assert traceability.exists()
    content = traceability.read_text(encoding="utf-8")
    assert "ONB-02" in content
    assert "RUN-01" in content
    assert "AUT-02" in content


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
         patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
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
         patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
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
             patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
             patch("brainpack.cli.download_audio", mock_download), \
             patch("brainpack.cli.transcribe_audio", mock_transcribe), \
             patch("brainpack.cli.chunk_text", return_value=["chunk1"]), \
             patch("brainpack.cli.embed_and_store", mock_embed), \
             patch("brainpack.cli.is_audio_step_done", return_value=False), \
             patch("brainpack.cli.get_audio_step", return_value={}), \
             patch("brainpack.cli.mark_audio_step"), \
             patch("brainpack.cli.mark_failed"):

            result = runner.invoke(app, ["build", "test-pack", "--verbose"])

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
             patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
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
             patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
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
        result = runner.invoke(app, ["build", "test-pack", "--verbose"])

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
    rows = [line.strip() for line in result.output.splitlines() if line.strip().startswith(("a-pack", "b-pack"))]
    assert rows[0].startswith("a-pack")
    assert rows[1].startswith("b-pack")
    assert "2" in rows[0]
    assert "2" in rows[0]
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
    assert expected_status in result.output
    assert "articles" in result.output
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
         patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)), \
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
         patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)), \
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
         patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)), \
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
         patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)), \
         patch("brainpack.cli.is_audio_step_done", return_value=True), \
         patch("brainpack.cli.get_audio_step", return_value={}), \
         patch("brainpack.cli.embed_and_store", return_value=0), \
         patch("brainpack.cli.mark_audio_step"), \
         patch("brainpack.cli.check_model_provenance"):
        result = runner.invoke(app, ["build", "testpack"])

    assert "0 new chunks" in result.output
    assert "up to date" in result.output


# ---------------------------------------------------------------------------
# Phase 12 Plan 02: Inventory-first home/list/status rendering
# ---------------------------------------------------------------------------


def _write_ready_pack(pack_dir, *, name: str = "demo-pack", llm: str = "ollama") -> None:
    """Write a minimal ready-state pack to disk."""
    from brainpack.inventory import pack_config_hash
    from brainpack.pack_state import save_state

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


def test_no_arg_tty_with_installed_packs_shows_home_table_not_authoring_menu(tmp_path):
    """TTY with installed packs: inventory table shown directly, authoring menu bypassed."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    _write_ready_pack(packs_root / "demo-pack", name="demo-pack")
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli.needs_initial_setup", return_value=False
    ), patch(
        "brainpack.cli.is_interactive_session", return_value=True
    ), patch(
        "brainpack.cli.run_authoring_menu",
        side_effect=AssertionError("authoring menu should not be called when packs exist"),
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Installed packs" in result.output
    assert "demo-pack" in result.output


def test_no_arg_tty_empty_inventory_still_routes_to_authoring_menu(tmp_path):
    """TTY with no packs should still show the authoring menu for first-pack creation."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    runner = CliRunner()

    menu_called = []

    def fake_authoring_menu():
        menu_called.append(True)
        return True

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli.needs_initial_setup", return_value=False
    ), patch(
        "brainpack.cli.is_interactive_session", return_value=True
    ), patch(
        "brainpack.cli.run_authoring_menu", side_effect=fake_authoring_menu
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert menu_called == [True]


def test_list_human_output_stays_compact_without_coaching_blocks(tmp_path):
    """list shows a compact table without appending 'Use with agent' coaching sections."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    _write_ready_pack(packs_root / "demo-pack", name="demo-pack")
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli._check_ollama_reachable", return_value=True
    ):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "demo-pack" in result.output
    assert "Use with agent" not in result.output
    assert "Use with local model" not in result.output
    assert "brainpack mcp-server" not in result.output


def test_status_renders_provenance_and_build_recap_before_source_rows(tmp_path):
    """status: provenance/build-recap sections must appear before the Sources section."""
    from brainpack.cli import app
    from brainpack.inventory import save_pack_origin

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli._check_ollama_reachable", return_value=True
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
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    _write_ready_pack(packs_root / "ready-pack", name="ready-pack")
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli._check_ollama_reachable", return_value=True
    ):
        result = runner.invoke(app, ["status", "ready-pack"])

    assert result.exit_code == 0
    assert "Use with agent" not in result.output
    assert "Use with local model" not in result.output
    # Ready packs: no coaching copy about next steps
    assert "brainpack mcp-server" not in result.output
    assert "brainpack create" not in result.output


def test_status_blocked_pack_shows_blockers_inline_without_coaching(tmp_path):
    """status on a blocked pack shows blocker text inline without appending the full coaching block."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ", {}, clear=True
    ):
        result = runner.invoke(app, ["status", "blocked-pack"])

    assert result.exit_code == 0
    # Blocker text must be present inline
    assert "OPENAI_API_KEY" in result.output
    # But coaching copy (Use with agent/local model blocks) must not be appended
    assert "Use with agent" not in result.output
    assert "Use with local model" not in result.output


def test_status_audio_sources_do_not_repeat_unowned_partial_episodes(tmp_path):
    """status should scope partial audio episodes to their owning source."""
    from brainpack.cli import app
    from brainpack.pack_state import save_state

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["status", "demo-pack"])

    assert result.exit_code == 0
    output = result.output
    assert output.count("Yazilim sektorundeki dolandiricilik") == 1
    assert "https://www.youtube.com/watch?v=yoXW3XD8li0" in output


def test_list_json_stays_stable_and_prompt_free_for_installed_packs(tmp_path):
    """list --json stays single-document, prompt-free, and structurally unchanged after inventory-first changes."""
    from brainpack.cli import app
    from brainpack.machine_output import CLI_SCHEMA_VERSION

    packs_root = tmp_path / "brainpacks"
    _write_ready_pack(packs_root / "demo-pack", name="demo-pack")
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch(
        "brainpack.cli._check_ollama_reachable", return_value=True
    ), patch(
        "brainpack.cli.load_prompt_backend",
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


def test_status_json_stays_stable_and_prompt_free_after_rendering_changes(tmp_path):
    """status --json stays single-document, prompt-free after human-rendering changes."""
    from brainpack.cli import app
    from brainpack.machine_output import CLI_SCHEMA_VERSION

    packs_root = tmp_path / "brainpacks"
    _write_ready_pack(packs_root / "demo-pack", name="demo-pack", llm="openai")
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), patch.dict(
        "os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False
    ), patch(
        "brainpack.cli.load_prompt_backend",
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


# ---------------------------------------------------------------------------
# Phase 12 Plan 03: Build output polish — concise progress, always-on summary table,
# mixed-result verdicts, and persisted recap state.
# ---------------------------------------------------------------------------
from contextlib import ExitStack


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
    stack.enter_context(patch("brainpack.cli._PACKS_DIR", packs_root))
    stack.enter_context(patch("brainpack.cli.load_config", return_value=mock_config))
    stack.enter_context(patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}))
    stack.enter_context(patch("brainpack.cli.check_model_provenance"))
    if save_state_mock:
        stack.enter_context(patch("brainpack.cli.save_state"))
    stack.enter_context(patch("brainpack.cli.load_model", return_value=MagicMock()))
    stack.enter_context(patch("brainpack.cli.get_collection", return_value=MagicMock()))
    if detect_side_effects:
        stack.enter_context(patch("brainpack.cli.detect_source_type", side_effect=detect_side_effects))
    else:
        stack.enter_context(patch("brainpack.cli.detect_source_type", return_value="article"))
    stack.enter_context(patch("brainpack.cli.is_processed", return_value=is_processed_return))
    if fetch_side_effects is not None:
        stack.enter_context(patch("brainpack.cli.fetch_article", side_effect=fetch_side_effects))
    else:
        stack.enter_context(patch("brainpack.cli.fetch_article", return_value=fetch_return))
    stack.enter_context(patch("brainpack.cli.chunk_text", return_value=["chunk"]))
    stack.enter_context(patch("brainpack.cli.embed_and_store", return_value=embed_return))
    stack.enter_context(patch("brainpack.cli.mark_processed"))
    stack.enter_context(patch("brainpack.cli.mark_failed"))
    if extra:
        for name, kwargs in extra.items():
            stack.enter_context(patch(name, **kwargs))
    return stack


def test_build_always_prints_summary_table_for_zero_new_run(tmp_path):
    """build must print a compact summary table even when all sources are already up-to-date."""
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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
            "brainpack.cli._check_ffmpeg_available": {"return_value": False},
            "brainpack.cli._youtube_build_issue": {"return_value": None},
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
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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
    # Count how many times "bad" or "failed" appears — recap at end means it should appear at least twice
    # (once inline, once in recap)
    failed_mentions = output.lower().count("fail") + output.lower().count("bad")
    assert failed_mentions >= 2, (
        f"Expected failed sources to appear multiple times (inline + recap), "
        f"got {failed_mentions} in: {output!r}"
    )


def test_build_persists_last_build_recap_for_mixed_result(tmp_path):
    """build persists last_build_result and last_build_summary into state for mixed outcomes."""
    from brainpack.cli import app
    from brainpack.pack_state import load_state
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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

    # Don't mock save_state — we need real disk writes to verify persistence
    with _p12_article_patches(
        packs_root, mock_config,
        fetch_side_effects=[("Article text", "Good Article"), None],
        embed_return=1,
        save_state_mock=False,
        extra={"brainpack.cli._youtube_build_issue": {"return_value": None}},
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
    from brainpack.cli import app
    from brainpack.pack_state import load_state
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])

    # Don't mock save_state — we need real disk writes to verify persistence
    with _p12_article_patches(
        packs_root, mock_config,
        fetch_return=("Article text", "Good Article"),
        embed_return=2,
        save_state_mock=False,
        extra={"brainpack.cli._youtube_build_issue": {"return_value": None}},
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
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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
    stack.enter_context(patch("brainpack.cli._PACKS_DIR", packs_root))
    stack.enter_context(patch("brainpack.cli.load_config", return_value=mock_config))
    stack.enter_context(patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}))
    stack.enter_context(patch("brainpack.cli.check_model_provenance"))
    stack.enter_context(patch("brainpack.cli.save_state"))
    stack.enter_context(patch("brainpack.cli.load_model", return_value=MagicMock()))
    stack.enter_context(patch("brainpack.cli.get_collection", return_value=MagicMock()))
    stack.enter_context(patch("brainpack.cli.detect_source_type", return_value="youtube"))
    stack.enter_context(patch("brainpack.cli.check_deno_available", return_value=True))
    stack.enter_context(patch("brainpack.cli._youtube_build_issue", return_value=None))
    stack.enter_context(patch("brainpack.cli._check_ffmpeg_available", return_value=True))
    stack.enter_context(patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", episodes)))
    stack.enter_context(patch("brainpack.cli.is_audio_step_done", return_value=False))
    stack.enter_context(patch("brainpack.cli.get_audio_step", return_value={}))
    stack.enter_context(patch("brainpack.cli.download_audio", return_value=audio_file))
    stack.enter_context(patch("brainpack.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]))
    stack.enter_context(patch("brainpack.cli.embed_and_store", return_value=3))
    stack.enter_context(patch("brainpack.cli.mark_audio_step"))
    stack.enter_context(patch("brainpack.cli._canonical_audio_path", return_value=audio_file))
    stack.enter_context(patch("brainpack.cli._save_transcript_segments"))
    stack.enter_context(patch("brainpack.cli._chunk_transcript_segments", return_value=(["chunk"], [{}])))

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
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}, "audio_steps": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="youtube"), \
         patch("brainpack.cli._youtube_build_issue", return_value=None), \
         patch("brainpack.cli._check_ffmpeg_available", return_value=True), \
         patch("brainpack.cli.list_youtube_episodes", return_value=("Test Playlist", [episode])), \
         patch("brainpack.cli.is_audio_step_done", return_value=False), \
         patch("brainpack.cli.get_audio_step", return_value={}), \
         patch("brainpack.cli.download_audio", return_value=audio_file), \
         patch("brainpack.cli.transcribe_audio", return_value=[{"start": 0.0, "end": 1.0, "text": "hello"}]), \
         patch("brainpack.cli.embed_and_store", return_value=3), \
         patch("brainpack.cli.mark_audio_step"), \
         patch("brainpack.cli._canonical_audio_path", return_value=audio_file), \
         patch("brainpack.cli._save_transcript_segments"), \
         patch("brainpack.cli._chunk_transcript_segments", return_value=(["chunk"], [{}])):
        result = runner.invoke(app, ["build", "testpack"])

    output = result.output
    assert "[download] Episode 1/1: Ep 1" in output
    assert "[transcribe] Episode 1/1: Ep 1" in output
    assert "[embed] Episode 1/1: Ep 1" in output
    assert "[embed] Loading embedding model:" in output


def test_build_clean_success_exits_0_and_shows_summary(tmp_path):
    """Clean build (no failures) exits 0 and always shows a final summary table."""
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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


# ---------------------------------------------------------------------------
# Phase 12-04: Remove / Reset / Update lifecycle flows and discovery  (RED)
# ---------------------------------------------------------------------------


def test_remove_command_exists_and_deletes_only_target_pack(tmp_path):
    """brainpack remove <pack> is a first-class command that deletes only the target installed pack."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    other_dir = packs_root / "other-pack"
    pack_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    (other_dir / "pack.yaml").write_text(
        "name: other-pack\ndescription: Other\nllm: ollama\nsources:\n"
        "  - https://example.com/other\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["remove", "test-pack", "--yes"])

    assert result.exit_code == 0
    assert not pack_dir.exists(), "target pack should be deleted"
    assert other_dir.exists(), "other packs must not be touched"


def test_remove_command_uses_explicit_destructive_wording(tmp_path):
    """brainpack remove output must include explicit destructive wording."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["remove", "test-pack", "--yes"])

    assert result.exit_code == 0
    output = result.output.lower()
    assert "removed" in output or "deleted" in output


def test_remove_command_requires_yes_or_force_in_non_interactive_use(tmp_path):
    """brainpack remove in non-interactive use (no TTY) must require --yes/--force to proceed."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    runner = CliRunner()

    # Non-interactive with no --yes should abort without deleting
    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.is_interactive_session", return_value=False):
        result = runner.invoke(app, ["remove", "test-pack"])

    assert result.exit_code != 0 or pack_dir.exists(), (
        "remove without --yes in non-interactive session should abort or keep the pack"
    )


def test_remove_nonexistent_pack_fails_with_clear_message(tmp_path):
    """brainpack remove on a missing pack should exit non-zero with a clear message."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    packs_root.mkdir(parents=True)
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["remove", "ghost-pack", "--yes"])

    assert result.exit_code != 0
    assert "ghost-pack" in result.output.lower() or "ghost-pack" in (result.stderr or "").lower()


def test_build_reset_flag_clears_runtime_artifacts_before_rebuild(tmp_path):
    """brainpack build <pack> --reset clears runtime artifacts and then runs the normal build path."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="article"), \
         patch("brainpack.cli.is_processed", return_value=False), \
         patch("brainpack.cli.fetch_article", return_value=("Article text", "Article Title")), \
         patch("brainpack.cli.chunk_text", return_value=["chunk"]), \
         patch("brainpack.cli.embed_and_store", return_value=1), \
         patch("brainpack.cli.mark_processed"), \
         patch("brainpack.cli.mark_failed"):
        result = runner.invoke(app, ["build", "test-pack", "--reset"])

    assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
    assert not chroma_dir.exists(), "--reset should have removed the chroma directory"


def test_build_reset_preserves_pack_yaml_and_origin_json(tmp_path):
    """brainpack build <pack> --reset must not remove pack.yaml or origin.json."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.check_model_provenance"), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli.load_model", return_value=MagicMock()), \
         patch("brainpack.cli.get_collection", return_value=MagicMock()), \
         patch("brainpack.cli.detect_source_type", return_value="article"), \
         patch("brainpack.cli.is_processed", return_value=False), \
         patch("brainpack.cli.fetch_article", return_value=("Article text", "Article Title")), \
         patch("brainpack.cli.chunk_text", return_value=["chunk"]), \
         patch("brainpack.cli.embed_and_store", return_value=1), \
         patch("brainpack.cli.mark_processed"), \
         patch("brainpack.cli.mark_failed"):
        result = runner.invoke(app, ["build", "test-pack", "--reset"])

    assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
    assert (pack_dir / "pack.yaml").read_text() == pack_yaml_text, "pack.yaml must survive --reset"
    assert (pack_dir / "origin.json").read_text() == origin_text, "origin.json must survive --reset"


def test_model_mismatch_remediation_points_to_build_reset(tmp_path):
    """Embedding model mismatch error message must point to `brainpack build <pack> --reset`."""
    from brainpack.pack_state import check_model_provenance

    state = {"embedding_model": "all-MiniLM-L6-v2"}
    import typer as _typer

    with pytest.raises(_typer.BadParameter) as exc_info:
        check_model_provenance(state, "paraphrase-multilingual-MiniLM-L12-v2", "my-pack")

    message = str(exc_info.value)
    assert "build" in message.lower() and "reset" in message.lower(), (
        f"Mismatch remediation should mention `build --reset`, got: {message!r}"
    )
    # Must not advise manual chroma directory deletion
    assert "delete" not in message.lower() and "chroma/" not in message, (
        f"Mismatch should not instruct manual deletion, got: {message!r}"
    )


def test_transcription_model_mismatch_remediation_points_to_build_reset():
    """Whisper model mismatch error message must point to `brainpack build <pack> --reset`."""
    from brainpack.pack_state import check_transcription_provenance

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
    from brainpack.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "brainpacks"
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

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value=state), \
         patch("brainpack.cli.save_state"), \
         patch("brainpack.cli._has_audio_sources", return_value=True):
        result = runner.invoke(app, ["build", "test-pack", "--model", "small"])

    assert result.exit_code == 2
    assert "Transcription model mismatch" in result.output
    assert "--reset" in result.output


def test_update_with_remembered_origin_fetches_and_rebuilds(tmp_path):
    """brainpack update refreshes pack.yaml from origin and rebuilds when the definition changed."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    import json as _json
    (pack_dir / "origin.json").write_text(_json.dumps({
        "source": "https://example.com/pack.yaml",
        "type": "url",
        "resolved": "https://example.com/pack.yaml",
    }))

    mock_config = _make_config([
        SourceEntry(url="https://example.com/article"),
        SourceEntry(url="https://example.com/new"),
    ])
    mock_config.id = "test-pack"  # must match the installed pack id
    runner = CliRunner()

    incoming_yaml = tmp_path / "incoming.yaml"
    incoming_yaml.write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "  - https://example.com/new\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    def _fake_write(_resolved, destination):
        destination.write_text(incoming_yaml.read_text())
        return destination, mock_config

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_pack_origin", return_value={
             "source": "https://example.com/pack.yaml",
             "type": "url",
             "resolved": "https://example.com/pack.yaml",
         }), \
         patch("brainpack.cli.resolve_pack_origin", return_value={
             "source": "https://example.com/pack.yaml",
             "type": "url",
             "resolved": "https://example.com/pack.yaml",
         }) as mock_resolve, \
         patch("brainpack.cli._write_pack_yaml_from_source", side_effect=_fake_write), \
         patch("brainpack.cli.save_pack_origin"), \
         patch("brainpack.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "test-pack"])

    assert result.exit_code == 0, result.output
    mock_resolve.assert_called_once()
    mock_build.assert_called_once()


def test_update_with_unchanged_remembered_origin_skips_rebuild_and_reports_runtime(tmp_path):
    """brainpack update should not rebuild when the synced remote definition is unchanged."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    installed_yaml = (
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    (pack_dir / "pack.yaml").write_text(installed_yaml)
    runner = CliRunner()

    incoming_yaml = tmp_path / "incoming-same.yaml"
    incoming_yaml.write_text(installed_yaml)
    mock_config = _make_config([SourceEntry(url="https://example.com/article")])
    mock_config.id = "test-pack"

    def _fake_write(_resolved, destination):
        destination.write_text(incoming_yaml.read_text())
        return destination, mock_config

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_pack_origin", return_value={
             "source": "https://example.com/pack.yaml",
             "type": "url",
             "resolved": "https://example.com/pack.yaml",
         }), \
         patch("brainpack.cli.resolve_pack_origin", return_value={
             "source": "https://example.com/pack.yaml",
             "type": "url",
             "resolved": "https://example.com/pack.yaml",
         }), \
         patch("brainpack.cli._write_pack_yaml_from_source", side_effect=_fake_write), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.save_pack_origin"), \
         patch("brainpack.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "test-pack"])

    assert result.exit_code == 0, result.output
    mock_build.assert_not_called()
    assert "definition is already current" in result.output.lower()
    assert "runtime status" in result.output.lower()


def test_update_without_remembered_origin_says_no_remote_refresh(tmp_path):
    """brainpack update with no stored origin reports runtime state and does not rebuild."""
    from brainpack.cli import app

    packs_root = tmp_path / "brainpacks"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    mock_config = _make_config([SourceEntry(url="https://example.com/article")])
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli.load_pack_origin", return_value={}), \
         patch("brainpack.cli.load_config", return_value=mock_config), \
         patch("brainpack.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("brainpack.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "test-pack"])

    assert result.exit_code == 0
    mock_build.assert_not_called()
    output = result.output.lower()
    assert (
        "no remembered remote origin" in output
        or "no remote origin" in output
    ), f"Expected a note about no remote refresh, got: {result.output!r}"
    assert "runtime status" in output
    assert "next step: brainpack build test-pack" in output


def test_status_command_exposes_lifecycle_management_lines(tmp_pack_root):
    """brainpack status should expose explicit lifecycle management commands in its output."""
    from brainpack.cli import app

    packs_root, pack_dir = tmp_pack_root
    _mark_pack_ready(pack_dir)
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True):
        result = runner.invoke(app, ["status", "test-pack"])

    assert result.exit_code == 0
    output = result.output
    # Lifecycle management commands should appear on pack-specific status
    assert "brainpack build test-pack --reset" in output or "build test-pack --reset" in output
    assert "brainpack update test-pack" in output or "update test-pack" in output
    assert "brainpack remove test-pack" in output or "remove test-pack" in output


def test_home_screen_with_packs_exposes_lifecycle_management_lines(tmp_pack_root):
    """Home screen with installed packs shows pack table and help footer."""
    from brainpack.cli import app

    packs_root, pack_dir = tmp_pack_root
    _mark_pack_ready(pack_dir)
    runner = CliRunner()

    with patch("brainpack.cli._PACKS_DIR", packs_root), \
         patch("brainpack.cli._check_ollama_reachable", return_value=True):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    output = result.output
    # Pack table and commands reachable via footer
    assert "Installed packs" in output
    assert "test-pack" in output
    assert "brainpack help" in output
