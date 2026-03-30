"""Sentence embedding runtime with a lightweight FastEmbed-first backend."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from threading import Lock
from typing import Any

_MODEL_CACHE: dict[str, Any] = {}
_MODEL_CACHE_LOCK = Lock()

_FASTEMBED_MODEL_ALIASES = {
    "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
    "paraphrase-multilingual-mpnet-base-v2": (
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    ),
    "paraphrase-multilingual-MiniLM-L12-v2": (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    ),
}


def _silence_model_load_logs() -> None:
    """Keep model bootstrap chatter out of the user-facing CLI."""
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


def _to_float_list(vector: Any) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(value) for value in vector]


class _SentenceTransformersAdapter:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.backend = "sentence-transformers"
        self._model = SentenceTransformer(model_name)

    def encode(self, inputs: str | list[str]) -> list[float] | list[list[float]]:
        is_single = isinstance(inputs, str)
        items = [inputs] if is_single else list(inputs)
        encoded = self._model.encode(items, show_progress_bar=False)
        rows = encoded.tolist() if hasattr(encoded, "tolist") else encoded
        rows = [[float(value) for value in row] for row in rows]
        return rows[0] if is_single else rows


class _FastEmbedAdapter:
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self.model_name = model_name
        self.backend = "fastembed"
        self._resolved_model_name = _FASTEMBED_MODEL_ALIASES.get(model_name, model_name)
        self._model = TextEmbedding(model_name=self._resolved_model_name)

    def encode(self, inputs: str | list[str]) -> list[float] | list[list[float]]:
        is_single = isinstance(inputs, str)
        items = [inputs] if is_single else list(inputs)
        rows = [_to_float_list(vector) for vector in self._model.embed(items)]
        return rows[0] if is_single else rows


def _load_fastembed_model(model_name: str) -> Any:
    sink = StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        return _FastEmbedAdapter(model_name)


def _load_sentence_transformers_model(model_name: str) -> Any:
    sink = StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        return _SentenceTransformersAdapter(model_name)


def load_model(model_name: str = "all-MiniLM-L6-v2") -> Any:
    """Load an embedding model adapter, preferring FastEmbed over PyTorch."""
    _silence_model_load_logs()

    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(model_name)
        if cached is not None:
            return cached

        load_errors: list[Exception] = []
        for loader in (_load_fastembed_model, _load_sentence_transformers_model):
            try:
                model = loader(model_name)
            except ImportError as exc:
                load_errors.append(exc)
                continue
            except Exception as exc:
                load_errors.append(exc)
                continue

            _MODEL_CACHE[model_name] = model
            return model

    hints = [
        "Install `fastembed` for the lightweight default embedding runtime.",
        "Or install `sentence-transformers` to use the legacy PyTorch embedding path.",
    ]
    if load_errors:
        detail = f"Last error: {load_errors[-1]}"
    else:
        detail = "No embedding backend could be loaded."
    raise RuntimeError(f"{detail}\n" + "\n".join(hints))


def embed_chunks(model: Any, chunks: list[str]) -> list[list[float]]:
    """
    Embed a list of text chunks using the provided model.

    Returns a list of embedding vectors (one per chunk) as Python float lists.
    Empty input returns empty list and does not touch the backend runtime.
    """
    if not chunks:
        return []

    embeddings = model.encode(chunks)
    return [_to_float_list(row) for row in embeddings]
