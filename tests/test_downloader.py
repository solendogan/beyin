"""Tests for brainpack.downloader — YouTube + podcast audio fetching."""
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from brainpack.downloader import (
    detect_source_type,
    list_youtube_episodes,
    download_audio,
    list_podcast_episodes,
    download_podcast_audio,
    check_deno_available,
)


# ING-04: URL type detection
class TestDetectSourceType:
    def test_youtube_channel_url(self):
        assert detect_source_type("https://www.youtube.com/@ArmaganAmcalar") == "youtube"

    def test_youtube_playlist_url(self):
        assert detect_source_type("https://www.youtube.com/playlist?list=PLxyz") == "youtube"

    def test_youtube_watch_url(self):
        assert detect_source_type("https://www.youtube.com/watch?v=abc123") == "youtube"

    def test_youtube_short_url(self):
        assert detect_source_type("https://youtu.be/abc123") == "youtube"

    def test_youtube_channel_path(self):
        assert detect_source_type("https://www.youtube.com/channel/UCxyz") == "youtube"

    def test_rss_feed_url(self):
        assert detect_source_type("https://example.com/podcast.rss") == "podcast"

    def test_feed_path_url(self):
        assert detect_source_type("https://example.com/feed/") == "podcast"

    def test_rss_path_url(self):
        assert detect_source_type("https://example.com/rss/") == "podcast"

    def test_feed_xml_url(self):
        assert detect_source_type("https://example.com/feed.xml") == "podcast"

    def test_article_url(self):
        assert detect_source_type("https://substack.com/some-article") == "article"

    def test_medium_article_url(self):
        assert detect_source_type("https://medium.com/@author/post") == "article"

    def test_local_path_markdown_detected_as_local_text(self, tmp_path):
        source = tmp_path / "notes.md"
        source.write_text("hello", encoding="utf-8")

        assert detect_source_type(str(source)) == "local_text"

    def test_local_path_pack_yaml_detected_as_pack(self, tmp_path):
        source = tmp_path / "pack.yaml"
        source.write_text("name: demo\n", encoding="utf-8")

        assert detect_source_type(str(source)) == "pack"


# ING-01: YouTube episode listing
class TestListYoutubeEpisodes:
    def test_returns_episode_list_with_limit(self):
        """list_youtube_episodes returns at most `limit` episode dicts."""
        mock_ydl_module = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl_module.YoutubeDL.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "entries": [
                {"id": "vid1", "title": "Episode 1", "webpage_url": "https://youtu.be/vid1"},
                {"id": "vid2", "title": "Episode 2", "webpage_url": "https://youtu.be/vid2"},
            ]
        }
        with patch.dict(sys.modules, {"yt_dlp": mock_ydl_module}):
            result = list_youtube_episodes("https://youtube.com/@channel", limit=2)
        assert len(result) == 2
        assert result[0]["title"] == "Episode 1"
        assert "url" in result[0]

    def test_returns_empty_list_on_error(self):
        """Returns [] on any yt-dlp failure — never raises."""
        mock_ydl_module = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl_module.YoutubeDL.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("network error")
        with patch.dict(sys.modules, {"yt_dlp": mock_ydl_module}):
            result = list_youtube_episodes("https://youtube.com/@channel", limit=20)
        assert result == []


# ING-01: YouTube audio download
class TestDownloadAudio:
    def test_returns_path_on_success(self, tmp_path):
        """download_audio returns Path to downloaded file."""
        mock_ydl_module = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl_module.YoutubeDL.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {"id": "abc123", "ext": "m4a"}
        audio_file = tmp_path / "abc123.m4a"
        audio_file.write_bytes(b"x" * 100_000)  # simulate 100KB file
        with patch.dict(sys.modules, {"yt_dlp": mock_ydl_module}):
            result = download_audio("https://youtu.be/abc123", tmp_path)
        assert result is not None
        assert result == audio_file

    def test_returns_none_on_error(self, tmp_path):
        """download_audio returns None on failure — never raises."""
        mock_ydl_module = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl_module.YoutubeDL.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("403 Forbidden")
        with patch.dict(sys.modules, {"yt_dlp": mock_ydl_module}):
            result = download_audio("https://youtu.be/abc123", tmp_path)
        assert result is None


# ING-02: Podcast RSS listing
class TestListPodcastEpisodes:
    def test_returns_episode_list_with_limit(self):
        """list_podcast_episodes returns at most `limit` episodes with audio URLs."""
        mock_enclosure = MagicMock()
        mock_enclosure.href = "https://cdn.example.com/ep1.mp3"
        mock_enclosure.get = lambda key, default="": {"type": "audio/mpeg"}.get(key, default)

        mock_entry = MagicMock()
        mock_entry.enclosures = [mock_enclosure]
        mock_entry.get = lambda key, default="Unknown": {
            "title": "Episode 1",
            "id": "ep-guid-1",
        }.get(key, default)

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        mock_fp_module = MagicMock()
        mock_fp_module.parse.return_value = mock_feed
        with patch.dict(sys.modules, {"feedparser": mock_fp_module}):
            result = list_podcast_episodes("https://example.com/feed.rss", limit=1)
        assert len(result) == 1
        assert result[0]["url"] == "https://cdn.example.com/ep1.mp3"
        assert result[0]["title"] == "Episode 1"

    def test_skips_entries_without_audio_enclosure(self):
        """Entries with no audio enclosures are silently skipped."""
        mock_entry = MagicMock()
        mock_entry.enclosures = []  # no audio enclosures
        mock_entry.links = []  # no link-rel enclosures either

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        mock_fp_module = MagicMock()
        mock_fp_module.parse.return_value = mock_feed
        with patch.dict(sys.modules, {"feedparser": mock_fp_module}):
            result = list_podcast_episodes("https://example.com/feed.rss", limit=None)
        assert result == []


# ING-02: Podcast audio download
class TestDownloadPodcastAudio:
    def test_returns_path_on_success(self, tmp_path):
        """download_podcast_audio returns Path to downloaded file."""
        audio_url = "https://cdn.example.com/ep1.mp3"
        out_file = tmp_path / "ep1.mp3"

        def fake_urlretrieve(url, dest):
            Path(dest).write_bytes(b"x" * 50_000)

        with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve):
            result = download_podcast_audio(audio_url, tmp_path, title="Episode 1")
        assert result is not None
        assert result == out_file

    def test_returns_none_on_error(self, tmp_path):
        """download_podcast_audio returns None on failure — never raises."""
        import urllib.request as _ur

        with patch.object(_ur, "urlretrieve", side_effect=Exception("connection refused")):
            result = download_podcast_audio("https://cdn.example.com/ep1.mp3", tmp_path)
        assert result is None


# Deno availability check
class TestCheckDenoAvailable:
    def test_returns_true_when_deno_on_path(self):
        with patch("shutil.which", return_value="/usr/local/bin/deno"):
            assert check_deno_available() is True

    def test_returns_false_when_deno_missing(self):
        with patch("shutil.which", return_value=None):
            assert check_deno_available() is False
