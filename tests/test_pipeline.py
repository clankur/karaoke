"""Tests for the pipeline orchestrator."""

from pathlib import Path
from unittest.mock import patch

from karaoke.models import (
    AlignmentResult,
    DownloadResult,
    LyricsResult,
    RenderResult,
    SeparationResult,
    SyncedLine,
    TimedLine,
    TimedWord,
)
from karaoke.pipeline import generate_karaoke


class TestGenerateKaraoke:
    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_full_pipeline(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        work_dir = tmp_path / "work"
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "video.mp4",
            audio_path=tmp_path / "audio.wav",
            title="Test Song",
            video_id="abc",
        )
        mock_fetch.return_value = LyricsResult(plain_text="Hello world")
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
        mock_fetch.assert_called_once_with("Test Song")
        mock_separate.assert_called_once()
        # Verify lyrics were passed to align
        align_kwargs = mock_align.call_args
        lyrics_arg = align_kwargs.kwargs.get("lyrics")
        assert isinstance(lyrics_arg, LyricsResult)
        assert lyrics_arg.plain_text == "Hello world"
        mock_render.assert_called_once()

    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_passes_vocals_to_render_by_default(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        output = tmp_path / "output.mp4"
        vocals_path = tmp_path / "vocals.wav"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="T",
            video_id="x",
        )
        mock_fetch.return_value = None
        mock_separate.return_value = SeparationResult(
            vocals_path=vocals_path,
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(lines=[])
        mock_render.return_value = RenderResult(output_path=output)

        generate_karaoke("https://youtube.com/watch?v=x", output, work_dir=tmp_path / "w")

        render_kwargs = mock_render.call_args
        assert render_kwargs.kwargs.get("vocals_path") == vocals_path
        assert render_kwargs.kwargs.get("vocals_volume") == 0.3

    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_no_vocals_when_keep_vocals_false(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="T",
            video_id="x",
        )
        mock_fetch.return_value = None
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "v.wav",
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(lines=[])
        mock_render.return_value = RenderResult(output_path=output)

        generate_karaoke("https://youtube.com/watch?v=x", output, work_dir=tmp_path / "w", keep_vocals=False)

        render_kwargs = mock_render.call_args
        assert render_kwargs.kwargs.get("vocals_path") is None

    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_uses_temp_dir_when_no_work_dir(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="T",
            video_id="x",
        )
        mock_fetch.return_value = None
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "v.wav",
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(lines=[])
        mock_render.return_value = RenderResult(output_path=output)

        result = generate_karaoke("https://youtube.com/watch?v=x", output)
        assert result.output_path == output

    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_no_synced_lyrics_strips_timestamps(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="Test Song",
            video_id="x",
        )
        mock_fetch.return_value = LyricsResult(
            plain_text="Hello world\nGoodbye moon",
            synced_lines=[
                SyncedLine(timestamp=10.0, text="Hello world"),
                SyncedLine(timestamp=15.0, text="Goodbye moon"),
            ],
        )
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "v.wav",
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(lines=[])
        mock_render.return_value = RenderResult(output_path=output)

        generate_karaoke(
            "https://youtube.com/watch?v=x", output,
            work_dir=tmp_path / "w", use_synced_lyrics=False,
        )

        lyrics_arg = mock_align.call_args.kwargs.get("lyrics")
        assert isinstance(lyrics_arg, LyricsResult)
        assert lyrics_arg.plain_text == "Hello world\nGoodbye moon"
        assert not lyrics_arg.has_synced_timestamps
