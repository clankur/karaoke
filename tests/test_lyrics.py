"""Tests for the lyrics fetcher."""

from unittest.mock import patch

from karaoke.lyrics import fetch_lyrics


class TestFetchLyrics:
    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_returns_lyrics_when_found(self, mock_search):
        mock_search.return_value = "Hello world\nGoodbye moon"
        result = fetch_lyrics("Test Song")
        assert result == "Hello world\nGoodbye moon"
        mock_search.assert_called_once_with("Test Song", plain_only=True)

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_returns_none_when_not_found(self, mock_search):
        mock_search.return_value = None
        result = fetch_lyrics("Unknown Song")
        assert result is None

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_returns_none_on_exception(self, mock_search):
        mock_search.side_effect = Exception("network error")
        result = fetch_lyrics("Test Song")
        assert result is None

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_strips_lrc_timestamps(self, mock_search):
        mock_search.return_value = "[00:12.34]Hello world\n[00:15.67]Goodbye moon"
        result = fetch_lyrics("Test Song")
        assert result == "Hello world\nGoodbye moon"

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_strips_nested_lrc_tags(self, mock_search):
        mock_search.return_value = "[00:12.34][by:someone]Hello world"
        result = fetch_lyrics("Test Song")
        assert result == "Hello world"

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_returns_none_for_empty_result(self, mock_search):
        mock_search.return_value = ""
        result = fetch_lyrics("Test Song")
        assert result is None

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_skips_blank_lines(self, mock_search):
        mock_search.return_value = "Line one\n\n\nLine two"
        result = fetch_lyrics("Test Song")
        assert result == "Line one\nLine two"
