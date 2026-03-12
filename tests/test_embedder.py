"""Tests for embedder.py — covers PIP-04."""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_model(n_chunks: int, dim: int = 384) -> MagicMock:
    """Create a mock SentenceTransformer that returns the correct shape for n_chunks."""
    model = MagicMock()
    model.encode.return_value = np.array([[0.1] * dim] * n_chunks)
    return model


def test_embed_chunks_returns_float_lists():
    from brainpack.embedder import embed_chunks
    chunks = ["Hello world.", "Another sentence."]
    model = _make_mock_model(len(chunks))
    result = embed_chunks(model, chunks)
    assert isinstance(result, list)
    assert len(result) == len(chunks)
    assert all(isinstance(v, float) for v in result[0])


def test_embed_chunks_vector_length():
    from brainpack.embedder import embed_chunks
    chunks = ["Hello."]
    model = _make_mock_model(len(chunks), dim=384)
    result = embed_chunks(model, chunks)
    assert len(result[0]) == 384


def test_embed_chunks_empty_returns_empty():
    from brainpack.embedder import embed_chunks
    model = MagicMock()
    result = embed_chunks(model, [])
    assert result == []
    model.encode.assert_not_called()


def test_load_model_calls_sentence_transformer():
    with patch("brainpack.embedder.SentenceTransformer") as MockST:
        MockST.return_value = MagicMock()
        from brainpack.embedder import load_model
        model = load_model("all-MiniLM-L6-v2")
    MockST.assert_called_once_with("all-MiniLM-L6-v2")
    assert model is not None
