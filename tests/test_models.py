"""Tests for karaoke data models."""

from karaoke.models import AlignmentResult, TimedLine, TimedWord


class TestTimedWord:
    def test_fields(self):
        w = TimedWord(text="hello", start=1.0, end=1.5)
        assert w.text == "hello"
        assert w.start == 1.0
        assert w.end == 1.5


class TestTimedLine:
    def test_properties(self):
        words = [
            TimedWord(text="hello", start=1.0, end=1.3),
            TimedWord(text="world", start=1.4, end=1.8),
        ]
        line = TimedLine(words=words)
        assert line.start == 1.0
        assert line.end == 1.8
        assert line.text == "hello world"

    def test_empty_line_defaults(self):
        line = TimedLine()
        assert line.start == 0.0
        assert line.end == 0.0
        assert line.text == ""


class TestAlignmentResult:
    def test_lines(self):
        lines = [
            TimedLine(words=[TimedWord(text="a", start=0.0, end=0.5)]),
            TimedLine(words=[TimedWord(text="b", start=1.0, end=1.5)]),
        ]
        result = AlignmentResult(lines=lines)
        assert len(result.lines) == 2
