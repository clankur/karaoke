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
