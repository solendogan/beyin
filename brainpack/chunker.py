"""Sliding-window text chunker with token-count guard."""
from typing import List

import nltk
import tiktoken

# Initialize tokenizer once at module level (no network call — data already installed)
_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in text using cl100k_base encoding."""
    return len(_enc.encode(text))


def chunk_text(
    text: str,
    window: int = 5,
    overlap: int = 2,
    max_tokens: int = 256,
) -> List[str]:
    """
    Split text into overlapping sentence windows.

    Strategy (PIP-01):
    - Tokenize text into sentences using NLTK punkt_tab
    - Slide a window of `window` sentences with step = window - overlap
    - Measure each window in tokens (tiktoken cl100k_base)
    - Exclude windows exceeding max_tokens (PIP-02 token guard)

    Default: window=5, overlap=2 -> step=3 sentences per advance.
    """
    if not text or not text.strip():
        return []

    sentences = nltk.sent_tokenize(text)
    if not sentences:
        return []

    step = window - overlap
    if step <= 0:
        step = 1  # defensive: prevent infinite loop

    chunks = []
    for i in range(0, len(sentences), step):
        window_sents = sentences[i : i + window]
        chunk = " ".join(window_sents)
        token_count = count_tokens(chunk)
        if token_count <= max_tokens:
            chunks.append(chunk)
        # Over limit: try a smaller slice (3 sentences) before discarding entirely
        elif len(window_sents) > 3:
            smaller = " ".join(window_sents[:3])
            if count_tokens(smaller) <= max_tokens:
                chunks.append(smaller)
        # If even 3 sentences exceed max_tokens, discard — these are pathological inputs

    return chunks
