"""Shared test fixtures for brainpack tests.

Note: punkt_tab NLTK data must be downloaded once before running tests.
Run: uv run python -c "import nltk; nltk.download('punkt_tab', quiet=True)"
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


@pytest.fixture
def tmp_pack_dir(tmp_path):
    """A temporary pack directory with a minimal pack.yaml."""
    pack_dir = tmp_path / "test-pack"
    pack_dir.mkdir()
    pack_yaml = pack_dir / "pack.yaml"
    pack_yaml.write_text(
        "name: test-pack\n"
        "description: Test pack\n"
        "llm: ollama\n"
        "sources:\n"
        "  - https://example.com/article\n"
        "embedding_model: all-MiniLM-L6-v2\n"
    )
    return pack_dir


@pytest.fixture
def pack_state_with_model(tmp_pack_dir):
    """A pack directory with meta.json containing embedding_model set."""
    state = {
        "embedding_model": "all-MiniLM-L6-v2",
        "processed": {},
    }
    (tmp_pack_dir / "meta.json").write_text(json.dumps(state))
    return tmp_pack_dir


@pytest.fixture
def mock_model():
    """A mock SentenceTransformer that returns deterministic float embeddings."""
    import numpy as np
    model = MagicMock()
    model.encode.return_value = np.array([[0.1] * 384])
    return model


@pytest.fixture
def mock_openai_client():
    """A mock OpenAI client that returns a canned LLM response."""
    client = MagicMock()
    choice = MagicMock()
    choice.message.content = "Test answer. Sources: [1] Example Article"
    client.chat.completions.create.return_value = MagicMock(choices=[choice])
    return client
