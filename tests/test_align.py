"""Tests for the alignment stage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from karaoke.align import _distribute_word_timing, _group_words_into_lines, _lines_from_synced, align
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
        # End should be at the next line's timestamp
        assert abs(lines[0].end - 15.0) < 0.01
        assert lines[1].text == "Goodbye moon"
        assert lines[1].start == 15.0

    def test_last_line_gets_default_duration(self):
        synced = [SyncedLine(timestamp=10.0, text="Only line")]
        lines = _lines_from_synced(synced, words_per_line=7)
        assert len(lines) == 1
        assert lines[0].start == 10.0
        # Last line gets ~3 second duration
        assert abs(lines[0].end - 13.0) < 0.01

    def test_long_line_splits_by_words_per_line(self):
        # 10 words should split into two lines with words_per_line=7
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
        assert abs(result[0].end - 2.0) < 0.01  # 2/7 * 7.0
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

    def test_uses_synced_timestamps_skips_model(self, tmp_path):
        """When synced lyrics with timestamps are available, skip model entirely."""
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        lyrics = LyricsResult(
            plain_text="Hello world\nGoodbye moon",
            synced_lines=[
                SyncedLine(timestamp=10.0, text="Hello world"),
                SyncedLine(timestamp=15.0, text="Goodbye moon"),
            ],
        )

        # No model mock needed — synced path shouldn't load whisper
        with patch("karaoke.align.stable_whisper") as mock_sw:
            result = align(vocals, lyrics=lyrics, model_size="tiny")
            mock_sw.load_model.assert_not_called()

        assert len(result.lines) == 2
        assert result.lines[0].text == "Hello world"
        assert result.lines[0].start == 10.0
        assert result.lines[1].text == "Goodbye moon"
        assert result.lines[1].start == 15.0
