"""Tests for the alignment stage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from karaoke.align import (
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


class TestLinesFromSyncedCjk:
    def test_japanese_text_splits_per_character(self):
        """CJK text should produce character-level tokens."""
        synced = [
            SyncedLine(timestamp=0.0, text="こんにちは"),
            SyncedLine(timestamp=5.0, text="世界"),
        ]
        lines = _lines_from_synced(synced, words_per_line=10)
        assert len(lines) == 2
        # Each character should be its own token
        assert len(lines[0].words) == 5
        assert lines[0].words[0].text == "こ"
        assert lines[0].words[4].text == "は"
        assert len(lines[1].words) == 2
        assert lines[1].words[0].text == "世"

    def test_mixed_text_splits_correctly(self):
        synced = [SyncedLine(timestamp=0.0, text="Hello こんにちは World")]
        lines = _lines_from_synced(synced, words_per_line=20)
        assert len(lines) == 1
        words = [w.text for w in lines[0].words]
        assert words == ["Hello", "こ", "ん", "に", "ち", "は", "World"]


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

    @patch("karaoke.align.stable_whisper")
    def test_language_passed_to_align(self, mock_stable_whisper, tmp_path):
        """Language parameter is forwarded to model.align()."""
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        mock_model = MagicMock()
        mock_stable_whisper.load_model.return_value = mock_model

        mock_word = MagicMock()
        mock_word.word = "こんにちは"
        mock_word.start = 0.0
        mock_word.end = 1.0
        mock_segment = MagicMock()
        mock_segment.words = [mock_word]
        mock_result = MagicMock()
        mock_result.segments = [mock_segment]
        mock_model.align.return_value = mock_result

        lyrics = LyricsResult(plain_text="こんにちは")
        align(vocals, lyrics=lyrics, model_size="tiny", language="ja")

        mock_model.align.assert_called_once()
        assert mock_model.align.call_args.kwargs.get("language") == "ja"

    @patch("karaoke.align.stable_whisper")
    def test_language_passed_to_transcribe(self, mock_stable_whisper, tmp_path):
        """Language parameter is forwarded to model.transcribe()."""
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        mock_model = MagicMock()
        mock_stable_whisper.load_model.return_value = mock_model

        mock_word = MagicMock()
        mock_word.word = "test"
        mock_word.start = 0.0
        mock_word.end = 1.0
        mock_segment = MagicMock()
        mock_segment.words = [mock_word]
        mock_result = MagicMock()
        mock_result.segments = [mock_segment]
        mock_model.transcribe.return_value = mock_result

        align(vocals, language="hi")

        mock_model.transcribe.assert_called_once()
        assert mock_model.transcribe.call_args.kwargs.get("language") == "hi"

    @patch("karaoke.align.stable_whisper")
    def test_language_none_by_default(self, mock_stable_whisper, tmp_path):
        """When no language is specified, None is passed (auto-detect)."""
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        mock_model = MagicMock()
        mock_stable_whisper.load_model.return_value = mock_model

        mock_word = MagicMock()
        mock_word.word = "test"
        mock_word.start = 0.0
        mock_word.end = 1.0
        mock_segment = MagicMock()
        mock_segment.words = [mock_word]
        mock_result = MagicMock()
        mock_result.segments = [mock_segment]
        mock_model.transcribe.return_value = mock_result

        align(vocals)

        assert mock_model.transcribe.call_args.kwargs.get("language") is None
