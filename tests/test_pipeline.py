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
from karaoke.pipeline import _should_skip_separation, generate_karaoke


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
        mock_fetch.assert_called_once_with("Test Song", artist=None)
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
    def test_skips_separation_when_vocals_volume_1(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        output = tmp_path / "output.mp4"
        audio_path = tmp_path / "a.wav"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=audio_path,
            title="T",
            video_id="x",
        )
        mock_fetch.return_value = None
        mock_align.return_value = AlignmentResult(lines=[])
        mock_render.return_value = RenderResult(output_path=output)

        generate_karaoke(
            "https://youtube.com/watch?v=x", output,
            work_dir=tmp_path / "w", vocals_volume=1.0,
        )

        mock_separate.assert_not_called()
        # Align should receive original audio, not separated vocals
        assert mock_align.call_args[0][0] == audio_path
        # Render should use original audio as instrumental, no vocals mixing
        render_kwargs = mock_render.call_args
        assert render_kwargs[0][1] == audio_path  # instrumental_path positional arg
        assert render_kwargs.kwargs.get("vocals_path") is None

    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_separation_runs_when_keep_vocals_false_even_with_volume_1(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
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

        generate_karaoke(
            "https://youtube.com/watch?v=x", output,
            work_dir=tmp_path / "w", keep_vocals=False, vocals_volume=1.0,
        )

        mock_separate.assert_called_once()
        render_kwargs = mock_render.call_args
        assert render_kwargs.kwargs.get("vocals_path") is None

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


    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_uses_track_for_lyrics_when_available(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="Balam Pichkari (Full Video) | Yeh Jawaani Hai Deewani",
            video_id="x",
            track="Balam Pichkari",
            artist="Vishal Dadlani",
        )
        mock_fetch.return_value = None
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "v.wav",
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(lines=[])
        mock_render.return_value = RenderResult(output_path=output)

        generate_karaoke("https://youtube.com/watch?v=x", output, work_dir=tmp_path / "w")

        # Should use track name instead of noisy title, and pass artist
        mock_fetch.assert_called_once_with("Balam Pichkari", artist="Vishal Dadlani")

    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_falls_back_to_title_when_no_track(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="Some Song",
            video_id="x",
        )
        mock_fetch.return_value = None
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "v.wav",
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(lines=[])
        mock_render.return_value = RenderResult(output_path=output)

        generate_karaoke("https://youtube.com/watch?v=x", output, work_dir=tmp_path / "w")

        # Should fall back to title when track is None
        mock_fetch.assert_called_once_with("Some Song", artist=None)


    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_non_english_pipeline_hindi(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        """Integration test: Hindi video with noisy title, track metadata, and language flag.

        Verifies the full non-English flow:
        1. Track metadata is preferred over noisy YouTube title for lyrics search
        2. Artist is passed to lyrics search for better matching
        3. Language is forwarded to align stage
        4. Language is forwarded to render stage (for font selection)
        """
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="Balam Pichkari (Full Video) | Yeh Jawaani Hai Deewani | Pritam | Ranbir Kapoor, Deepika | Holi Song",
            video_id="0WtRNGubWGA",
            track="Balam Pichkari",
            artist="Vishal Dadlani",
        )
        mock_fetch.return_value = LyricsResult(plain_text="Balam pichkari jo tune mujhe maari")
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "v.wav",
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(
            lines=[TimedLine(words=[TimedWord(text="Balam", start=0.0, end=0.5)])]
        )
        mock_render.return_value = RenderResult(output_path=output)

        result = generate_karaoke(
            "https://youtu.be/0WtRNGubWGA", output,
            work_dir=tmp_path / "w", language="hi",
        )

        assert result.output_path == output

        # Lyrics search used track name + artist, not the noisy title
        mock_fetch.assert_called_once_with("Balam Pichkari", artist="Vishal Dadlani")

        # Language was forwarded to align
        align_kwargs = mock_align.call_args.kwargs
        assert align_kwargs.get("language") == "hi"

        # Language was forwarded to render (for font selection)
        render_kwargs = mock_render.call_args.kwargs
        assert render_kwargs.get("language") == "hi"

    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_non_english_pipeline_japanese(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        """Integration test: Japanese video with CJK title and no track metadata.

        Verifies:
        1. Falls back to title when no track metadata
        2. Language is forwarded to align and render stages
        """
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="残酷な天使のテーゼ (Official Video)",
            video_id="abc",
        )
        mock_fetch.return_value = LyricsResult(plain_text="残酷な天使のように")
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "v.wav",
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(
            lines=[TimedLine(words=[TimedWord(text="残", start=0.0, end=0.5)])]
        )
        mock_render.return_value = RenderResult(output_path=output)

        result = generate_karaoke(
            "https://youtube.com/watch?v=abc", output,
            work_dir=tmp_path / "w", language="ja",
        )

        assert result.output_path == output

        # Raw title passed to fetch_lyrics (title cleaning happens inside fetch_lyrics)
        mock_fetch.assert_called_once_with("残酷な天使のテーゼ (Official Video)", artist=None)

        # Language forwarded to align and render
        assert mock_align.call_args.kwargs.get("language") == "ja"
        assert mock_render.call_args.kwargs.get("language") == "ja"

    @patch("karaoke.pipeline.render")
    @patch("karaoke.pipeline.align")
    @patch("karaoke.pipeline.separate")
    @patch("karaoke.pipeline.fetch_lyrics")
    @patch("karaoke.pipeline.download")
    def test_non_english_pipeline_no_language_flag(self, mock_download, mock_fetch, mock_separate, mock_align, mock_render, tmp_path):
        """Integration test: non-English video without --language flag.

        Verifies that omitting --language still works (auto-detect) and
        language=None is forwarded correctly.
        """
        output = tmp_path / "output.mp4"

        mock_download.return_value = DownloadResult(
            video_path=tmp_path / "v.mp4",
            audio_path=tmp_path / "a.wav",
            title="Balam Pichkari (Full Video) | Yeh Jawaani Hai Deewani",
            video_id="x",
            track="Balam Pichkari",
            artist="Vishal Dadlani",
        )
        mock_fetch.return_value = LyricsResult(plain_text="Balam pichkari")
        mock_separate.return_value = SeparationResult(
            vocals_path=tmp_path / "v.wav",
            instrumental_path=tmp_path / "i.wav",
        )
        mock_align.return_value = AlignmentResult(lines=[])
        mock_render.return_value = RenderResult(output_path=output)

        # No language flag — auto-detect
        generate_karaoke("https://youtube.com/watch?v=x", output, work_dir=tmp_path / "w")

        # Language defaults to None
        assert mock_align.call_args.kwargs.get("language") is None
        assert mock_render.call_args.kwargs.get("language") is None


class TestShouldSkipSeparation:
    def test_skip_when_keep_vocals_and_full_volume(self):
        assert _should_skip_separation(keep_vocals=True, vocals_volume=1.0) is True

    def test_no_skip_when_reduced_volume(self):
        assert _should_skip_separation(keep_vocals=True, vocals_volume=0.3) is False

    def test_no_skip_when_no_vocals(self):
        assert _should_skip_separation(keep_vocals=False, vocals_volume=1.0) is False

    def test_skip_when_volume_above_1(self):
        assert _should_skip_separation(keep_vocals=True, vocals_volume=1.5) is True
