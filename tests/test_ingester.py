"""Tests for ingester.py — covers ING-03."""
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
