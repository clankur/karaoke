"""Alignment stage: align lyrics to vocals with word-level timestamps."""

import logging
from pathlib import Path

import stable_whisper

from karaoke.models import AlignmentResult, TimedLine, TimedWord

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "base"
WORDS_PER_LINE = 7


def align(
    vocals_path: Path,
    lyrics: str | None = None,
    model_size: str = DEFAULT_MODEL_SIZE,
    words_per_line: int = WORDS_PER_LINE,
) -> AlignmentResult:
    """Align lyrics to vocals with word-level timestamps.

    If lyrics are provided, uses stable_whisper.align() to force-align them
    to the audio — this produces more accurate timestamps than transcription.
    Falls back to transcription if no lyrics are given.

    Args:
        vocals_path: Path to the isolated vocals audio file.
        lyrics: Pre-fetched plain-text lyrics. If None, transcribes instead.
        model_size: Whisper model size (tiny, base, small, medium, large).
        words_per_line: Max words per karaoke line.

    Returns:
        AlignmentResult with timed lyrics lines.

    Raises:
        FileNotFoundError: If the vocals file doesn't exist.
        RuntimeError: If transcription/alignment fails.
    """
    if not vocals_path.exists():
        raise FileNotFoundError(f"Vocals file not found: {vocals_path}")

    logger.info("Loading whisper model '%s'", model_size)
    model = stable_whisper.load_model(model_size)

    if lyrics:
        logger.info("Aligning fetched lyrics to vocals")
        try:
            result = model.align(str(vocals_path), lyrics)
        except Exception as e:
            logger.warning("Lyrics alignment failed, falling back to transcription: %s", e)
            result = _transcribe(model, vocals_path)
    else:
        logger.info("No lyrics provided, transcribing vocals")
        result = _transcribe(model, vocals_path)

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


def _transcribe(model, vocals_path: Path):
    """Run whisper transcription as fallback."""
    try:
        return model.transcribe(str(vocals_path))
    except Exception as e:
        raise RuntimeError(f"stable-ts transcription failed: {e}") from e


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
