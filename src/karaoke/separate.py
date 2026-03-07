"""Separation stage: split audio into vocals and instrumental using demucs."""

import logging
import subprocess
import sys
from pathlib import Path

from karaoke.models import SeparationResult

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "htdemucs"


def separate(
    audio_path: Path,
    output_dir: Path,
    model: str = DEFAULT_MODEL,
) -> SeparationResult:
    """Separate audio into vocals and instrumental tracks.

    Args:
        audio_path: Path to the input audio file (WAV).
        output_dir: Directory to write separated stems.
        model: Demucs model name.

    Returns:
        SeparationResult with paths to vocals and instrumental files.

    Raises:
        RuntimeError: If demucs fails.
        FileNotFoundError: If the input audio file doesn't exist.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "demucs",
        "--two-stems",
        "vocals",
        "-n",
        model,
        "-o",
        str(output_dir),
        str(audio_path),
    ]

    logger.info("Running demucs separation with model '%s'", model)
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"demucs failed (exit code {result.returncode}):\n{result.stderr}"
        )

    stem_name = audio_path.stem
    stems_dir = output_dir / model / stem_name

    vocals_path = stems_dir / "vocals.wav"
    instrumental_path = stems_dir / "no_vocals.wav"

    if not vocals_path.exists():
        raise RuntimeError(f"demucs did not produce expected vocals file: {vocals_path}")
    if not instrumental_path.exists():
        raise RuntimeError(
            f"demucs did not produce expected instrumental file: {instrumental_path}"
        )

    logger.info("Separation complete: %s", stems_dir)
    return SeparationResult(
        vocals_path=vocals_path,
        instrumental_path=instrumental_path,
    )
