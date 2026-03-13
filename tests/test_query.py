"""Tests for query.py — covers QRY-01, QRY-02, QRY-03, QRY-04, QRY-05, QRY-06."""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_ollama_config():
    from brainpack.query import _provider_settings
    base_url, api_key = _provider_settings("ollama")
    assert base_url == "http://localhost:11434/v1"
    assert api_key == "ollama"


def test_provider_routing():
    from brainpack.query import _provider_settings
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        base_url, api_key = _provider_settings("openai")
    assert "openai.com" in base_url
    assert api_key == "sk-test"


def test_anthropic_raises():
    from brainpack.query import _provider_settings
    with pytest.raises(NotImplementedError) as exc_info:
        _provider_settings("anthropic")
    assert "not supported" in str(exc_info.value)
    assert "ollama" in str(exc_info.value)
    assert "openai" in str(exc_info.value)


def test_context_cap():
    from brainpack.query import _cap_context
    # 6 chunks of ~600 tokens each should result in fewer than 6 being returned
    long_chunk = "word " * 600
    chunks = [long_chunk] * 6
    capped = _cap_context(chunks, max_tokens=3000)
    assert len(capped) < 6


def test_context_cap_small_chunks_pass_through():
    from brainpack.query import _cap_context
    # 2 small chunks well under 3000 tokens should be returned unchanged
    small_chunk = "This is a short sentence."
    chunks = [small_chunk, small_chunk]
    capped = _cap_context(chunks, max_tokens=3000)
    assert len(capped) == 2
    assert capped == chunks


def test_topk(tmp_pack_dir, mock_model):
    from brainpack.store import get_collection, embed_and_store
    from brainpack.query import run_query
    col = get_collection(tmp_pack_dir, "test-pack")
    # Add 7 chunks so we can verify only 5 are retrieved
    for i in range(7):
        embed_and_store(
            col, mock_model, [f"Chunk {i} content."],
            [{"url": f"https://example.com/{i}", "title": f"Article {i}"}],
            url=f"https://example.com/{i}",
        )
    with patch("brainpack.query.OpenAI") as MockOpenAI:
        client = MockOpenAI.return_value
        choice = MagicMock()
        choice.message.content = "Answer with citations."
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        result = run_query("test question", col, mock_model)
    assert len(result["sources"]) <= 5


def test_citations(tmp_pack_dir, mock_model):
    from brainpack.store import get_collection, embed_and_store
    from brainpack.query import run_query
    col = get_collection(tmp_pack_dir, "test-pack")
    embed_and_store(
        col, mock_model, ["Some content."],
        [{"url": "https://example.com/a", "title": "My Article"}],
        url="https://example.com/a",
    )
    with patch("brainpack.query.OpenAI") as MockOpenAI:
        client = MockOpenAI.return_value
        choice = MagicMock()
        choice.message.content = "Answer."
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        result = run_query("test question", col, mock_model)
    assert any("url" in s for s in result["sources"])
    assert any("title" in s for s in result["sources"])


def test_answer_is_nonempty(tmp_pack_dir, mock_model):
    from brainpack.store import get_collection, embed_and_store
    from brainpack.query import run_query
    col = get_collection(tmp_pack_dir, "test-pack")
    embed_and_store(
        col, mock_model, ["Some content."],
        [{"url": "https://example.com/a", "title": "My Article"}],
        url="https://example.com/a",
    )
    with patch("brainpack.query.OpenAI") as MockOpenAI:
        client = MockOpenAI.return_value
        choice = MagicMock()
        choice.message.content = "Non-empty answer from LLM."
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        result = run_query("test question", col, mock_model)
    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0


def test_timestamp_source_labels_include_ranges():
    """Timestamp-capable source labels include a human-readable range."""
    from brainpack.query import _source_label

    label = _source_label(
        {
            "title": "Episode",
            "url": "https://youtu.be/vid123",
            "timestamp_start": 12.0,
            "timestamp_end": 34.0,
        }
    )

    assert "00:12-00:34" in label


def test_source_labels_fall_back_cleanly_without_timestamps():
    """Sources without timing data should not invent timestamp output."""
    from brainpack.query import _source_label

    label = _source_label(
        {"title": "Article", "url": "https://example.com/article"}
    )

    assert "00:" not in label
    assert "Article" in label
    assert "https://example.com/article" in label


def test_run_query_includes_chat_history_in_prompt(tmp_pack_dir, mock_model):
    """run_query folds prior turns into the LLM prompt when chat history is provided."""
    from brainpack.store import get_collection, embed_and_store
    from brainpack.query import run_query

    col = get_collection(tmp_pack_dir, "test-pack")
    embed_and_store(
        col,
        mock_model,
        ["Some content."],
        [{"url": "https://example.com/a", "title": "My Article"}],
        url="https://example.com/a",
    )

    with patch("brainpack.query.OpenAI") as MockOpenAI:
        client = MockOpenAI.return_value
        choice = MagicMock()
        choice.message.content = "Answer with memory."
        client.chat.completions.create.return_value = MagicMock(choices=[choice])

        run_query(
            "Second question",
            col,
            mock_model,
            history=[{"question": "First question", "answer": "First answer"}],
        )

    user_message = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Conversation so far:" in user_message
    assert "User: First question" in user_message
    assert "Assistant: First answer" in user_message
    assert "Question: Second question" in user_message


def test_run_query_prefers_answering_in_turkish_for_turkish_questions(tmp_pack_dir, mock_model):
    """run_query instructs the model to stay in Turkish when the question/context are Turkish."""
    from brainpack.store import get_collection, embed_and_store
    from brainpack.query import run_query

    col = get_collection(tmp_pack_dir, "test-pack")
    embed_and_store(
        col,
        mock_model,
        ["Bu metin Turkce icerik ve tesvik detaylari icerir."],
        [{"url": "https://example.com/a", "title": "Turkce Makale"}],
        url="https://example.com/a",
    )

    with patch("brainpack.query.OpenAI") as MockOpenAI:
        client = MockOpenAI.return_value
        choice = MagicMock()
        choice.message.content = "Turkce cevap."
        client.chat.completions.create.return_value = MagicMock(choices=[choice])

        run_query("Bu desteklerde neler degisti?", col, mock_model)

    system_message = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Answer in Turkish" in system_message
    assert "Do not switch to English" in system_message
