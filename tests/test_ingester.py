import pytest
from unittest.mock import patch


def test_resolve_article_ingestion_follows_transcript_link():
    from brainpack.ingester import resolve_article_ingestion

    landing_html = """
    <html><body>
      <h1>Episode 1</h1>
      <p>Podcast episode show notes.</p>
      <a href="/episode-1-transcript">Transcript</a>
    </body></html>
    """
    transcript_html = "<html><body><h1>Episode 1 Transcript</h1><p>" + ("Transcript sentence. " * 200) + "</p></body></html>"

    def _fetch(url: str):
        if url.endswith("/episode-1"):
            return landing_html
        if url.endswith("/episode-1-transcript"):
            return transcript_html
        return None

    def _extract(downloaded: str, output_format=None, **_kwargs):
        if downloaded == landing_html and output_format == "json":
            return '{"title":"Episode 1"}'
        if downloaded == landing_html:
            return "Podcast episode show notes."
        if downloaded == transcript_html and output_format == "json":
            return '{"title":"Episode 1 Transcript"}'
        if downloaded == transcript_html:
            return "Transcript sentence. " * 200
        return None

    with patch("brainpack.ingester.fetch_url", side_effect=_fetch), patch(
        "brainpack.ingester.extract",
        side_effect=_extract,
    ):
        plan = resolve_article_ingestion("https://example.com/episode-1")

    assert plan is not None
    assert plan["mode"] == "transcript"
    assert plan["metadata_url"] == "https://example.com/episode-1-transcript"
    assert "Transcript sentence." in plan["text"]


def test_resolve_article_ingestion_detects_inline_transcript():
    from brainpack.ingester import resolve_article_ingestion

    html = "<html><body><h1>Episode 2</h1><h2>Transcript</h2><p>" + ("Long transcript paragraph. " * 120) + "</p></body></html>"

    def _extract(downloaded: str, output_format=None, **_kwargs):
        if output_format == "json":
            return '{"title":"Episode 2"}'
        return "Transcript " + ("Long transcript paragraph. " * 120)

    with patch("brainpack.ingester.fetch_url", return_value=html), patch(
        "brainpack.ingester.extract",
        side_effect=_extract,
    ):
        plan = resolve_article_ingestion("https://example.com/episode-2")

    assert plan is not None
    assert plan["mode"] == "transcript"
    assert plan["metadata_url"] == "https://example.com/episode-2"


def test_resolve_article_ingestion_falls_back_to_direct_audio_for_podcast_page():
    from brainpack.ingester import resolve_article_ingestion

    html = """
    <html><body>
      <h1>Podcast Episode 3</h1>
      <p>Show notes for the podcast episode.</p>
      <audio src="https://cdn.example.com/audio/episode-3.mp3"></audio>
    </body></html>
    """

    def _extract(_downloaded: str, output_format=None, **_kwargs):
        if output_format == "json":
            return '{"title":"Podcast Episode 3"}'
        return "Show notes for the podcast episode."

    with patch("brainpack.ingester.fetch_url", return_value=html), patch(
        "brainpack.ingester.extract",
        side_effect=_extract,
    ):
        plan = resolve_article_ingestion("https://example.com/episode-3")

    assert plan is not None
    assert plan["mode"] == "podcast_audio"
    assert plan["audio_url"] == "https://cdn.example.com/audio/episode-3.mp3"


def test_resolve_article_ingestion_rejects_podcast_page_without_transcript_or_audio():
    from brainpack.ingester import resolve_article_ingestion

    html = """
    <html><body>
      <h1>Podcast Episode 4</h1>
      <p>Show notes and listen on Spotify or Apple Podcasts.</p>
    </body></html>
    """

    def _extract(_downloaded: str, output_format=None, **_kwargs):
        if output_format == "json":
            return '{"title":"Podcast Episode 4"}'
        return "Show notes and listen on Spotify or Apple Podcasts."

    with patch("brainpack.ingester.fetch_url", return_value=html), patch(
        "brainpack.ingester.extract",
        side_effect=_extract,
    ):
        plan = resolve_article_ingestion("https://example.com/episode-4")

    assert plan is not None
    assert plan["mode"] == "podcast_unresolved"
    assert "no transcript or audio found" in plan["reason"]


def test_resolve_article_ingestion_keeps_normal_articles_as_articles():
    from brainpack.ingester import resolve_article_ingestion

    html = "<html><body><h1>Regular Article</h1><p>" + ("Useful article text. " * 80) + "</p></body></html>"

    def _extract(_downloaded: str, output_format=None, **_kwargs):
        if output_format == "json":
            return '{"title":"Regular Article"}'
        return "Useful article text. " * 80

    with patch("brainpack.ingester.fetch_url", return_value=html), patch(
        "brainpack.ingester.extract",
        side_effect=_extract,
    ):
        plan = resolve_article_ingestion("https://example.com/regular-article")

    assert plan is not None
    assert plan["mode"] == "article"
    assert plan["metadata_url"] == "https://example.com/regular-article"
