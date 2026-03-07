"""Tests for the separation stage."""

from pathlib import Path
from unittest.mock import patch

import pytest

from karaoke.separate import separate


class TestSeparate:
    def test_missing_audio_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            separate(tmp_path / "missing.wav", tmp_path / "output")

    @patch("karaoke.separate.subprocess.run")
    def test_demucs_failure_raises(self, mock_run, tmp_path):
        audio = tmp_path / "song.wav"
        audio.touch()

        mock_run.return_value = type(
            "Result", (), {"returncode": 1, "stderr": "demucs error"}
        )()

        with pytest.raises(RuntimeError, match="demucs failed"):
            separate(audio, tmp_path / "output")

    @patch("karaoke.separate.subprocess.run")
    def test_successful_separation(self, mock_run, tmp_path):
        audio = tmp_path / "song.wav"
        audio.touch()
        output_dir = tmp_path / "output"

        def fake_run(cmd, **kwargs):
            stems = output_dir / "htdemucs" / "song"
            stems.mkdir(parents=True)
            (stems / "vocals.wav").touch()
            (stems / "no_vocals.wav").touch()
            return type("Result", (), {"returncode": 0, "stderr": ""})()

        mock_run.side_effect = fake_run

        result = separate(audio, output_dir)
        assert result.vocals_path.exists()
        assert result.instrumental_path.exists()

    @patch("karaoke.separate.subprocess.run")
    def test_missing_output_stems_raises(self, mock_run, tmp_path):
        audio = tmp_path / "song.wav"
        audio.touch()

        mock_run.return_value = type(
            "Result", (), {"returncode": 0, "stderr": ""}
        )()

        with pytest.raises(RuntimeError, match="did not produce expected vocals"):
            separate(audio, tmp_path / "output")
