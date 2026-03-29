"""Tests for pack create, add, manage, remove-source commands."""
import json
import pytest
import yaml
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch

from beyin.config import SourceEntry, load_config

from tests.conftest import _FakePromptBackend


def test_create_writes_public_pack_yaml_shape(tmp_path):
    """create should write the cleaner public manifest shape for new packs."""
    from beyin.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "beyin"

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(
            app,
            ["create"],
            input="https://example.com/article\nmy-pack\nA clean manifest\n",
        )

    assert result.exit_code == 0, result.output
    raw = (packs_root / "my-pack" / "pack.yaml").read_text()
    assert "id: my-pack" in raw
    assert "name: my-pack" in raw
    assert "description: A clean manifest" in raw
    assert "sources:" in raw
    assert "- url: https://example.com/article" in raw
    assert "llm:" not in raw
    assert "embedding_model:" not in raw
    assert "episode_limit:" not in raw


def test_create_command_asks_source_input_first_and_writes_local_text_source(tmp_path):
    """create should start from a source URL/path prompt and persist local text paths as sources."""
    from beyin.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "beyin"
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

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli.is_interactive_session",
        return_value=True,
    ), patch(
        "beyin.cli.load_prompt_backend",
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
    assert raw["sources"] == [{"url": str(local_source)}]
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


def test_create_command_accepts_local_media_source(tmp_path):
    """create should accept local media paths as supported source inputs."""
    from beyin.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "beyin"
    local_source = tmp_path / "clip.mp4"
    local_source.write_bytes(b"x" * 20_000)
    backend = _FakePromptBackend(
        [
            str(local_source),
            "media-pack",
            "Creator clip",
            True,
        ]
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), patch(
        "beyin.cli.is_interactive_session",
        return_value=True,
    ), patch(
        "beyin.cli.load_prompt_backend",
        return_value=backend,
    ):
        result = runner.invoke(app, ["create"])

    assert result.exit_code == 0
    config = load_config(packs_root / "media-pack")
    assert config.sources == [SourceEntry(url=str(local_source))]


def test_add_rejects_local_text_path_as_pack_import(tmp_path):
    """add remains import-only and should not reinterpret a local text file as pack authoring input."""
    from beyin.cli import app

    runner = CliRunner()
    packs_root = tmp_path / "beyin"
    local_source = tmp_path / "notes.txt"
    local_source.write_text("plain text source")

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["add", str(local_source)])

    assert result.exit_code == 1
    assert "Invalid pack.yaml" in result.output


def test_manage_flow_can_edit_basic_metadata_and_add_source(tmp_path):
    """Manage flow should update description and add a local text-like source without manual YAML edits."""
    from beyin.config import write_config, PackConfig
    from beyin.interactive import run_manage_pack_flow

    packs_root = tmp_path / "beyin"
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
    from beyin.config import write_config, PackConfig
    from beyin.interactive import run_manage_pack_flow

    packs_root = tmp_path / "beyin"
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


def test_remove_source_command_removes_by_index(tmp_path):
    """remove-source should drop the selected current source index and preserve the others."""
    from beyin.cli import app
    from beyin.config import PackConfig, write_config

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    write_config(
        PackConfig(
            id="test-pack",
            name="test-pack",
            description="Test pack",
            llm="ollama",
            sources=[
                SourceEntry(url="https://example.com/article-1", title="Article One"),
                SourceEntry(url="https://example.com/article-2", title="Article Two"),
                SourceEntry(url=str(tmp_path / "notes.md"), title="Local Notes"),
            ],
        ),
        pack_dir / "pack.yaml",
    )

    runner = CliRunner()
    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["remove-source", "test-pack", "2"])

    config = load_config(pack_dir)

    assert result.exit_code == 0, result.output
    assert "Removed 1 source(s)" in result.output
    assert [source.url for source in config.sources] == [
        "https://example.com/article-1",
        str(tmp_path / "notes.md"),
    ]


def test_remove_source_command_removes_by_text_match(tmp_path):
    """remove-source should allow matching a source by visible title text."""
    from beyin.cli import app
    from beyin.config import PackConfig, write_config

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    write_config(
        PackConfig(
            id="test-pack",
            name="test-pack",
            description="Test pack",
            llm="ollama",
            sources=[
                SourceEntry(url="https://example.com/article-1", title="Winning Paywalls"),
                SourceEntry(url="https://example.com/article-2", title="Meta Ads Guide"),
            ],
        ),
        pack_dir / "pack.yaml",
    )

    runner = CliRunner()
    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["remove-source", "test-pack", "meta ads"])

    config = load_config(pack_dir)

    assert result.exit_code == 0, result.output
    assert [source.url for source in config.sources] == [
        "https://example.com/article-1",
    ]
