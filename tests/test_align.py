"""Tests for the alignment stage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from karaoke.align import (
    _detect_simultaneous_lines,
    _distribute_word_timing,
    _group_words_by_synced_lines,
    _group_words_into_lines,
    _lines_from_synced,
    align,
)
from karaoke.models import LyricsResult, SyncedLine, TimedWord


class TestGroupWordsIntoLines:
    def test_exact_fit(self):
        words = [TimedWord(text=f"w{i}", start=float(i), end=float(i) + 0.5) for i in range(7)]
        lines = _group_words_into_lines(words, words_per_line=7)
        assert len(lines) == 1
        assert len(lines[0].words) == 7

    def test_overflow_creates_new_line(self):
        words = [TimedWord(text=f"w{i}", start=float(i), end=float(i) + 0.5) for i in range(10)]
        lines = _group_words_into_lines(words, words_per_line=7)
        assert len(lines) == 2
        assert len(lines[0].words) == 7
        assert len(lines[1].words) == 3

    def test_empty_input(self):
        lines = _group_words_into_lines([], words_per_line=7)
        assert lines == []

    def test_single_word(self):
        words = [TimedWord(text="solo", start=0.0, end=1.0)]
        lines = _group_words_into_lines(words, words_per_line=7)
        assert len(lines) == 1
        assert lines[0].text == "solo"


class TestGroupWordsBySyncedLines:
    def test_words_grouped_by_lrc_boundaries(self):
        """Words are assigned to LRC lines based on their midpoint timestamp."""
        words = [
            TimedWord(text="Hello", start=10.0, end=10.5),
            TimedWord(text="world", start=10.5, end=11.0),
            TimedWord(text="Goodbye", start=15.0, end=15.5),
            TimedWord(text="moon", start=15.5, end=16.0),
        ]
        synced = [
            SyncedLine(timestamp=10.0, text="Hello world"),
            SyncedLine(timestamp=15.0, text="Goodbye moon"),
        ]
        lines = _group_words_by_synced_lines(words, synced, words_per_line=7)
        assert len(lines) == 2
        assert lines[0].text == "Hello world"
        assert lines[1].text == "Goodbye moon"

    def test_words_use_whisper_timestamps(self):
        """Word-level timing should come from whisper, not LRC estimation."""
        words = [
            TimedWord(text="Hello", start=10.2, end=10.7),
            TimedWord(text="world", start=10.8, end=11.3),
        ]
        synced = [SyncedLine(timestamp=10.0, text="Hello world")]
        lines = _group_words_by_synced_lines(words, synced, words_per_line=7)
        assert lines[0].words[0].start == 10.2
        assert lines[0].words[0].end == 10.7
        assert lines[0].words[1].start == 10.8
        assert lines[0].words[1].end == 11.3

    def test_long_line_splits_by_words_per_line(self):
        words = [TimedWord(text=f"w{i}", start=float(i), end=float(i) + 0.5) for i in range(10)]
        synced = [SyncedLine(timestamp=0.0, text="all words")]
        lines = _group_words_by_synced_lines(words, synced, words_per_line=7)
        assert len(lines) == 2
        assert len(lines[0].words) == 7
        assert len(lines[1].words) == 3

    def test_empty_inputs(self):
        assert _group_words_by_synced_lines([], [], words_per_line=7) == []
        synced = [SyncedLine(timestamp=0.0, text="text")]
        assert _group_words_by_synced_lines([], synced, words_per_line=7) == []

    def test_skips_lines_with_no_words(self):
        """If no whisper words fall within an LRC line's range, that line is skipped."""
        words = [TimedWord(text="hello", start=15.0, end=15.5)]
        synced = [
            SyncedLine(timestamp=0.0, text="First line"),
            SyncedLine(timestamp=10.0, text="Second line"),
        ]
        lines = _group_words_by_synced_lines(words, synced, words_per_line=7)
        assert len(lines) == 1
        assert lines[0].text == "hello"


class TestLinesFromSynced:
    def test_basic_synced_lines(self):
        synced = [
            SyncedLine(timestamp=10.0, text="Hello world"),
            SyncedLine(timestamp=15.0, text="Goodbye moon"),
        ]
        lines = _lines_from_synced(synced, words_per_line=7)
        assert len(lines) == 2
        assert lines[0].text == "Hello world"
        assert lines[0].start == 10.0
        assert abs(lines[0].end - 15.0) < 0.01
        assert lines[1].text == "Goodbye moon"
        assert lines[1].start == 15.0

    def test_last_line_gets_default_duration(self):
        synced = [SyncedLine(timestamp=10.0, text="Only line")]
        lines = _lines_from_synced(synced, words_per_line=7)
        assert len(lines) == 1
        assert lines[0].start == 10.0
        assert abs(lines[0].end - 13.0) < 0.01

    def test_long_line_splits_by_words_per_line(self):
        text = " ".join(f"word{i}" for i in range(10))
        synced = [
            SyncedLine(timestamp=0.0, text=text),
            SyncedLine(timestamp=10.0, text="next"),
        ]
        lines = _lines_from_synced(synced, words_per_line=7)
        assert len(lines) == 3  # 7 + 3 from first, 1 from second
        assert len(lines[0].words) == 7
        assert len(lines[1].words) == 3

    def test_skips_empty_text(self):
        synced = [
            SyncedLine(timestamp=5.0, text=""),
            SyncedLine(timestamp=10.0, text="Real lyrics"),
        ]
        lines = _lines_from_synced(synced, words_per_line=7)
        assert len(lines) == 1
        assert lines[0].text == "Real lyrics"


class TestDistributeWordTiming:
    def test_proportional_distribution(self):
        words = ["Hi", "World"]  # 2 chars vs 5 chars
        result = _distribute_word_timing(words, start=0.0, end=7.0)
        assert len(result) == 2
        assert result[0].text == "Hi"
        assert result[0].start == 0.0
        assert abs(result[0].end - 2.0) < 0.01
        assert result[1].text == "World"
        assert abs(result[1].start - 2.0) < 0.01
        assert abs(result[1].end - 7.0) < 0.01

    def test_empty_words(self):
        result = _distribute_word_timing([], start=0.0, end=5.0)
        assert result == []

    def test_single_word_gets_full_duration(self):
        result = _distribute_word_timing(["hello"], start=1.0, end=3.0)
        assert len(result) == 1
        assert result[0].start == 1.0
        assert result[0].end == 3.0


class TestAlign:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Vocals file not found"):
            align(tmp_path / "missing.wav")

    @patch("karaoke.align.stable_whisper")
    def test_successful_alignment(self, mock_stable_whisper, tmp_path):
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        mock_model = MagicMock()
        mock_stable_whisper.load_model.return_value = mock_model

        mock_word1 = MagicMock()
        mock_word1.word = "hello"
        mock_word1.start = 0.0
        mock_word1.end = 0.5

        mock_word2 = MagicMock()
        mock_word2.word = "world"
        mock_word2.start = 0.5
        mock_word2.end = 1.0

        mock_segment = MagicMock()
        mock_segment.words = [mock_word1, mock_word2]

        mock_result = MagicMock()
        mock_result.segments = [mock_segment]
        mock_model.transcribe.return_value = mock_result

        result = align(vocals, model_size="tiny", words_per_line=7)
        assert len(result.lines) == 1
        assert len(result.lines[0].words) == 2
        assert result.lines[0].text == "hello world"

    @patch("karaoke.align.stable_whisper")
    def test_transcription_failure_raises(self, mock_stable_whisper, tmp_path):
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        mock_model = MagicMock()
        mock_stable_whisper.load_model.return_value = mock_model
        mock_model.transcribe.side_effect = Exception("model error")

        with pytest.raises(RuntimeError, match="stable-ts transcription failed"):
            align(vocals)

    @patch("karaoke.align.stable_whisper")
    def test_uses_align_when_plain_lyrics_provided(self, mock_stable_whisper, tmp_path):
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        mock_model = MagicMock()
        mock_stable_whisper.load_model.return_value = mock_model

        mock_word = MagicMock()
        mock_word.word = "hello"
        mock_word.start = 0.0
        mock_word.end = 0.5

        mock_segment = MagicMock()
        mock_segment.words = [mock_word]

        mock_result = MagicMock()
        mock_result.segments = [mock_segment]
        mock_model.align.return_value = mock_result

        lyrics = LyricsResult(plain_text="hello")
        result = align(vocals, lyrics=lyrics, model_size="tiny")

        mock_model.align.assert_called_once()
        mock_model.transcribe.assert_not_called()
        assert result.lines[0].text == "hello"

    @patch("karaoke.align.stable_whisper")
    def test_falls_back_to_transcribe_when_align_fails(self, mock_stable_whisper, tmp_path):
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        mock_model = MagicMock()
        mock_stable_whisper.load_model.return_value = mock_model

        mock_model.align.side_effect = Exception("alignment failed")

        mock_word = MagicMock()
        mock_word.word = "fallback"
        mock_word.start = 0.0
        mock_word.end = 1.0

        mock_segment = MagicMock()
        mock_segment.words = [mock_word]

        mock_result = MagicMock()
        mock_result.segments = [mock_segment]
        mock_model.transcribe.return_value = mock_result

        lyrics = LyricsResult(plain_text="some lyrics")
        result = align(vocals, lyrics=lyrics)
        mock_model.transcribe.assert_called_once()
        assert result.lines[0].text == "fallback"

    @patch("karaoke.align.stable_whisper")
    def test_synced_lyrics_uses_whisper_for_word_timing(self, mock_stable_whisper, tmp_path):
        """Synced lyrics use whisper alignment for word-level timing, LRC for line grouping."""
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        mock_model = MagicMock()
        mock_stable_whisper.load_model.return_value = mock_model

        # Whisper returns word-level timing
        mock_word1 = MagicMock()
        mock_word1.word = "Hello"
        mock_word1.start = 10.2
        mock_word1.end = 10.7

        mock_word2 = MagicMock()
        mock_word2.word = "world"
        mock_word2.start = 10.8
        mock_word2.end = 11.3

        mock_word3 = MagicMock()
        mock_word3.word = "Goodbye"
        mock_word3.start = 15.1
        mock_word3.end = 15.6

        mock_segment = MagicMock()
        mock_segment.words = [mock_word1, mock_word2, mock_word3]

        mock_result = MagicMock()
        mock_result.segments = [mock_segment]
        mock_model.align.return_value = mock_result

        lyrics = LyricsResult(
            plain_text="Hello world\nGoodbye moon",
            synced_lines=[
                SyncedLine(timestamp=10.0, text="Hello world"),
                SyncedLine(timestamp=15.0, text="Goodbye moon"),
            ],
        )

        result = align(vocals, lyrics=lyrics, model_size="tiny")

        # Whisper was used for alignment
        mock_model.align.assert_called_once()
        # Words are grouped by LRC line boundaries
        assert len(result.lines) == 2
        assert result.lines[0].text == "Hello world"
        # Word timing comes from whisper, not LRC estimation
        assert result.lines[0].words[0].start == 10.2
        assert result.lines[0].words[0].end == 10.7
        assert result.lines[1].text == "Goodbye"
        assert result.lines[1].words[0].start == 15.1

    @patch("karaoke.align.stable_whisper")
    def test_synced_lyrics_falls_back_to_estimated_timing(self, mock_stable_whisper, tmp_path):
        """When whisper fails with synced lyrics, fall back to LRC-based estimated timing."""
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        mock_model = MagicMock()
        mock_stable_whisper.load_model.return_value = mock_model
        mock_model.align.side_effect = Exception("alignment failed")

        lyrics = LyricsResult(
            plain_text="Hello world\nGoodbye moon",
            synced_lines=[
                SyncedLine(timestamp=10.0, text="Hello world"),
                SyncedLine(timestamp=15.0, text="Goodbye moon"),
            ],
        )

        result = align(vocals, lyrics=lyrics, model_size="tiny")

        # Should still produce output from LRC timestamps
        assert len(result.lines) == 2
        assert result.lines[0].text == "Hello world"
        assert result.lines[0].start == 10.0
        # Transcribe should NOT be called — we have LRC fallback
        mock_model.transcribe.assert_not_called()


class TestDetectSimultaneousLines:
    def test_empty(self):
        assert _detect_simultaneous_lines([]) == []

    def test_single_line(self):
        lines = [SyncedLine(timestamp=10.0, text="Hello")]
        result = _detect_simultaneous_lines(lines)
        assert result == [(lines[0], False)]

    def test_no_overlaps(self):
        lines = [
            SyncedLine(timestamp=10.0, text="Hello"),
            SyncedLine(timestamp=15.0, text="World"),
        ]
        result = _detect_simultaneous_lines(lines)
        assert result == [(lines[0], False), (lines[1], False)]

    def test_same_timestamp(self):
        lines = [
            SyncedLine(timestamp=10.0, text="Lead vocal"),
            SyncedLine(timestamp=10.0, text="Background vocal"),
        ]
        result = _detect_simultaneous_lines(lines)
        assert result[0] == (lines[0], False)
        assert result[1] == (lines[1], True)

    def test_near_threshold(self):
        lines = [
            SyncedLine(timestamp=10.0, text="Lead"),
            SyncedLine(timestamp=10.4, text="Background"),
        ]
        result = _detect_simultaneous_lines(lines)
        assert result[1][1] is True  # within 0.5s threshold

    def test_outside_threshold(self):
        lines = [
            SyncedLine(timestamp=10.0, text="Line one"),
            SyncedLine(timestamp=10.6, text="Line two"),
        ]
        result = _detect_simultaneous_lines(lines)
        assert result[1][1] is False  # 0.6s > 0.5s threshold

    def test_three_simultaneous(self):
        lines = [
            SyncedLine(timestamp=10.0, text="Lead"),
            SyncedLine(timestamp=10.1, text="Backing 1"),
            SyncedLine(timestamp=10.2, text="Backing 2"),
        ]
        result = _detect_simultaneous_lines(lines)
        assert result[0][1] is False
        assert result[1][1] is True
        assert result[2][1] is True

    def test_mixed(self):
        lines = [
            SyncedLine(timestamp=10.0, text="Lead 1"),
            SyncedLine(timestamp=10.1, text="Background 1"),
            SyncedLine(timestamp=20.0, text="Lead 2"),
            SyncedLine(timestamp=25.0, text="Lead 3"),
        ]
        result = _detect_simultaneous_lines(lines)
        assert [is_bg for _, is_bg in result] == [False, True, False, False]


class TestGroupWordsBySyncedLinesSimultaneous:
    def test_simultaneous_lines_produce_background(self):
        words = [
            TimedWord(text="Lead", start=10.0, end=10.5),
            TimedWord(text="vocals", start=10.5, end=11.0),
        ]
        synced = [
            SyncedLine(timestamp=10.0, text="Lead vocals"),
            SyncedLine(timestamp=10.1, text="ooh ahh"),
        ]
        lines = _group_words_by_synced_lines(words, synced, words_per_line=7)

        primary = [l for l in lines if not l.is_background]
        background = [l for l in lines if l.is_background]

        assert len(primary) == 1
        assert primary[0].text == "Lead vocals"
        assert len(background) == 1
        assert background[0].text == "ooh ahh"
        assert background[0].is_background is True

    def test_all_whisper_words_go_to_primary(self):
        words = [
            TimedWord(text="Hello", start=10.0, end=10.5),
            TimedWord(text="world", start=10.5, end=11.0),
        ]
        synced = [
            SyncedLine(timestamp=10.0, text="Hello world"),
            SyncedLine(timestamp=10.0, text="background words"),
        ]
        lines = _group_words_by_synced_lines(words, synced, words_per_line=7)
        primary = [l for l in lines if not l.is_background]
        # All whisper words assigned to primary
        assert primary[0].words[0].start == 10.0
        assert primary[0].words[1].start == 10.5

    def test_background_gets_estimated_timing(self):
        words = [
            TimedWord(text="Lead", start=10.0, end=11.0),
        ]
        synced = [
            SyncedLine(timestamp=10.0, text="Lead"),
            SyncedLine(timestamp=10.1, text="bg"),
        ]
        lines = _group_words_by_synced_lines(words, synced, words_per_line=7)
        background = [l for l in lines if l.is_background]
        assert len(background) == 1
        # Background timing is estimated, not from whisper
        assert background[0].words[0].start == 10.0
        assert background[0].words[0].end == 11.0


class TestLinesFromSyncedSimultaneous:
    def test_simultaneous_lines_produce_background(self):
        synced = [
            SyncedLine(timestamp=10.0, text="Lead vocals here"),
            SyncedLine(timestamp=10.1, text="ooh ahh"),
            SyncedLine(timestamp=20.0, text="Next line"),
        ]
        lines = _lines_from_synced(synced, words_per_line=7)

        primary = [l for l in lines if not l.is_background]
        background = [l for l in lines if l.is_background]

        assert len(primary) == 2
        assert primary[0].text == "Lead vocals here"
        assert primary[1].text == "Next line"
        assert len(background) == 1
        assert background[0].text == "ooh ahh"
        assert background[0].is_background is True

    def test_background_shares_primary_time_range(self):
        synced = [
            SyncedLine(timestamp=10.0, text="Lead"),
            SyncedLine(timestamp=10.0, text="bg"),
            SyncedLine(timestamp=20.0, text="Next"),
        ]
        lines = _lines_from_synced(synced, words_per_line=7)
        background = [l for l in lines if l.is_background]
        assert len(background) == 1
        assert background[0].start == 10.0
        assert abs(background[0].end - 20.0) < 0.01
