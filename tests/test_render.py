"""Tests for the render stage."""

from pathlib import Path
from unittest.mock import patch

import pytest

from karaoke.models import AlignmentResult, TimedLine, TimedWord
from karaoke.render import (
    _build_background_text,
    _build_karaoke_text,
    _format_ass_time,
    _generate_ass,
    render,
)


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


class TestBuildBackgroundText:
    def test_wraps_in_parentheses(self):
        line = TimedLine(
            words=[TimedWord(text="ooh", start=0.0, end=0.5)],
            is_background=True,
        )
        result = _build_background_text(line)
        assert result.startswith("(")
        assert result.endswith(")")
        assert "\\kf50" in result
        assert "ooh" in result

    def test_multiple_words(self):
        line = TimedLine(
            words=[
                TimedWord(text="ooh", start=0.0, end=0.5),
                TimedWord(text="ahh", start=0.5, end=1.0),
            ],
            is_background=True,
        )
        result = _build_background_text(line)
        assert result == "({\\kf50}ooh {\\kf50}ahh)"


class TestGenerateAssBackground:
    def test_background_style_present(self, tmp_path):
        alignment = AlignmentResult(
            lines=[TimedLine(words=[TimedWord(text="test", start=0.0, end=1.0)])]
        )
        ass_path = tmp_path / "test.ass"
        _generate_ass(alignment, ass_path)
        content = ass_path.read_text()
        assert "Style: Background," in content

    def test_background_line_uses_background_style(self, tmp_path):
        alignment = AlignmentResult(
            lines=[
                TimedLine(words=[TimedWord(text="lead", start=0.0, end=1.0)]),
                TimedLine(
                    words=[TimedWord(text="ooh", start=0.0, end=1.0)],
                    is_background=True,
                ),
            ]
        )
        ass_path = tmp_path / "test.ass"
        _generate_ass(alignment, ass_path)
        content = ass_path.read_text()
        dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
        assert len(dialogue_lines) == 2

        # Primary line: Layer 0, Karaoke style
        assert dialogue_lines[0].startswith("Dialogue: 0,")
        assert ",Karaoke," in dialogue_lines[0]

        # Background line: Layer 1, Background style, parenthesized
        assert dialogue_lines[1].startswith("Dialogue: 1,")
        assert ",Background," in dialogue_lines[1]
        assert "({\\" in dialogue_lines[1]

    def test_mixed_primary_and_background(self, tmp_path):
        alignment = AlignmentResult(
            lines=[
                TimedLine(words=[TimedWord(text="verse", start=0.0, end=1.0)]),
                TimedLine(
                    words=[TimedWord(text="bg", start=0.0, end=1.0)],
                    is_background=True,
                ),
                TimedLine(words=[TimedWord(text="chorus", start=2.0, end=3.0)]),
            ]
        )
        ass_path = tmp_path / "test.ass"
        _generate_ass(alignment, ass_path)
        content = ass_path.read_text()
        dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
        assert len(dialogue_lines) == 3
        assert ",Karaoke," in dialogue_lines[0]
        assert ",Background," in dialogue_lines[1]
        assert ",Karaoke," in dialogue_lines[2]
