"""Tests for query.py — covers QRY-01, QRY-02, QRY-03, QRY-04, QRY-05, QRY-06."""
import pytest
from unittest.mock import patch, MagicMock


def test_ollama_config():
    from beyin.query import _provider_settings
    base_url, api_key = _provider_settings("ollama")
    assert base_url == "http://localhost:11434/v1"
    assert api_key == "ollama"


def test_unknown_provider_raises():
    from beyin.query import _provider_settings
    with pytest.raises(ValueError) as exc_info:
        _provider_settings("bogus")
    assert "Unknown LLM provider" in str(exc_info.value)
    assert "ollama" in str(exc_info.value)


def test_anthropic_raises():
    from beyin.query import _provider_settings
    with pytest.raises(NotImplementedError) as exc_info:
        _provider_settings("anthropic")
    assert "not supported" in str(exc_info.value)
    assert "ollama" in str(exc_info.value)


def test_context_cap():
    from beyin.query import _cap_context
    # 6 chunks of ~600 tokens each should result in fewer than 6 being returned
    long_chunk = "word " * 600
    chunks = [long_chunk] * 6
    capped = _cap_context(chunks, max_tokens=3000)
    assert len(capped) < 6


def test_context_cap_small_chunks_pass_through():
    from beyin.query import _cap_context
    # 2 small chunks well under 3000 tokens should be returned unchanged
    small_chunk = "This is a short sentence."
    chunks = [small_chunk, small_chunk]
    capped = _cap_context(chunks, max_tokens=3000)
    assert len(capped) == 2
    assert capped == chunks


def test_retrieve_evidence_returns_raw_text_metadata_and_rank(mock_model):
    from beyin.query import retrieve_evidence

    collection = MagicMock()
    collection.query.return_value = {
        "documents": [["Chunk A", "Chunk B"]],
        "metadatas": [[
            {"url": "https://example.com/a", "title": "Article A"},
            {"url": "https://example.com/b", "title": "Article B", "timestamp_start": 12.0, "timestamp_end": 34.0},
        ]],
        "distances": [[0.11, 0.22]],
    }

    evidence = retrieve_evidence("test question", collection, mock_model, n_results=2)

    assert evidence == [
        {
            "text": "Chunk A",
            "url": "https://example.com/a",
            "title": "Article A",
            "rank": 1,
            "distance": 0.11,
        },
        {
            "text": "Chunk B",
            "url": "https://example.com/b",
            "title": "Article B",
            "rank": 2,
            "distance": 0.22,
            "timestamp_start": 12.0,
            "timestamp_end": 34.0,
        },
    ]


def test_retrieve_evidence_defaults_to_broader_than_answer_path(mock_model):
    from beyin.query import retrieve_evidence

    collection = MagicMock()
    collection.query.return_value = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }

    retrieve_evidence("test question", collection, mock_model)

    assert collection.query.call_args.kwargs["n_results"] > 5


def test_topk(tmp_pack_dir, mock_model):
    from beyin.store import get_collection, embed_and_store
    from beyin.query import run_query
    col = get_collection(tmp_pack_dir, "test-pack")
    # Add 7 chunks so we can verify only 5 are retrieved
    for i in range(7):
        embed_and_store(
            col, mock_model, [f"Chunk {i} content."],
            [{"url": f"https://example.com/{i}", "title": f"Article {i}"}],
            url=f"https://example.com/{i}",
        )
    with patch("beyin.query._CLIENT_CLASS") as MockClientClass:
        client = MockClientClass.return_value
        choice = MagicMock()
        choice.message.content = "Answer with citations."
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        result = run_query("test question", col, mock_model)
    assert len(result["sources"]) <= 5



def test_run_query_caps_context_after_shared_retrieval(mock_model):
    from beyin.query import run_query

    long_chunk = "word " * 2500
    short_chunk = "second " * 700

    with patch(
        "beyin.query.retrieve_evidence",
        return_value=[
            {
                "text": long_chunk,
                "url": "https://example.com/a",
                "title": "Article A",
                "rank": 1,
                "distance": 0.1,
            },
            {
                "text": short_chunk,
                "url": "https://example.com/b",
                "title": "Article B",
                "rank": 2,
                "distance": 0.2,
            },
        ],
    ), patch("beyin.query._CLIENT_CLASS") as MockClientClass:
        client = MockClientClass.return_value
        choice = MagicMock()
        choice.message.content = "Capped answer."
        client.chat.completions.create.return_value = MagicMock(choices=[choice])

        result = run_query("test question", MagicMock(), mock_model)

    user_message = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert short_chunk not in user_message
    assert long_chunk in user_message
    assert len(result["sources"]) == 1


def test_timestamp_source_labels_include_ranges():
    """Timestamp-capable source labels include a human-readable range."""
    from beyin.query import _source_label

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
    from beyin.query import _source_label

    label = _source_label(
        {"title": "Article", "url": "https://example.com/article"}
    )

    assert "00:" not in label
    assert "Article" in label
    assert "https://example.com/article" in label


def test_run_query_prefers_answering_in_turkish_for_turkish_questions(tmp_pack_dir, mock_model):
    """run_query instructs the model to stay in Turkish when the question/context are Turkish."""
    from beyin.store import get_collection, embed_and_store
    from beyin.query import run_query

    col = get_collection(tmp_pack_dir, "test-pack")
    embed_and_store(
        col,
        mock_model,
        ["Bu metin Turkce icerik ve tesvik detaylari icerir."],
        [{"url": "https://example.com/a", "title": "Turkce Makale"}],
        url="https://example.com/a",
    )

    with patch("beyin.query._CLIENT_CLASS") as MockClientClass:
        client = MockClientClass.return_value
        choice = MagicMock()
        choice.message.content = "Turkce cevap."
        client.chat.completions.create.return_value = MagicMock(choices=[choice])

        run_query("Bu desteklerde neler degisti?", col, mock_model)

    system_message = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Answer in Turkish" in system_message
    assert "Do not switch to English" in system_message
