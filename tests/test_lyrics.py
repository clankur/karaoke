"""Tests for the lyrics fetcher."""

from unittest.mock import patch

from karaoke.lyrics import _clean_title, _parse_lrc, _strip_to_plain, fetch_lyrics
from karaoke.models import SyncedLine


class TestFetchLyrics:
    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_returns_synced_lyrics_when_lrc_available(self, mock_search):
        mock_search.return_value = "[00:12.34]Hello world\n[00:15.67]Goodbye moon"
        result = fetch_lyrics("Test Song")
        assert result is not None
        assert result.plain_text == "Hello world\nGoodbye moon"
        assert result.has_synced_timestamps
        assert len(result.synced_lines) == 2
        assert result.synced_lines[0].timestamp == 12.34
        assert result.synced_lines[0].text == "Hello world"
        assert result.synced_lines[1].timestamp == 15.67
        assert result.synced_lines[1].text == "Goodbye moon"
        mock_search.assert_called_once_with("Test Song")

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_returns_plain_lyrics_when_no_timestamps(self, mock_search):
        mock_search.return_value = "Hello world\nGoodbye moon"
        result = fetch_lyrics("Test Song")
        assert result is not None
        assert result.plain_text == "Hello world\nGoodbye moon"
        assert not result.has_synced_timestamps

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
    def test_returns_none_for_empty_result(self, mock_search):
        mock_search.return_value = ""
        result = fetch_lyrics("Test Song")
        assert result is None

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_skips_blank_lines(self, mock_search):
        mock_search.return_value = "Line one\n\n\nLine two"
        result = fetch_lyrics("Test Song")
        assert result is not None
        assert result.plain_text == "Line one\nLine two"

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_no_longer_uses_plain_only(self, mock_search):
        """Verify we fetch synced lyrics by default (no plain_only=True)."""
        mock_search.return_value = None
        fetch_lyrics("Test Song")
        mock_search.assert_called_once_with("Test Song")


class TestCleanTitle:
    def test_strips_parenthetical_tags(self):
        result = _clean_title("Song Name (Official Video)")
        assert result == ["Song Name"]

    def test_strips_bracketed_tags(self):
        result = _clean_title("Song Name [HD]")
        assert result == ["Song Name"]

    def test_strips_multiple_parenthetical_tags(self):
        result = _clean_title("Song Name (Full Video) (HD)")
        assert result == ["Song Name"]

    def test_splits_on_pipes(self):
        queries = _clean_title("Song | Album | Artist")
        assert "Song" in queries

    def test_complex_bollywood_title(self):
        title = (
            "Balam Pichkari (Full Video) | Yeh Jawaani Hai Deewani "
            "| Pritam | Ranbir Kapoor, Deepika | Holi Song"
        )
        queries = _clean_title(title)
        # First query: cleaned full title (parens stripped)
        assert queries[0] == (
            "Balam Pichkari | Yeh Jawaani Hai Deewani "
            "| Pritam | Ranbir Kapoor, Deepika | Holi Song"
        )
        # Second query: first pipe segment only
        assert queries[1] == "Balam Pichkari"

    def test_preserves_simple_titles(self):
        result = _clean_title("Bohemian Rhapsody")
        assert result == ["Bohemian Rhapsody"]

    def test_strips_common_suffixes(self):
        result = _clean_title("Song Name - Official Video")
        assert result == ["Song Name"]

    def test_strips_lyric_video_suffix(self):
        result = _clean_title("Song Name | Lyric Video")
        assert result[0] == "Song Name"

    def test_empty_title(self):
        result = _clean_title("")
        assert result == [""]

    def test_dash_separated_title(self):
        queries = _clean_title("Artist - Song Name - Official Audio")
        # After suffix stripping: "Artist - Song Name"
        # First pipe segment split on dash: "Artist"
        assert "Artist" in queries


class TestFetchLyricsRetry:
    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_retries_with_cleaned_title(self, mock_search):
        """When first query fails, retry with cleaned variant."""
        mock_search.side_effect = [None, "Found lyrics"]
        result = fetch_lyrics("Song (Official Video) | Album")
        assert result is not None
        assert mock_search.call_count == 2

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_uses_artist_when_provided(self, mock_search):
        """When artist is provided, searches with 'title artist' first."""
        mock_search.return_value = "Found lyrics"
        fetch_lyrics("Song Name", artist="Artist Name")
        first_call_query = mock_search.call_args_list[0][0][0]
        assert first_call_query == "Song Name Artist Name"

    @patch("karaoke.lyrics.syncedlyrics.search")
    def test_returns_none_when_all_queries_fail(self, mock_search):
        mock_search.return_value = None
        result = fetch_lyrics("Song (Official Video) | Album | Artist")
        assert result is None
        # Should have tried multiple queries
        assert mock_search.call_count >= 2


class TestParseLrc:
    def test_parses_standard_lrc(self):
        text = "[00:12.34]Hello world\n[00:15.67]Goodbye moon"
        result = _parse_lrc(text)
        assert result is not None
        assert len(result) == 2
        assert result[0] == SyncedLine(timestamp=12.34, text="Hello world")
        assert result[1] == SyncedLine(timestamp=15.67, text="Goodbye moon")

    def test_parses_millisecond_timestamps(self):
        text = "[00:12.345]Hello"
        result = _parse_lrc(text)
        assert result is not None
        assert abs(result[0].timestamp - 12.345) < 0.001

    def test_strips_nested_tags(self):
        text = "[00:12.34][by:someone]Hello world"
        result = _parse_lrc(text)
        assert result is not None
        assert result[0].text == "Hello world"

    def test_returns_none_for_plain_text(self):
        text = "Hello world\nGoodbye moon"
        result = _parse_lrc(text)
        assert result is None

    def test_skips_empty_lyric_lines(self):
        text = "[00:05.00]\n[00:12.34]Hello"
        result = _parse_lrc(text)
        assert result is not None
        assert len(result) == 1
        assert result[0].text == "Hello"

    def test_skips_blank_lines(self):
        text = "[00:12.34]Hello\n\n[00:15.67]World"
        result = _parse_lrc(text)
        assert result is not None
        assert len(result) == 2

    def test_handles_minutes(self):
        text = "[02:30.00]Two minutes in"
        result = _parse_lrc(text)
        assert result is not None
        assert result[0].timestamp == 150.0


class TestStripToPlain:
    def test_strips_lrc_timestamps(self):
        result = _strip_to_plain("[00:12.34]Hello world\n[00:15.67]Goodbye moon")
        assert result == ["Hello world", "Goodbye moon"]

    def test_strips_metadata_tags(self):
        result = _strip_to_plain("[by:someone]Hello")
        assert result == ["Hello"]

    def test_skips_blank_lines(self):
        result = _strip_to_plain("Line one\n\n\nLine two")
        assert result == ["Line one", "Line two"]

    def test_returns_empty_for_empty_input(self):
        result = _strip_to_plain("")
        assert result == []
