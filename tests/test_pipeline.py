"""Tests for the pipeline orchestrator."""

from pathlib import Path
from unittest.mock import patch

from karaoke.models import (
    AlignmentResult,
    DownloadResult,
    RenderResult,
    SeparationResult,
    TimedLine,
    TimedWord,
)
from karaoke.pipeline import generate_karaoke


class TestGenerateKaraoke:
    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.download")
    def test_full_pipeline(self, mock_download, mock_separate, mock_align, mock_render, tmp_path):
        work_dir = tmp_path / "work"
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "video.mp4",
            audio_path=tmp_path / "audio.wav",
            title="Test",
            video_id="abc",
        )
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "vocals.wav",
            instrumental_path=tmp_path / "instrumental.wav",
        )
        mock_align.return_value = AlignmentResult(
            lines=[TimedLine(words=[TimedWord(text="test", start=0.0, end=1.0)])]
        )
        mock_render.return_value = RenderResult(output_path=output)

        result = generate_karaoke("https://youtube.com/watch?v=abc", output, work_dir=work_dir)

        assert result.output_path == output
        mock_download.assert_called_once()
        mock_separate.assert_called_once()
        mock_align.assert_called_once()
        mock_render.assert_called_once()

    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.download")
    def test_uses_temp_dir_when_no_work_dir(self, mock_download, mock_separate, mock_align, mock_render, tmp_path):
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="T",
            video_id="x",
        )
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "v.wav",
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(lines=[])
        mock_render.return_value = RenderResult(output_path=output)

        result = generate_karaoke("https://youtube.com/watch?v=x", output)
        assert result.output_path == output
