"""Tests for karaoke data models."""

from karaoke.models import AlignmentResult, LyricsResult, SyncedLine, TimedLine, TimedWord


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

    def test_default_not_background(self):
        line = TimedLine()
        assert line.is_background is False

    def test_background_flag(self):
        words = [TimedWord(text="ooh", start=1.0, end=1.5)]
        line = TimedLine(words=words, is_background=True)
        assert line.is_background is True
        assert line.text == "ooh"


class TestSyncedLine:
    def test_fields(self):
        sl = SyncedLine(timestamp=12.34, text="Hello world")
        assert sl.timestamp == 12.34
        assert sl.text == "Hello world"


class TestLyricsResult:
    def test_has_synced_timestamps_true(self):
        result = LyricsResult(
            plain_text="Hello",
            synced_lines=[SyncedLine(timestamp=1.0, text="Hello")],
        )
        assert result.has_synced_timestamps

    def test_has_synced_timestamps_false_when_none(self):
        result = LyricsResult(plain_text="Hello")
        assert not result.has_synced_timestamps

    def test_has_synced_timestamps_false_when_empty(self):
        result = LyricsResult(plain_text="Hello", synced_lines=[])
        assert not result.has_synced_timestamps


class TestAlignmentResult:
    def test_lines(self):
        lines = [
            TimedLine(words=[TimedWord(text="a", start=0.0, end=0.5)]),
            TimedLine(words=[TimedWord(text="b", start=1.0, end=1.5)]),
        ]
        result = AlignmentResult(lines=lines)
        assert len(result.lines) == 2
