"""Tests for the global Brainpack settings seam."""

import json
from unittest.mock import patch

import pytest


def test_load_settings_uses_defaults_when_file_is_missing(monkeypatch, tmp_path):
    """Missing settings.json should load one versioned default settings object."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.settings import load_settings, settings_path

    settings = load_settings()

    assert settings.version == 1
    assert settings.setup_completed is False
    assert settings.preferred_mode == "agent"
    assert settings.audio_enabled_by_default is True
    assert settings.preferred_transcription_backend in {"mlx-whisper", "faster-whisper"}
    assert settings_path() == tmp_path / ".brainpacks" / "settings.json"


def test_load_settings_migrates_partial_documents_without_crashing(monkeypatch, tmp_path):
    """Older or partial settings documents should merge with defaults safely."""
    monkeypatch.setenv("HOME", str(tmp_path))

    settings_file = tmp_path / ".brainpacks" / "settings.json"
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text(json.dumps({"preferred_mode": "local"}))

    from brainpack.settings import load_settings, needs_initial_setup

    settings = load_settings()

    assert settings.version == 1
    assert settings.preferred_mode == "local"
    assert settings.setup_completed is False
    assert needs_initial_setup() is True


def test_save_settings_round_trips_a_versioned_document(monkeypatch, tmp_path):
    """Saving settings should persist a versioned JSON document and load it back."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.settings import BrainpackSettings, load_settings, save_settings, settings_path

    save_settings(
        BrainpackSettings(
            version=1,
            setup_completed=True,
            preferred_mode="both",
            audio_enabled_by_default=False,
            preferred_transcription_backend="faster-whisper",
            preferred_whisper_model="medium",
            preferred_local_provider="openai",
        )
    )

    raw = json.loads(settings_path().read_text())
    loaded = load_settings()

    assert raw["version"] == 1
    assert raw["setup_completed"] is True
    assert raw["preferred_mode"] == "both"
    assert loaded == BrainpackSettings(**raw)
    assert loaded.preferred_whisper_model == "medium"


def test_save_settings_uses_atomic_replace_and_cleans_up_failed_temp_files(
    monkeypatch,
    tmp_path,
):
    """A failed atomic replace should preserve the previous file and leave no temp files."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from brainpack.settings import BrainpackSettings, save_settings, settings_path

    save_settings(
        BrainpackSettings(
            version=1,
            setup_completed=True,
            preferred_mode="agent",
            audio_enabled_by_default=True,
            preferred_transcription_backend="faster-whisper",
            preferred_whisper_model="small",
            preferred_local_provider="ollama",
        )
    )
    original = settings_path().read_text()

    with patch("brainpack.settings.os.replace", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            save_settings(
                BrainpackSettings(
                    version=1,
                    setup_completed=True,
                    preferred_mode="local",
                    audio_enabled_by_default=False,
                    preferred_transcription_backend="faster-whisper",
                    preferred_whisper_model="large",
                    preferred_local_provider="openai",
                )
            )

    settings_dir = settings_path().parent

    assert settings_path().read_text() == original
    assert sorted(path.name for path in settings_dir.iterdir()) == ["settings.json"]
