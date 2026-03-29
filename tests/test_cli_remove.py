"""Tests for the remove pack command."""
import pytest
from typer.testing import CliRunner
from unittest.mock import patch


def test_remove_command_exists_and_deletes_only_target_pack(tmp_path):
    """beyin remove <pack> is a first-class command that deletes only the target installed pack."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
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

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["remove", "test-pack", "--yes"])

    assert result.exit_code == 0
    assert not pack_dir.exists(), "target pack should be deleted"
    assert other_dir.exists(), "other packs must not be touched"


def test_remove_command_uses_explicit_destructive_wording(tmp_path):
    """beyin remove output must include explicit destructive wording."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["remove", "test-pack", "--yes"])

    assert result.exit_code == 0
    output = result.output.lower()
    assert "removed" in output or "deleted" in output


def test_remove_command_requires_yes_or_force_in_non_interactive_use(tmp_path):
    """beyin remove in non-interactive use (no TTY) must require --yes/--force to proceed."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    runner = CliRunner()

    # Non-interactive with no --yes should abort without deleting
    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.is_interactive_session", return_value=False):
        result = runner.invoke(app, ["remove", "test-pack"])

    assert result.exit_code != 0 or pack_dir.exists(), (
        "remove without --yes in non-interactive session should abort or keep the pack"
    )


def test_remove_nonexistent_pack_fails_with_clear_message(tmp_path):
    """beyin remove on a missing pack should exit non-zero with a clear message."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    packs_root.mkdir(parents=True)
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["remove", "ghost-pack", "--yes"])

    assert result.exit_code != 0
    assert "ghost-pack" in result.output.lower() or "ghost-pack" in (result.stderr or "").lower()
