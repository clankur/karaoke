"""Tests for the render stage."""

from pathlib import Path
from unittest.mock import patch

import pytest

from karaoke.models import AlignmentResult, TimedLine, TimedWord
from karaoke.render import _build_karaoke_text, _format_ass_time, _generate_ass, _select_font, render


class TestFormatAssTime:
    def test_zero(self):
        assert _format_ass_time(0.0) == "0:00:00.00"

    def test_simple_seconds(self):
        assert _format_ass_time(5.5) == "0:00:05.50"

    def test_minutes_and_seconds(self):
        assert _format_ass_time(125.75) == "0:02:05.75"

    def test_hours(self):
        assert _format_ass_time(3661.0) == "1:01:01.00"


class TestBuildKaraokeText:
    def test_single_word(self):
        line = TimedLine(words=[TimedWord(text="hello", start=0.0, end=0.5)])
        result = _build_karaoke_text(line)
        assert result == "{\\kf50}hello"

    def test_multiple_words(self):
        line = TimedLine(
            words=[
                TimedWord(text="hello", start=0.0, end=0.5),
                TimedWord(text="world", start=0.5, end=1.0),
            ]
        )
        result = _build_karaoke_text(line)
        assert result == "{\\kf50}hello {\\kf50}world"

    def test_minimum_duration(self):
        line = TimedLine(words=[TimedWord(text="a", start=0.0, end=0.001)])
        result = _build_karaoke_text(line)
        # Should clamp to minimum 1 centisecond
        assert result == "{\\kf1}a"

    def test_cjk_no_spaces(self):
        """Adjacent CJK characters should not have spaces between them."""
        line = TimedLine(
            words=[
                TimedWord(text="こ", start=0.0, end=0.5),
                TimedWord(text="ん", start=0.5, end=1.0),
                TimedWord(text="に", start=1.0, end=1.5),
            ]
        )
        result = _build_karaoke_text(line)
        assert result == "{\\kf50}こ{\\kf50}ん{\\kf50}に"

    def test_mixed_cjk_and_latin(self):
        """Spaces between Latin words, no spaces between CJK characters."""
        line = TimedLine(
            words=[
                TimedWord(text="Hello", start=0.0, end=0.5),
                TimedWord(text="こ", start=0.5, end=1.0),
                TimedWord(text="ん", start=1.0, end=1.5),
                TimedWord(text="World", start=1.5, end=2.0),
            ]
        )
        result = _build_karaoke_text(line)
        assert result == "{\\kf50}Hello {\\kf50}こ{\\kf50}ん {\\kf50}World"


class TestSelectFont:
    def test_default_font(self):
        assert _select_font(None) == "Arial"

    def test_english_font(self):
        assert _select_font("en") == "Arial"

    def test_japanese_font(self):
        assert _select_font("ja") == "Noto Sans CJK"

    def test_korean_font(self):
        assert _select_font("ko") == "Noto Sans CJK"

    def test_chinese_font(self):
        assert _select_font("zh") == "Noto Sans CJK"

    def test_hindi_font(self):
        assert _select_font("hi") == "Noto Sans"

    def test_thai_font(self):
        assert _select_font("th") == "Noto Sans"

    def test_arabic_font(self):
        assert _select_font("ar") == "Noto Sans"


class TestGenerateAss:
    def test_creates_valid_ass_file(self, tmp_path):
        alignment = AlignmentResult(
            lines=[
                TimedLine(
                    words=[
                        TimedWord(text="hello", start=0.0, end=0.5),
                        TimedWord(text="world", start=0.5, end=1.0),
                    ]
                ),
            ]
        )
        ass_path = tmp_path / "test.ass"
        _generate_ass(alignment, ass_path)

        content = ass_path.read_text()
        assert "[Script Info]" in content
        assert "[V4+ Styles]" in content
        assert "[Events]" in content
        assert "Dialogue:" in content
        assert "\\kf50" in content

    def test_skips_empty_lines(self, tmp_path):
        alignment = AlignmentResult(lines=[TimedLine()])
        ass_path = tmp_path / "test.ass"
        _generate_ass(alignment, ass_path)

        content = ass_path.read_text()
        assert "Dialogue:" not in content

    def test_uses_default_arial_font(self, tmp_path):
        alignment = AlignmentResult(
            lines=[TimedLine(words=[TimedWord(text="test", start=0.0, end=1.0)])]
        )
        ass_path = tmp_path / "test.ass"
        _generate_ass(alignment, ass_path)

        content = ass_path.read_text()
        assert "Karaoke,Arial,60" in content

    def test_uses_custom_font(self, tmp_path):
        alignment = AlignmentResult(
            lines=[TimedLine(words=[TimedWord(text="test", start=0.0, end=1.0)])]
        )
        ass_path = tmp_path / "test.ass"
        _generate_ass(alignment, ass_path, font_name="Noto Sans CJK")

        content = ass_path.read_text()
        assert "Karaoke,Noto Sans CJK,60" in content
        assert "Arial" not in content


class TestRender:
    def test_missing_video_raises(self, tmp_path):
        alignment = AlignmentResult(lines=[])
        with pytest.raises(FileNotFoundError, match="Video file not found"):
            render(
                tmp_path / "missing.mp4",
                tmp_path / "instrumental.wav",
                alignment,
                tmp_path / "output.mp4",
            )

    def test_missing_instrumental_raises(self, tmp_path):
        video = tmp_path / "video.mp4"
        video.touch()
        alignment = AlignmentResult(lines=[])
        with pytest.raises(FileNotFoundError, match="Instrumental file not found"):
            render(
                video,
                tmp_path / "missing.wav",
                alignment,
                tmp_path / "output.mp4",
            )

    def test_ffmpeg_failure_raises(self, tmp_path):
        video = tmp_path / "video.mp4"
        video.touch()
        instrumental = tmp_path / "instrumental.wav"
        instrumental.touch()
        alignment = AlignmentResult(
            lines=[
                TimedLine(words=[TimedWord(text="test", start=0.0, end=1.0)])
            ]
        )

        mock_result = type("Result", (), {"returncode": 1, "stderr": "ffmpeg error"})()
        with patch("karaoke.render.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="ffmpeg failed"):
                render(video, instrumental, alignment, tmp_path / "output.mp4")

    def test_missing_vocals_raises(self, tmp_path):
        video = tmp_path / "video.mp4"
        video.touch()
        instrumental = tmp_path / "instrumental.wav"
        instrumental.touch()
        alignment = AlignmentResult(lines=[])
        with pytest.raises(FileNotFoundError, match="Vocals file not found"):
            render(
                video, instrumental, alignment, tmp_path / "output.mp4",
                vocals_path=tmp_path / "missing_vocals.wav",
            )

    def test_vocals_mixing_uses_filter_complex(self, tmp_path):
        video = tmp_path / "video.mp4"
        video.touch()
        instrumental = tmp_path / "instrumental.wav"
        instrumental.touch()
        vocals = tmp_path / "vocals.wav"
        vocals.touch()
        alignment = AlignmentResult(
            lines=[TimedLine(words=[TimedWord(text="test", start=0.0, end=1.0)])]
        )

        mock_result = type("Result", (), {"returncode": 0, "stderr": ""})()
        with patch("karaoke.render.subprocess.run", return_value=mock_result) as mock_run:
            render(
                video, instrumental, alignment, tmp_path / "output.mp4",
                vocals_path=vocals, vocals_volume=0.3,
            )
            cmd = mock_run.call_args[0][0]
            cmd_str = " ".join(cmd)
            assert "-filter_complex" in cmd_str
            assert "amix" in cmd_str
            assert "volume=0.3" in cmd_str
