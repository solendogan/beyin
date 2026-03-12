"""Tests for chunker.py — covers PIP-01, PIP-02."""
import pytest


def test_chunk_text_produces_overlapping_windows():
    from brainpack.chunker import chunk_text
    # 10 sentences — with window=5, overlap=2 (step=3) should produce at least 2 chunks
    text = " ".join([f"Sentence {i}." for i in range(10)])
    chunks = chunk_text(text, window=5, overlap=2)
    assert len(chunks) >= 2
    # Overlap: chunk 0 and chunk 1 should share some sentences
    assert any(word in chunks[1] for word in chunks[0].split()[:3])


def test_token_limit():
    from brainpack.chunker import chunk_text
    # A chunk of 300 tokens should be excluded
    long_sentence = "word " * 60  # ~60 tokens per sentence, 5 = ~300 tokens
    text = " ".join([long_sentence] * 5)
    chunks = chunk_text(text, window=5, overlap=2, max_tokens=256)
    # All returned chunks must be <= 256 tokens
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    for chunk in chunks:
        assert len(enc.encode(chunk)) <= 256


def test_single_sentence_returns_one_chunk():
    from brainpack.chunker import chunk_text
    chunks = chunk_text("This is a single sentence.")
    assert len(chunks) == 1


def test_empty_text_returns_empty_list():
    from brainpack.chunker import chunk_text
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_count_tokens_accuracy():
    from brainpack.chunker import count_tokens
    # "hello world" should be 2 tokens in cl100k_base (not 1, not 0)
    result = count_tokens("hello world")
    assert result == 2


def test_overlap_shares_sentences():
    from brainpack.chunker import chunk_text
    # 6 sentences, window=3, overlap=1 => step=2
    # chunk 0: sentences 0,1,2 | chunk 1: sentences 2,3,4 | chunk 2: sentences 4,5
    sentences = [f"This is sentence {i} of the test." for i in range(6)]
    text = " ".join(sentences)
    chunks = chunk_text(text, window=3, overlap=1)
    assert len(chunks) >= 2
    # The last sentence of chunk 0 should appear in chunk 1
    last_word_of_chunk0 = chunks[0].split()[-1]
    assert last_word_of_chunk0 in chunks[1]
