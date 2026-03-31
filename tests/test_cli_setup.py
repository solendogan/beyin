"""Tests for CLI setup, home screen, settings, TTY detection, and interactive flow."""
import importlib
import sys
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch

from beyin import __version__
from tests.conftest import (
    _FakePromptBackend,
    _save_global_settings,
    _mark_pack_ready,
)


@pytest.fixture(autouse=True)
def _default_punkt_tab_ready():
    """Keep setup/home tests independent from host NLTK data state."""
    with patch("beyin.cli._punkt_tab_build_issue", return_value=None), \
         patch("beyin.cli._check_nltk_punkt_tab_available", return_value=True), \
         patch("beyin.interactive._check_nltk_punkt_tab_available", return_value=True):
        yield


def test_no_arg_home_screen_guides_first_run(tmp_path):
    """No-arg invocation on a fresh machine shows a guided home screen."""
    from beyin.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "beyin"

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert f"beyin v{__version__}" in result.output
    assert "No packs installed yet" in result.output
    assert "Settings" in result.output
    assert "Dependencies" in result.output
    assert "Local model" in result.output
    assert "beyin create" in result.output
    assert "beyin settings" in result.output


def test_no_arg_home_screen_orients_around_existing_inventory(tmp_pack_root):
    """No-arg invocation with installed packs shows inventory and settings."""
    from beyin.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._check_ollama_reachable", return_value=True):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Installed packs" in result.output
    assert "ID" in result.output
    assert "Status" in result.output
    assert "test-pack" in result.output
    assert "needs-build" in result.output
    assert "Settings" in result.output
    assert "Local model" in result.output


def test_no_arg_home_screen_is_not_plain_help_text(tmp_pack_root):
    """No-arg invocation renders product copy instead of the default help screen."""
    from beyin.cli import app

    packs_root, _ = tmp_pack_root
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._check_ollama_reachable", return_value=True):
        home_result = runner.invoke(app, [])

    help_result = runner.invoke(app, ["--help"])

    assert home_result.exit_code == 0
    assert help_result.exit_code == 0
    assert "Usage:" not in home_result.output
    assert "Commands:" not in home_result.output
    assert f"beyin v{__version__}" in home_result.output
    assert "Home" not in home_result.output
    assert "Your local knowledge base" not in home_result.output
    assert home_result.output != help_result.output


def test_no_arg_tty_first_run_routes_to_the_setup_seam_before_home_screen():
    """No-subcommand first-run setup is only considered on the interactive TTY path."""
    from beyin.cli import app

    runner = CliRunner()

    with patch("beyin.cli.needs_initial_setup", return_value=True) as needs_mock, patch(
        "beyin.cli.is_interactive_session",
        return_value=True,
    ) as tty_mock, patch(
        "beyin.cli._run_initial_setup_flow",
        return_value=True,
    ) as setup_mock, patch(
        "beyin.cli._render_home_screen"
    ) as home_mock, patch(
        "beyin.cli.list_packs",
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
    from beyin.cli import app

    runner = CliRunner()

    with patch("beyin.cli.needs_initial_setup", return_value=True), patch(
        "beyin.cli.is_interactive_session",
        return_value=True,
    ), patch(
        "beyin.cli._run_initial_setup_flow",
        return_value=False,
    ) as setup_mock, patch(
        "beyin.cli.run_authoring_menu",
    ) as authoring_mock, patch(
        "beyin.cli._render_home_screen",
    ) as home_mock, patch(
        "beyin.cli.list_packs",
        return_value=[],
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    setup_mock.assert_called_once_with()
    authoring_mock.assert_not_called()
    home_mock.assert_not_called()


def test_no_arg_non_tty_first_run_falls_back_to_current_home_screen():
    """Fresh non-TTY runs should not try to prompt and should keep the current guidance."""
    from beyin.cli import app

    runner = CliRunner()

    with patch("beyin.cli.needs_initial_setup", return_value=True), patch(
        "beyin.cli.is_interactive_session",
        return_value=False,
    ) as tty_mock, patch(
        "beyin.cli._run_initial_setup_flow"
    ) as setup_mock, patch(
        "beyin.cli._render_home_screen"
    ) as home_mock:
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert tty_mock.call_count == 2
    setup_mock.assert_not_called()
    home_mock.assert_called_once_with()


def test_explicit_subcommands_skip_the_initial_setup_gate(tmp_path):
    """Explicit commands stay scriptable and do not consult the first-run setup gate."""
    from beyin.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "beyin"

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli.needs_initial_setup",
        side_effect=AssertionError("setup gate should not run"),
    ), patch(
        "beyin.cli.is_interactive_session",
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

    from beyin.cli import app
    from beyin.settings import load_settings

    runner = CliRunner()
    packs_root = tmp_path / "beyin"
    backend = _FakePromptBackend(
        [
            ["web", "youtube", "podcasts"],
            "faster-whisper",
            "small",
            True,
            KeyboardInterrupt(),
        ]
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli.is_interactive_session",
        return_value=True,
    ), patch(
        "beyin.cli.load_prompt_backend",
        return_value=backend,
    ) as load_backend:
        first = runner.invoke(app, [])
        second = runner.invoke(app, [])

    settings = load_settings()

    assert first.exit_code == 0
    assert settings.setup_completed is True
    assert settings.enabled_capabilities == ["web", "youtube", "podcasts"]
    assert f"beyin v{__version__}" in first.output
    assert "Start your first setup now" in first.output
    first_checkbox = next(
        kwargs for prompt_type, kwargs in backend.calls if prompt_type == "checkbox"
    )
    assert first_checkbox["message"] == "Choose what you want to work with"
    assert "[SPACE] Select or unselect items." in first.output
    assert first.output.count("Setup complete") == 1
    assert "Quick start" in first.output
    assert second.exit_code == 0
    assert "Setup complete" not in second.output
    assert "What would you like to do?" in second.output
    assert load_backend.call_count == 2


def test_initial_setup_limits_choices_to_current_machine(monkeypatch, tmp_path):
    """Setup should expose only the valid high-level runtime choices for this machine."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from beyin.interactive import run_initial_setup_flow
    from beyin.settings import load_settings

    backend = _FakePromptBackend(
        [
            ["youtube", "local_files", "local_query"],
            ["pdf", "xlsx"],
            "faster-whisper",
            "small",
            "llama3.2:latest",
            True,
        ]
    )

    with patch("beyin.settings.platform.system", return_value="Linux"), patch(
        "beyin.settings.platform.machine",
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
    assert settings.enabled_capabilities == ["youtube", "local_files", "local_query"]
    assert settings.enabled_local_file_types == ["pdf", "xlsx"]
    assert settings.preferred_transcription_backend == "faster-whisper"
    assert settings.preferred_whisper_model == "small"
    assert settings.preferred_llm_model == "llama3.2:latest"
    assert "mlx-whisper" not in backend_names


def test_settings_command_applies_custom_changes_and_prints_summary(monkeypatch, tmp_path):
    """beyin settings should reuse the guided setup flow and persist saved changes."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from beyin.cli import app
    from beyin.settings import load_settings

    _save_global_settings(
        tmp_path,
        enabled_capabilities=["youtube"],
        preferred_whisper_model="small",
    )
    runner = CliRunner()
    backend = _FakePromptBackend(
        [
            ["youtube", "local_query"],
            "faster-whisper",
            "large",
            "qwen2.5",
            True,
        ]
    )

    with patch("beyin.cli.is_interactive_session", return_value=True), patch(
        "beyin.cli.load_prompt_backend",
        return_value=backend,
    ):
        result = runner.invoke(app, ["settings"])

    settings = load_settings()

    assert result.exit_code == 0
    assert settings.preferred_whisper_model == "large"
    assert settings.preferred_llm_model == "qwen2.5"
    assert settings.enabled_capabilities == ["youtube", "local_query"]
    # Settings table is always shown
    assert "beyin Settings" in result.output
    assert "Setup complete" in result.output


def test_settings_command_whisper_menu_includes_all_models_and_help_text(monkeypatch, tmp_path):
    """TTY settings should expose the same guided Whisper model choices as initial setup."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from beyin.cli import app

    _save_global_settings(tmp_path, enabled_capabilities=["youtube"], preferred_whisper_model="small")
    runner = CliRunner()
    backend = _FakePromptBackend(
        [
            ["youtube"],
            "faster-whisper",
            "small",
            True,
        ]
    )

    with patch("beyin.cli.is_interactive_session", return_value=True), patch(
        "beyin.cli.load_prompt_backend",
        return_value=backend,
    ):
        result = runner.invoke(app, ["settings"])

    assert result.exit_code == 0
    whisper_call = next(
        kwargs
        for prompt_type, kwargs in backend.calls
        if prompt_type == "select" and kwargs["message"] == "Select the default Whisper model"
    )
    values = [choice["value"] for choice in whisper_call["choices"]]
    names = {
        choice["value"]: choice.get("name")
        for choice in whisper_call["choices"]
    }

    assert values == [
        "tiny",
        "tiny.en",
        "base",
        "base.en",
        "small",
        "small.en",
        "medium",
        "medium.en",
        "large",
    ]
    assert "(~75 MB) Fastest. Clean English audio only." in names["tiny"]
    assert "(~75 MB) English-only. Fastest option" in names["tiny.en"]
    assert "(~145 MB) Fast. Simple content and English podcasts." in names["base"]
    assert "(~145 MB) English-only. Better fit" in names["base.en"]
    assert "(~483 MB) Moderate. Strong default" in names["small"]
    assert "(~483 MB) English-only. Strong default" in names["small.en"]


def test_settings_command_shows_table_in_non_tty(
    monkeypatch,
    tmp_path,
):
    """Non-interactive settings invocation shows the current settings table and exits cleanly."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from beyin.cli import app

    _save_global_settings(
        tmp_path,
        enabled_capabilities=["local_files"],
        enabled_local_file_types=["pdf"],
    )
    runner = CliRunner()

    with patch("beyin.cli.is_interactive_session", return_value=False), patch(
        "beyin.cli.load_prompt_backend",
        side_effect=AssertionError("prompt backend should stay unloaded"),
    ):
        result = runner.invoke(app, ["settings"])

    assert result.exit_code == 0
    assert "beyin Settings" in result.output
    assert "Transcription" in result.output
    assert "Dependencies" in result.output
    assert "PDF (.pdf)" in result.output
    assert "beyin settings" in result.output


def test_saved_local_preference_shown_in_home_settings_section(
    monkeypatch,
    tmp_path,
):
    """The home screen settings section reflects the saved local model."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from beyin.cli import app

    _save_global_settings(tmp_path)
    runner = CliRunner()
    packs_root = tmp_path / "beyin"

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "llama3.2" in result.output


def test_cancelled_initial_setup_leaves_settings_missing(monkeypatch, tmp_path):
    """Aborting first-run setup must not leave behind a partial settings file."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from beyin.interactive import run_initial_setup_flow
    from beyin.settings import settings_path

    backend = _FakePromptBackend(
        [
            KeyboardInterrupt(),
        ]
    )

    completed = run_initial_setup_flow(prompt_backend=backend)

    assert completed is False
    assert settings_path().exists() is False


def test_cancelled_settings_edit_preserves_previous_settings(monkeypatch, tmp_path):
    """Aborting a later settings edit should keep the prior settings file untouched."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from beyin.interactive import run_settings_flow
    from beyin.settings import load_settings, settings_path

    _save_global_settings(
        tmp_path,
        preferred_whisper_model="small",
    )
    original = settings_path().read_text()
    backend = _FakePromptBackend(
        [
            ["local_query"],
            "mistral",
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
        module = importlib.import_module("beyin.interactive")
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
        from beyin.interactive import load_prompt_backend

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
    from beyin.interactive import InteractiveAbort, normalize_prompt_abort

    def _raise_abort():
        raise exc_type()

    with pytest.raises(InteractiveAbort):
        normalize_prompt_abort(_raise_abort)


def test_no_arg_interactive_home_routes_to_authoring_menu_after_setup(tmp_path):
    """Interactive no-arg use with no packs installed routes to the authoring menu."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    runner = CliRunner()
    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli.needs_initial_setup", return_value=False
    ), patch(
        "beyin.cli.is_interactive_session",
        return_value=True,
    ), patch(
        "beyin.cli.run_authoring_menu",
        create=True,
        return_value=True,
    ) as menu_mock, patch(
        "beyin.cli._render_home_screen",
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
    from beyin.interactive import run_authoring_menu

    backend = _FakePromptBackend([selection])

    with patch("beyin.interactive.run_create_flow", create=True) as create_mock, patch(
        "beyin.interactive.run_import_flow",
        create=True,
    ) as import_mock, patch(
        "beyin.interactive.run_manage_pack_flow",
        create=True,
    ) as manage_mock:
        completed = run_authoring_menu(
            packs_dir=tmp_path / "beyin",
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


def test_no_arg_tty_with_installed_packs_shows_home_table_not_authoring_menu(tmp_path):
    """TTY with installed packs: inventory table shown directly, authoring menu bypassed."""
    from beyin.cli import app
    from beyin.inventory import pack_config_hash
    from beyin.pack_state import save_state

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "demo-pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        "name: demo-pack\n"
        "description: Demo pack\n"
        "llm: ollama\n"
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
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli.needs_initial_setup", return_value=False
    ), patch(
        "beyin.cli.is_interactive_session", return_value=True
    ), patch(
        "beyin.cli.run_authoring_menu",
        side_effect=AssertionError("authoring menu should not be called when packs exist"),
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Installed packs" in result.output
    assert "demo-pack" in result.output


def test_no_arg_tty_empty_inventory_still_routes_to_authoring_menu(tmp_path):
    """TTY with no packs should still show the authoring menu for first-pack creation."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    runner = CliRunner()

    menu_called = []

    def fake_authoring_menu():
        menu_called.append(True)
        return True

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli.needs_initial_setup", return_value=False
    ), patch(
        "beyin.cli.is_interactive_session", return_value=True
    ), patch(
        "beyin.cli.run_authoring_menu", side_effect=fake_authoring_menu
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert menu_called == [True]


def test_home_screen_with_packs_exposes_lifecycle_management_lines(tmp_pack_root):
    """Home screen with installed packs shows pack table and help footer."""
    from beyin.cli import app

    packs_root, pack_dir = tmp_pack_root
    _mark_pack_ready(pack_dir)
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli._check_ollama_reachable", return_value=True):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    output = result.output
    # Pack table and commands reachable via footer
    assert "Installed packs" in output
    assert "test-pack" in output
    assert "beyin help" in output
