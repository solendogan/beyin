"""Tests for config.py — covers PCK-01."""
import pytest
from pathlib import Path


def test_load_config_returns_packconfig(tmp_pack_dir):
    from brainpack.config import load_config, PackConfig
    config = load_config(tmp_pack_dir)
    assert isinstance(config, PackConfig)
    assert config.name == "test-pack"
    assert config.description == "Test pack"
    assert config.llm == "ollama"
    assert config.embedding_model == "all-MiniLM-L6-v2"
    assert "https://example.com/article" in config.sources


def test_load_config_default_embedding_model(tmp_path):
    """embedding_model defaults to all-MiniLM-L6-v2 when not specified."""
    from brainpack.config import load_config
    pack_dir = tmp_path / "no-model-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: minimal\n"
        "description: Minimal pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
    )
    config = load_config(pack_dir)
    assert config.embedding_model == "all-MiniLM-L6-v2"


def test_load_config_raises_if_missing(tmp_path):
    """load_config raises FileNotFoundError if pack.yaml does not exist."""
    from brainpack.config import load_config
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent")
