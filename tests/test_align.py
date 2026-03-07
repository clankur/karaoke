"""Tests for the alignment stage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from karaoke.align import _group_words_into_lines, align
from karaoke.models import TimedWord


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


class TestAlign:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Vocals file not found"):
            align(tmp_path / "missing.wav")

    @patch("karaoke.align.stable_whisper")
    def test_successful_alignment(self, mock_stable_whisper, tmp_path):
        vocals = tmp_path / "vocals.wav"
        vocals.touch()

        # Mock whisper model and result
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
    def test_uses_align_when_lyrics_provided(self, mock_stable_whisper, tmp_path):
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

        result = align(vocals, lyrics="hello", model_size="tiny")

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

        result = align(vocals, lyrics="some lyrics")
        mock_model.transcribe.assert_called_once()
        assert result.lines[0].text == "fallback"
