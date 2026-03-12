"""Tests for store.py — covers PIP-03, PIP-05."""
import pytest


def test_persistence(tmp_pack_dir):
    """get_collection creates pack_dir/chroma/ directory and returns a collection."""
    from brainpack.store import get_collection
    col = get_collection(tmp_pack_dir, "test-pack")
    assert col is not None
    # Collection directory is created under pack_dir/chroma
    assert (tmp_pack_dir / "chroma").exists()


def test_get_collection_idempotent(tmp_pack_dir):
    """get_collection called twice returns collections with the same name."""
    from brainpack.store import get_collection
    col1 = get_collection(tmp_pack_dir, "test-pack")
    col2 = get_collection(tmp_pack_dir, "test-pack")
    assert col1.name == col2.name


def test_metadata(tmp_pack_dir, mock_model):
    """embed_and_store stores chunks with url and title in metadata; fields are retrievable."""
    from brainpack.store import get_collection, embed_and_store
    col = get_collection(tmp_pack_dir, "test-pack")
    chunks = ["Test chunk."]
    metadatas = [{"url": "https://example.com", "title": "Example"}]
    embed_and_store(col, mock_model, chunks, metadatas, url="https://example.com")
    results = col.get(include=["metadatas"])
    assert results["metadatas"][0]["url"] == "https://example.com"
    assert results["metadatas"][0]["title"] == "Example"


def test_embed_and_store_returns_count(tmp_pack_dir, mock_model):
    """embed_and_store returns the number of newly added chunks on first call."""
    from brainpack.store import get_collection, embed_and_store
    col = get_collection(tmp_pack_dir, "test-pack")
    chunks = ["Chunk one.", "Chunk two."]
    metadatas = [
        {"url": "https://example.com", "title": "Example"},
        {"url": "https://example.com", "title": "Example"},
    ]
    import numpy as np
    mock_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384])
    count = embed_and_store(col, mock_model, chunks, metadatas, url="https://example.com")
    assert count == 2


def test_embed_and_store_idempotent(tmp_pack_dir, mock_model):
    """embed_and_store called twice with same URL returns 0 on second call."""
    from brainpack.store import get_collection, embed_and_store
    col = get_collection(tmp_pack_dir, "test-pack")
    chunks = ["Test chunk."]
    metadatas = [{"url": "https://example.com", "title": "Example"}]
    first = embed_and_store(col, mock_model, chunks, metadatas, url="https://example.com")
    assert first == 1
    second = embed_and_store(col, mock_model, chunks, metadatas, url="https://example.com")
    assert second == 0


def test_chunk_id_format(tmp_pack_dir, mock_model):
    """Chunk IDs are deterministic and formatted as '{url}::chunk::{i}'."""
    from brainpack.store import get_collection, embed_and_store
    col = get_collection(tmp_pack_dir, "test-pack")
    url = "https://example.com/article"
    chunks = ["First chunk.", "Second chunk."]
    metadatas = [
        {"url": url, "title": "Article"},
        {"url": url, "title": "Article"},
    ]
    import numpy as np
    mock_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384])
    embed_and_store(col, mock_model, chunks, metadatas, url=url)
    results = col.get(include=["documents"])
    ids = results["ids"]
    assert f"{url}::chunk::0" in ids
    assert f"{url}::chunk::1" in ids
