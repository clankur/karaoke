"""Alignment stage: transcribe vocals and produce word-level timestamps."""

import logging
from pathlib import Path

import stable_whisper

from karaoke.models import AlignmentResult, TimedLine, TimedWord

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "base"
WORDS_PER_LINE = 7


def align(
    vocals_path: Path,
    model_size: str = DEFAULT_MODEL_SIZE,
    words_per_line: int = WORDS_PER_LINE,
) -> AlignmentResult:
    """Transcribe vocals and produce word-level timestamps.

    Args:
        vocals_path: Path to the isolated vocals audio file.
        model_size: Whisper model size (tiny, base, small, medium, large).
        words_per_line: Max words per karaoke line.

    Returns:
        AlignmentResult with timed lyrics lines.

    Raises:
        FileNotFoundError: If the vocals file doesn't exist.
        RuntimeError: If transcription fails.
    """
    if not vocals_path.exists():
        raise FileNotFoundError(f"Vocals file not found: {vocals_path}")

    logger.info("Loading whisper model '%s'", model_size)
    model = stable_whisper.load_model(model_size)

    logger.info("Transcribing vocals: %s", vocals_path)
    try:
        result = model.transcribe(str(vocals_path))
    except Exception as e:
        raise RuntimeError(f"stable-ts transcription failed: {e}") from e

    all_words: list[TimedWord] = []
    for segment in result.segments:
        for word in segment.words:
            all_words.append(
                TimedWord(
                    text=word.word.strip(),
                    start=word.start,
                    end=word.end,
                )
            )

    lines = _group_words_into_lines(all_words, words_per_line)
    logger.info("Aligned %d words into %d lines", len(all_words), len(lines))
    return AlignmentResult(lines=lines)


def _group_words_into_lines(
    words: list[TimedWord], words_per_line: int
) -> list[TimedLine]:
    """Group words into display lines for karaoke rendering."""
    lines: list[TimedLine] = []
    for i in range(0, len(words), words_per_line):
        chunk = words[i : i + words_per_line]
        if chunk:
            lines.append(TimedLine(words=chunk))
    return lines
