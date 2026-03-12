"""Sentence embedding using sentence-transformers."""
from typing import List

from sentence_transformers import SentenceTransformer


def load_model(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    """
    Load a SentenceTransformer model by name.

    First call downloads model weights (~90 MB for all-MiniLM-L6-v2) to
    ~/.cache/huggingface/. Subsequent calls use cached weights.
    """
    return SentenceTransformer(model_name)


def embed_chunks(model: SentenceTransformer, chunks: List[str]) -> List[List[float]]:
    """
    Embed a list of text chunks using the provided model.

    Returns a list of embedding vectors (one per chunk) as Python float lists.
    Empty input returns empty list — no model call made.

    Note: chunk_text() guarantees all inputs are <= 256 tokens, so no silent
    truncation occurs here. The token guard lives in chunker.py, not here.
    """
    if not chunks:
        return []
    embeddings = model.encode(chunks, show_progress_bar=False)
    return embeddings.tolist()
