"""Tests for ingester.py — covers ING-03."""
from pathlib import Path

import pytest
from unittest.mock import patch


def test_fetch_article_returns_text_and_title():
    from brainpack.ingester import fetch_article
    with patch("brainpack.ingester.fetch_url") as mock_fetch, \
         patch("brainpack.ingester.extract") as mock_extract:
        mock_fetch.return_value = "<html>content</html>"
        mock_extract.side_effect = ["Sample article text.", '{"title": "Sample Title"}']
        result = fetch_article("https://example.com/article")
    assert result is not None
    text, title = result
    assert len(text) > 0
    assert title == "Sample Title"


def test_fetch_article_returns_none_on_fetch_failure():
    from brainpack.ingester import fetch_article
    with patch("brainpack.ingester.fetch_url", return_value=None):
        result = fetch_article("https://example.com/broken")
    assert result is None


def test_fetch_article_returns_none_on_extraction_failure():
    from brainpack.ingester import fetch_article
    with patch("brainpack.ingester.fetch_url") as mock_fetch, \
         patch("brainpack.ingester.extract") as mock_extract:
        mock_fetch.return_value = "<html>content</html>"
        mock_extract.return_value = None  # extract returns None (no extractable text)
        result = fetch_article("https://example.com/no-text")
    assert result is None


def test_fetch_article_falls_back_to_url_as_title():
    from brainpack.ingester import fetch_article
    url = "https://example.com/article-no-meta"
    with patch("brainpack.ingester.fetch_url") as mock_fetch, \
         patch("brainpack.ingester.extract") as mock_extract:
        mock_fetch.return_value = "<html>content</html>"
        # First call (text extraction) returns text, second call (metadata) returns None
        mock_extract.side_effect = ["Sample article text.", None]
        result = fetch_article(url)
    assert result is not None
    text, title = result
    assert len(text) > 0
    assert title == url  # falls back to URL when no metadata


def test_local_path_load_text_like_source_reads_markdown(tmp_path):
    from brainpack.ingester import load_text_like_source

    source = tmp_path / "notes.md"
    source.write_text("# Heading\n\nUseful local text.\n", encoding="utf-8")

    text, title = load_text_like_source(source)

    assert "Useful local text." in text
    assert title == "notes"


def test_local_path_load_text_like_source_raises_for_missing_file(tmp_path):
    from brainpack.ingester import load_text_like_source

    missing = tmp_path / "missing.md"

    with pytest.raises(FileNotFoundError):
        load_text_like_source(missing)


def test_local_path_load_text_like_source_rejects_unsupported_suffix(tmp_path):
    from brainpack.ingester import load_text_like_source

    source = tmp_path / "recording.mp3"
    source.write_bytes(b"not text")

    with pytest.raises(ValueError, match="Unsupported local source type"):
        load_text_like_source(source)
