"""Tests for update, origin, and pack lifecycle flows."""
import hashlib
import json
import pytest
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch

from beyin.config import SourceEntry

from tests.conftest import (
    _make_config,
    _mark_pack_ready,
)


def test_update_uses_remembered_origin_and_shows_change_summary(tmp_path):
    """update reloads pack.yaml from the remembered origin and prints config changes."""
    from beyin.cli import app
    from beyin.inventory import load_pack_origin

    runner = CliRunner()
    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "sync-pack"
    pack_dir.mkdir(parents=True)
    source_yaml = tmp_path / "sync-pack.yaml"
    source_yaml.write_text(
        "name: sync-pack\n"
        "description: test\n"
        "llm: anthropic\n"
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

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "sync-pack"])

    assert result.exit_code == 0, result.output
    assert "Updating pack definition:" in result.output
    assert "provider: anthropic -> ollama" in result.output
    assert "sources: 1 -> 2" in result.output
    mock_build.assert_called_once()
    origin = load_pack_origin(pack_dir)
    assert "provider: anthropic -> ollama" in origin["last_update_summary"]


def test_update_with_remembered_origin_fetches_and_rebuilds(tmp_path):
    """beyin update refreshes pack.yaml from origin and rebuilds when the definition changed."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
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

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_pack_origin", return_value={
             "source": "https://example.com/pack.yaml",
             "type": "url",
             "resolved": "https://example.com/pack.yaml",
         }), \
         patch("beyin.cli.resolve_pack_origin", return_value={
             "source": "https://example.com/pack.yaml",
             "type": "url",
             "resolved": "https://example.com/pack.yaml",
         }) as mock_resolve, \
         patch("beyin.cli._write_pack_yaml_from_source", side_effect=_fake_write), \
         patch("beyin.cli.save_pack_origin"), \
         patch("beyin.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "test-pack"])

    assert result.exit_code == 0, result.output
    mock_resolve.assert_called_once()
    mock_build.assert_called_once()


def test_update_with_unchanged_remembered_origin_skips_rebuild_and_reports_runtime(tmp_path):
    """beyin update should not rebuild when the synced remote definition is unchanged."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
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

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_pack_origin", return_value={
             "source": "https://example.com/pack.yaml",
             "type": "url",
             "resolved": "https://example.com/pack.yaml",
         }), \
         patch("beyin.cli.resolve_pack_origin", return_value={
             "source": "https://example.com/pack.yaml",
             "type": "url",
             "resolved": "https://example.com/pack.yaml",
         }), \
         patch("beyin.cli._write_pack_yaml_from_source", side_effect=_fake_write), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.save_pack_origin"), \
         patch("beyin.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "test-pack"])

    assert result.exit_code == 0, result.output
    mock_build.assert_not_called()
    assert "definition is already current" in result.output.lower()
    assert "runtime status" in result.output.lower()


def test_update_blocks_when_local_and_origin_both_changed(tmp_path):
    """update should refuse to overwrite local edits when origin also changed."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    local_yaml = (
        "name: test-pack\ndescription: Local edit\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    last_synced_yaml = (
        "name: test-pack\ndescription: Old sync\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    upstream_yaml = (
        "name: test-pack\ndescription: Upstream changed\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "  - https://example.com/new\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    (pack_dir / "pack.yaml").write_text(local_yaml)
    source_yaml = tmp_path / "remote-pack.yaml"
    source_yaml.write_text(upstream_yaml)

    from beyin.inventory import pack_file_hash

    (pack_dir / "origin.json").write_text(
        json.dumps(
            {
                "type": "file",
                "source": str(source_yaml.resolve()),
                "resolved": str(source_yaml.resolve()),
                "last_source_hash": pack_file_hash(source_yaml),
                "last_synced_pack_hash": hashlib.sha1(last_synced_yaml.encode("utf-8")).hexdigest(),
            }
        )
    )
    source_yaml.write_text(upstream_yaml.replace("Upstream changed", "Upstream changed again"))
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "test-pack"])

    assert result.exit_code == 1
    assert "local changes" in result.output.lower()
    assert "avoid overwriting local edits" in result.output.lower()
    mock_build.assert_not_called()


def test_update_with_local_divergence_and_unchanged_origin_reports_local_edits(tmp_path):
    """update should report local divergence when origin has no new changes."""
    from beyin.cli import app
    from beyin.inventory import pack_file_hash

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    local_yaml = (
        "name: test-pack\ndescription: Local edit\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    last_synced_yaml = (
        "name: test-pack\ndescription: Old sync\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    (pack_dir / "pack.yaml").write_text(local_yaml)
    source_yaml = tmp_path / "remote-pack.yaml"
    source_yaml.write_text(last_synced_yaml)
    (pack_dir / "origin.json").write_text(
        json.dumps(
            {
                "type": "file",
                "source": str(source_yaml.resolve()),
                "resolved": str(source_yaml.resolve()),
                "last_source_hash": pack_file_hash(source_yaml),
                "last_synced_pack_hash": hashlib.sha1(last_synced_yaml.encode("utf-8")).hexdigest(),
            }
        )
    )
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "test-pack"])

    assert result.exit_code == 0
    assert "origin for 'test-pack' is already current" in result.output.lower()
    assert "differs from the last synced origin" in result.output.lower()
    mock_build.assert_not_called()


def test_update_without_remembered_origin_says_no_remote_refresh(tmp_path):
    """beyin update with no stored origin reports runtime state and does not rebuild."""
    from beyin.cli import app

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "test-pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: test-pack\ndescription: Test\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )

    mock_config = _make_config([SourceEntry(url="https://example.com/article")])
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.load_pack_origin", return_value={}), \
         patch("beyin.cli.load_config", return_value=mock_config), \
         patch("beyin.cli.load_state", return_value={"embedding_model": None, "processed": {}}), \
         patch("beyin.cli.build") as mock_build:
        result = runner.invoke(app, ["update", "test-pack"])

    assert result.exit_code == 0
    mock_build.assert_not_called()
    output = result.output.lower()
    assert (
        "no remembered remote origin" in output
        or "no remote origin" in output
    ), f"Expected a note about no remote refresh, got: {result.output!r}"
    assert "runtime status" in output
    assert "next step: beyin build test-pack" in output


def test_status_warns_when_pack_diverged_from_origin(tmp_path):
    """status should warn when local pack.yaml changed since the last synced origin."""
    from beyin.cli import app
    from beyin.inventory import pack_file_hash

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "diverged-pack"
    pack_dir.mkdir(parents=True)
    current_yaml = (
        "name: diverged-pack\ndescription: local\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
    )
    old_yaml = (
        "name: diverged-pack\ndescription: upstream\nllm: ollama\nsources:\n"
        "  - https://example.com/article\n"
    )
    (pack_dir / "pack.yaml").write_text(current_yaml)
    (pack_dir / "origin.json").write_text(
        json.dumps(
            {
                "type": "file",
                "source": "/tmp/diverged-pack.yaml",
                "last_synced_pack_hash": hashlib.sha1(old_yaml.encode("utf-8")).hexdigest(),
                "last_source_hash": pack_file_hash(pack_dir / "pack.yaml"),
            }
        )
    )
    runner = CliRunner()

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["status", "diverged-pack"])

    assert result.exit_code == 0
    assert "differs from the last synced origin" in result.output.lower()


# ---------------------------------------------------------------------------
# PCK-03 + CLI-04: update command tests (TDD RED phase)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False)
def test_update_existing_pack(tmp_path):
    """update <pack> delegates to build and exits 0 when pack dir exists."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    pack_dir = packs_root / "mypack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "name: mypack\ndescription: x\nllm: ollama\nsources:\n  - https://example.com\n"
    )

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.build") as mock_build:
        mock_build.return_value = None
        result = runner.invoke(app, ["update", "mypack"])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
    mock_build.assert_called_once()


@pytest.mark.xfail(strict=False)
def test_update_pack_not_found(tmp_path):
    """update exits 1 with 'not found' and 'beyin install' when pack dir missing."""
    from beyin.cli import app
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    # Do NOT create the pack dir

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["update", "nonexistent"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()
    assert "beyin install" in result.output


# ---------------------------------------------------------------------------
# PCK-02 + CLI-03: install command tests (TDD RED phase)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False)
def test_install_local_success(tmp_path):
    """install <local-path> copies pack.yaml to ~/.beyin/<name>/pack.yaml and exits 0."""
    from beyin.cli import app
    from unittest.mock import MagicMock
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
    packs_root = tmp_path / "beyin"

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.shutil") as mock_shutil:
        mock_shutil.copy2 = MagicMock()
        result = runner.invoke(app, ["install", str(yaml_file)])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"
    assert "test-pack" in result.output


@pytest.mark.xfail(strict=False)
def test_install_already_exists(tmp_path):
    """install exits 1 with 'already installed' and 'beyin update' suggestion when dest exists."""
    from beyin.cli import app
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
    packs_root = tmp_path / "beyin"
    dest_dir = packs_root / "test-pack"
    dest_dir.mkdir(parents=True)

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["install", str(yaml_file)])

    assert result.exit_code == 1
    assert "already installed" in result.output
    assert "beyin update" in result.output


@pytest.mark.xfail(strict=False)
def test_install_remote_url(tmp_path):
    """install https://example.com/pack.yaml downloads, validates, and exits 0."""
    from beyin.cli import app
    from unittest.mock import MagicMock
    runner = CliRunner()

    packs_root = tmp_path / "beyin"
    valid_yaml = (
        "name: remote-pack\n"
        "description: remote\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )

    def fake_urlretrieve(url, tmp_file):
        Path(tmp_file).write_text(valid_yaml)

    with patch("beyin.cli._PACKS_DIR", packs_root), \
         patch("beyin.cli.urllib.request.urlretrieve", side_effect=fake_urlretrieve), \
         patch("beyin.cli.shutil") as mock_shutil:
        mock_shutil.copy2 = MagicMock()
        result = runner.invoke(app, ["install", "https://example.com/pack.yaml"])

    assert result.exit_code == 0, f"Exit: {result.exit_code}, output: {result.output}"


@pytest.mark.xfail(strict=False)
def test_install_file_not_found(tmp_path):
    """install exits 1 with 'not found' for a nonexistent local path."""
    from beyin.cli import app
    runner = CliRunner()

    result = runner.invoke(app, ["install", "/nonexistent/path/pack.yaml"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_add_local_pack_stores_origin_metadata(tmp_path):
    """add stores local-file provenance next to the installed pack."""
    from beyin.cli import app
    from beyin.inventory import load_pack_origin

    runner = CliRunner()
    packs_root = tmp_path / "beyin"
    yaml_file = tmp_path / "pack.yaml"
    yaml_file.write_text(
        "name: added-pack\n"
        "description: test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["add", str(yaml_file)])

    assert result.exit_code == 0, result.output
    origin = load_pack_origin(packs_root / "added-pack")
    assert origin["type"] == "file"
    assert origin["source"] == str(yaml_file.resolve())


def test_add_marketplace_id_uses_local_mapping(tmp_path):
    """add resolves marketplace-style ids through the local mapping file."""
    from beyin.cli import app
    from beyin.inventory import load_pack_origin, marketplace_mapping_path

    runner = CliRunner()
    packs_root = tmp_path / "beyin"
    packs_root.mkdir()
    yaml_file = tmp_path / "remote-pack.yaml"
    yaml_file.write_text(
        "name: mapped-pack\n"
        "description: mapped\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )
    marketplace_mapping_path(packs_root).write_text(
        json.dumps({"starter-pack": str(yaml_file.resolve())})
    )

    with patch("beyin.cli._PACKS_DIR", packs_root):
        result = runner.invoke(app, ["add", "starter-pack"])

    assert result.exit_code == 0, result.output
    origin = load_pack_origin(packs_root / "mapped-pack")
    assert origin["type"] == "id"
    assert origin["source"] == "starter-pack"
