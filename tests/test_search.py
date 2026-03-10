"""Tests for the YouTube search module."""

from unittest.mock import MagicMock, patch

import pytest

from karaoke.models import VideoSearchResult
from karaoke.search import _YTDLP_OPTS, search_videos


def _make_entry(video_id="abc123", title="Test Song", channel="Test Channel",
                duration=240, thumbnail="https://img.youtube.com/vi/abc123/0.jpg"):
    return {
        "id": video_id,
        "title": title,
        "channel": channel,
        "duration": duration,
        "thumbnail": thumbnail,
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
    }


@patch("karaoke.search.yt_dlp.YoutubeDL")
def test_search_returns_results(mock_ytdlp_cls):
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = {
        "entries": [_make_entry(), _make_entry(video_id="def456", title="Another Song")]
    }
    mock_ytdlp_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ytdlp_cls.return_value.__exit__ = MagicMock(return_value=False)

    results = search_videos("test query", max_results=2)

    assert len(results) == 2
    assert isinstance(results[0], VideoSearchResult)
    assert results[0].video_id == "abc123"
    assert results[0].title == "Test Song"
    assert results[1].video_id == "def456"
    mock_ydl.extract_info.assert_called_once_with("ytsearch2:test query", download=False)


@patch("karaoke.search.yt_dlp.YoutubeDL")
def test_search_handles_missing_fields(mock_ytdlp_cls):
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = {
        "entries": [{"id": "xyz", "uploader": "Some Uploader"}]
    }
    mock_ytdlp_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ytdlp_cls.return_value.__exit__ = MagicMock(return_value=False)

    results = search_videos("incomplete")

    assert len(results) == 1
    assert results[0].title == ""
    assert results[0].thumbnail_url == "https://i.ytimg.com/vi/xyz/hqdefault.jpg"
    assert results[0].channel == "Some Uploader"
    assert results[0].duration_seconds == 0
    assert results[0].url == "https://www.youtube.com/watch?v=xyz"


def test_search_empty_query_raises():
    with pytest.raises(ValueError, match="must not be empty"):
        search_videos("")

    with pytest.raises(ValueError, match="must not be empty"):
        search_videos("   ")


@patch("karaoke.search.yt_dlp.YoutubeDL")
def test_search_ytdlp_error_raises_runtime(mock_ytdlp_cls):
    import yt_dlp

    mock_ydl = MagicMock()
    mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError("network error")
    mock_ytdlp_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ytdlp_cls.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(RuntimeError, match="yt-dlp search failed"):
        search_videos("fail query")


@patch("karaoke.search.yt_dlp.YoutubeDL")
def test_search_max_results_clamped(mock_ytdlp_cls):
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = {"entries": []}
    mock_ytdlp_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ytdlp_cls.return_value.__exit__ = MagicMock(return_value=False)

    search_videos("query", max_results=50)
    mock_ydl.extract_info.assert_called_once_with("ytsearch10:query", download=False)


@patch("karaoke.search.yt_dlp.YoutubeDL")
def test_search_no_entries(mock_ytdlp_cls):
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = {"entries": None}
    mock_ytdlp_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ytdlp_cls.return_value.__exit__ = MagicMock(return_value=False)

    results = search_videos("nothing")
    assert results == []


def test_search_uses_extract_flat():
    assert _YTDLP_OPTS.get("extract_flat") is True


@patch("karaoke.search.yt_dlp.YoutubeDL")
def test_search_url_fallback_to_url_field(mock_ytdlp_cls):
    """With extract_flat, entries may have 'url' instead of 'webpage_url'."""
    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = {
        "entries": [{"id": "flat1", "url": "https://www.youtube.com/watch?v=flat1"}]
    }
    mock_ytdlp_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ytdlp_cls.return_value.__exit__ = MagicMock(return_value=False)

    results = search_videos("flat test")
    assert results[0].url == "https://www.youtube.com/watch?v=flat1"
