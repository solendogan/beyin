"""Tests for brainpack.downloader — YouTube + podcast audio fetching."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from brainpack.downloader import detect_source_type, list_youtube_episodes, download_audio, list_podcast_episodes, download_podcast_audio


# ING-04: URL type detection
class TestDetectSourceType:
    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_youtube_channel_url(self):
        assert detect_source_type("https://www.youtube.com/@ArmaganAmcalar") == "youtube"

    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_youtube_playlist_url(self):
        assert detect_source_type("https://www.youtube.com/playlist?list=PLxyz") == "youtube"

    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_youtube_watch_url(self):
        assert detect_source_type("https://www.youtube.com/watch?v=abc123") == "youtube"

    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_rss_feed_url(self):
        assert detect_source_type("https://example.com/podcast.rss") == "podcast"

    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_feed_path_url(self):
        assert detect_source_type("https://example.com/feed/") == "podcast"

    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_article_url(self):
        assert detect_source_type("https://substack.com/some-article") == "article"


# ING-01: YouTube episode listing
class TestListYoutubeEpisodes:
    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_returns_episode_list_with_limit(self):
        """list_youtube_episodes returns at most `limit` episode dicts."""
        with patch("brainpack.downloader.yt_dlp") as mock_ydl_module:
            mock_ydl = MagicMock()
            mock_ydl_module.YoutubeDL.return_value.__enter__.return_value = mock_ydl
            mock_ydl.extract_info.return_value = {
                "entries": [
                    {"id": "vid1", "title": "Episode 1", "webpage_url": "https://youtu.be/vid1"},
                    {"id": "vid2", "title": "Episode 2", "webpage_url": "https://youtu.be/vid2"},
                ]
            }
            result = list_youtube_episodes("https://youtube.com/@channel", limit=2)
        assert len(result) == 2
        assert result[0]["title"] == "Episode 1"
        assert "url" in result[0]

    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_returns_empty_list_on_error(self):
        """Returns [] on any yt-dlp failure — never raises."""
        with patch("brainpack.downloader.yt_dlp") as mock_ydl_module:
            mock_ydl = MagicMock()
            mock_ydl_module.YoutubeDL.return_value.__enter__.return_value = mock_ydl
            mock_ydl.extract_info.side_effect = Exception("network error")
            result = list_youtube_episodes("https://youtube.com/@channel", limit=20)
        assert result == []


# ING-01: YouTube audio download
class TestDownloadAudio:
    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_returns_path_on_success(self, tmp_path):
        """download_audio returns Path to downloaded file."""
        with patch("brainpack.downloader.yt_dlp") as mock_ydl_module:
            mock_ydl = MagicMock()
            mock_ydl_module.YoutubeDL.return_value.__enter__.return_value = mock_ydl
            mock_ydl.extract_info.return_value = {"id": "abc123", "ext": "m4a"}
            audio_file = tmp_path / "abc123.m4a"
            audio_file.write_bytes(b"x" * 100_000)  # simulate 100KB file
            result = download_audio("https://youtu.be/abc123", tmp_path)
        assert result is not None

    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_returns_none_on_error(self, tmp_path):
        """download_audio returns None on failure — never raises."""
        with patch("brainpack.downloader.yt_dlp") as mock_ydl_module:
            mock_ydl = MagicMock()
            mock_ydl_module.YoutubeDL.return_value.__enter__.return_value = mock_ydl
            mock_ydl.extract_info.side_effect = Exception("403 Forbidden")
            result = download_audio("https://youtu.be/abc123", tmp_path)
        assert result is None


# ING-02: Podcast RSS listing
class TestListPodcastEpisodes:
    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_returns_episode_list_with_limit(self):
        """list_podcast_episodes returns at most `limit` episodes with audio URLs."""
        mock_feed = MagicMock()
        mock_entry = MagicMock()
        mock_entry.title = "Episode 1"
        mock_entry.id = "ep-guid-1"
        mock_enclosure = MagicMock()
        mock_enclosure.href = "https://cdn.example.com/ep1.mp3"
        mock_enclosure.type = "audio/mpeg"
        mock_entry.enclosures = [mock_enclosure]
        mock_feed.entries = [mock_entry]

        with patch("brainpack.downloader.feedparser") as mock_fp:
            mock_fp.parse.return_value = mock_feed
            result = list_podcast_episodes("https://example.com/feed.rss", limit=1)
        assert len(result) == 1
        assert result[0]["url"] == "https://cdn.example.com/ep1.mp3"
        assert result[0]["title"] == "Episode 1"

    @pytest.mark.xfail(strict=False, reason="stub — implement in plan 02-03")
    def test_skips_entries_without_audio_enclosure(self):
        """Entries with no audio enclosures are silently skipped."""
        mock_feed = MagicMock()
        mock_entry = MagicMock()
        mock_entry.enclosures = []  # no audio
        mock_feed.entries = [mock_entry]
        with patch("brainpack.downloader.feedparser") as mock_fp:
            mock_fp.parse.return_value = mock_feed
            result = list_podcast_episodes("https://example.com/feed.rss", limit=None)
        assert result == []
