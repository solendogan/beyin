"""Tests for config.py — covers PCK-01, ING-01, ING-02."""
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
    # sources are now SourceEntry objects — check via .url
    assert config.sources[0].url == "https://example.com/article"


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


def test_sources_as_plain_strings_normalized_to_source_entry(tmp_path):
    """Plain string sources become SourceEntry(url=s, limit=None)."""
    from brainpack.config import load_config, SourceEntry
    pack_dir = tmp_path / "str-sources"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test\n"
        "description: test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/a\n"
        "  - https://example.com/b\n"
    )
    config = load_config(pack_dir)
    assert len(config.sources) == 2
    assert isinstance(config.sources[0], SourceEntry)
    assert config.sources[0].url == "https://example.com/a"
    assert config.sources[0].limit is None
    assert config.sources[1].url == "https://example.com/b"
    assert config.sources[1].limit is None


def test_sources_as_object_normalized_to_source_entry(tmp_path):
    """Object source {url: ..., limit: 50} becomes SourceEntry(url=..., limit=50)."""
    from brainpack.config import load_config, SourceEntry
    pack_dir = tmp_path / "obj-sources"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test\n"
        "description: test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - url: https://example.com/feed\n"
        "    limit: 50\n"
    )
    config = load_config(pack_dir)
    assert len(config.sources) == 1
    assert isinstance(config.sources[0], SourceEntry)
    assert config.sources[0].url == "https://example.com/feed"
    assert config.sources[0].limit == 50


def test_sources_mixed_formats_normalized(tmp_path):
    """Mixed sources (string + object) both normalized to SourceEntry."""
    from brainpack.config import load_config, SourceEntry
    pack_dir = tmp_path / "mixed-sources"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test\n"
        "description: test\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/str\n"
        "  - url: https://example.com/obj\n"
        "    limit: 10\n"
    )
    config = load_config(pack_dir)
    assert len(config.sources) == 2
    assert config.sources[0].url == "https://example.com/str"
    assert config.sources[0].limit is None
    assert config.sources[1].url == "https://example.com/obj"
    assert config.sources[1].limit == 10


def test_whisper_model_explicit(tmp_path):
    """whisper_model: medium → config.whisper_model == 'medium'."""
    from brainpack.config import load_config
    pack_dir = tmp_path / "whisper-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test\n"
        "description: test\n"
        "llm: ollama\n"
        "sources: []\n"
        "whisper_model: medium\n"
    )
    config = load_config(pack_dir)
    assert config.whisper_model == "medium"


def test_whisper_model_default(tmp_path):
    """whisper_model defaults to 'small' when not specified."""
    from brainpack.config import load_config
    pack_dir = tmp_path / "no-whisper-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test\n"
        "description: test\n"
        "llm: ollama\n"
        "sources: []\n"
    )
    config = load_config(pack_dir)
    assert config.whisper_model == "small"


def test_episode_limit_explicit(tmp_path):
    """episode_limit: 10 → config.episode_limit == 10."""
    from brainpack.config import load_config
    pack_dir = tmp_path / "ep-limit-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test\n"
        "description: test\n"
        "llm: ollama\n"
        "sources: []\n"
        "episode_limit: 10\n"
    )
    config = load_config(pack_dir)
    assert config.episode_limit == 10


def test_episode_limit_default(tmp_path):
    """episode_limit defaults to 20 when not specified."""
    from brainpack.config import load_config
    pack_dir = tmp_path / "no-ep-limit-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test\n"
        "description: test\n"
        "llm: ollama\n"
        "sources: []\n"
    )
    config = load_config(pack_dir)
    assert config.episode_limit == 20


def test_episode_limit_null_means_unlimited(tmp_path):
    """episode_limit: null → config.episode_limit is None (unlimited)."""
    from brainpack.config import load_config
    pack_dir = tmp_path / "unlimited-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "name: test\n"
        "description: test\n"
        "llm: ollama\n"
        "sources: []\n"
        "episode_limit: null\n"
    )
    config = load_config(pack_dir)
    assert config.episode_limit is None
