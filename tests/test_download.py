"""Tests for the download stage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from karaoke.download import download


class TestDownload:
    @patch("karaoke.download.yt_dlp.YoutubeDL")
    def test_successful_download(self, mock_ytdlp_class, tmp_path):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Song",
        }
        mock_ytdlp_class.return_value = mock_ydl

        # Simulate yt-dlp creating the output files
        def fake_download(urls):
            (tmp_path / "abc123.mp4").touch()
            (tmp_path / "abc123.wav").touch()

        mock_ydl.download.side_effect = fake_download

        result = download("https://youtube.com/watch?v=abc123", tmp_path)

        assert result.video_id == "abc123"
        assert result.title == "Test Song"
        assert result.video_path == tmp_path / "abc123.mp4"
        assert result.audio_path == tmp_path / "abc123.wav"

    @patch("karaoke.download.yt_dlp.YoutubeDL")
    def test_extract_info_failure_raises(self, mock_ytdlp_class, tmp_path):
        import yt_dlp

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError("not found")
        mock_ytdlp_class.return_value = mock_ydl

        with pytest.raises(RuntimeError, match="yt-dlp failed to extract info"):
            download("https://youtube.com/watch?v=bad", tmp_path)

    @patch("karaoke.download.yt_dlp.YoutubeDL")
    def test_reuses_cached_files(self, mock_ytdlp_class, tmp_path):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Song",
        }
        mock_ytdlp_class.return_value = mock_ydl

        # Pre-create both files to simulate a previous run
        (tmp_path / "abc123.mp4").touch()
        (tmp_path / "abc123.wav").touch()

        result = download("https://youtube.com/watch?v=abc123", tmp_path)

        assert result.video_id == "abc123"
        assert result.title == "Test Song"
        assert result.video_path == tmp_path / "abc123.mp4"
        assert result.audio_path == tmp_path / "abc123.wav"
        # Should NOT have called download — only extract_info
        mock_ydl.download.assert_not_called()

    @patch("karaoke.download.yt_dlp.YoutubeDL")
    def test_redownloads_on_partial_cache(self, mock_ytdlp_class, tmp_path):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Song",
        }
        mock_ytdlp_class.return_value = mock_ydl

        # Only video exists — partial cache should trigger re-download
        (tmp_path / "abc123.mp4").touch()

        def fake_download(urls):
            (tmp_path / "abc123.mp4").touch()
            (tmp_path / "abc123.wav").touch()

        mock_ydl.download.side_effect = fake_download

        result = download("https://youtube.com/watch?v=abc123", tmp_path)

        assert result.video_id == "abc123"
        # download() should have been called (for video and audio)
        assert mock_ydl.download.call_count == 2

    @patch("karaoke.download.yt_dlp.YoutubeDL")
    def test_extracts_track_and_artist(self, mock_ytdlp_class, tmp_path):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Balam Pichkari (Full Video)",
            "track": "Balam Pichkari",
            "artist": "Vishal Dadlani",
        }
        mock_ytdlp_class.return_value = mock_ydl

        (tmp_path / "abc123.mp4").touch()
        (tmp_path / "abc123.wav").touch()

        result = download("https://youtube.com/watch?v=abc123", tmp_path)
        assert result.track == "Balam Pichkari"
        assert result.artist == "Vishal Dadlani"

    @patch("karaoke.download.yt_dlp.YoutubeDL")
    def test_track_and_artist_none_when_missing(self, mock_ytdlp_class, tmp_path):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Song",
        }
        mock_ytdlp_class.return_value = mock_ydl

        (tmp_path / "abc123.mp4").touch()
        (tmp_path / "abc123.wav").touch()

        result = download("https://youtube.com/watch?v=abc123", tmp_path)
        assert result.track is None
        assert result.artist is None

    @patch("karaoke.download.yt_dlp.YoutubeDL")
    def test_missing_output_file_raises(self, mock_ytdlp_class, tmp_path):
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Song",
        }
        mock_ytdlp_class.return_value = mock_ydl

        with pytest.raises(RuntimeError, match="did not produce expected video file"):
            download("https://youtube.com/watch?v=abc123", tmp_path)
