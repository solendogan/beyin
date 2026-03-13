"""Sentence embedding using sentence-transformers."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Any, List

SentenceTransformer = None


def load_model(model_name: str = "all-MiniLM-L6-v2") -> Any:
    """
    Load a SentenceTransformer model by name.

    First call downloads model weights (~90 MB for all-MiniLM-L6-v2) to
    ~/.cache/huggingface/. Subsequent calls use cached weights.
    """
    global SentenceTransformer
    if SentenceTransformer is None:
        from sentence_transformers import SentenceTransformer as _SentenceTransformer

        SentenceTransformer = _SentenceTransformer

    # Keep model-loading chatter out of the user-facing CLI.
    try:
        from huggingface_hub.utils import logging as hf_logging

        hf_logging.set_verbosity_error()
    except Exception:
        pass

    try:
        from transformers.utils import logging as transformers_logging

        transformers_logging.set_verbosity_error()
    except Exception:
        pass

    sink = StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        return SentenceTransformer(model_name)


def embed_chunks(model: Any, chunks: List[str]) -> List[List[float]]:
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
