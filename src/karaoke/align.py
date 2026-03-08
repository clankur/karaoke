"""Alignment stage: align lyrics to vocals with word-level timestamps."""

import logging
from pathlib import Path

import stable_whisper

from karaoke.models import AlignmentResult, LyricsResult, SyncedLine, TimedLine, TimedWord

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "base"
WORDS_PER_LINE = 7


def align(
    vocals_path: Path,
    lyrics: LyricsResult | None = None,
    model_size: str = DEFAULT_MODEL_SIZE,
    words_per_line: int = WORDS_PER_LINE,
) -> AlignmentResult:
    """Align lyrics to vocals with word-level timestamps.

    Uses the best available timing source:
    1. Synced lyrics with LRC timestamps (most accurate, no model needed)
    2. Model alignment with plain lyrics text
    3. Model transcription (no lyrics available)

    Args:
        vocals_path: Path to the isolated vocals audio file.
        lyrics: LyricsResult with plain text and optional synced timestamps.
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

    # Best case: synced lyrics with timestamps from the lyrics provider
    if lyrics and lyrics.has_synced_timestamps:
        logger.info("Using synced lyrics timestamps (%d lines)", len(lyrics.synced_lines))
        lines = _lines_from_synced(lyrics.synced_lines, words_per_line)
        logger.info("Created %d display lines from synced lyrics", len(lines))
        return AlignmentResult(lines=lines)

    # Fall back to model-based alignment
    logger.info("Loading whisper model '%s'", model_size)
    model = stable_whisper.load_model(model_size)

    if lyrics and lyrics.plain_text:
        logger.info("Aligning fetched lyrics to vocals")
        try:
            result = model.align(str(vocals_path), lyrics.plain_text)
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


def _lines_from_synced(
    synced_lines: list[SyncedLine], words_per_line: int
) -> list[TimedLine]:
    """Convert synced lyrics lines into TimedLines with estimated word timing.

    Each line's duration is estimated from the gap to the next line's timestamp.
    Word timing within a line is distributed proportionally by character count.
    """
    result: list[TimedLine] = []

    for i, sline in enumerate(synced_lines):
        # Estimate line end time from the next line's start
        if i + 1 < len(synced_lines):
            line_end = synced_lines[i + 1].timestamp
        else:
            # Last line: estimate ~3 seconds duration
            line_end = sline.timestamp + 3.0

        words_text = sline.text.split()
        if not words_text:
            continue

        # Split into sub-lines if needed
        for chunk_start in range(0, len(words_text), words_per_line):
            chunk = words_text[chunk_start : chunk_start + words_per_line]
            # Calculate time range for this chunk proportionally
            chunk_fraction_start = chunk_start / len(words_text)
            chunk_fraction_end = min((chunk_start + len(chunk)) / len(words_text), 1.0)
            chunk_time_start = sline.timestamp + (line_end - sline.timestamp) * chunk_fraction_start
            chunk_time_end = sline.timestamp + (line_end - sline.timestamp) * chunk_fraction_end

            timed_words = _distribute_word_timing(chunk, chunk_time_start, chunk_time_end)
            result.append(TimedLine(words=timed_words))

    return result


def _distribute_word_timing(
    words: list[str], start: float, end: float
) -> list[TimedWord]:
    """Distribute timing across words proportionally by character length."""
    total_chars = sum(len(w) for w in words)
    if total_chars == 0:
        return []

    duration = end - start
    timed: list[TimedWord] = []
    cursor = start

    for word in words:
        word_duration = duration * (len(word) / total_chars)
        timed.append(TimedWord(text=word, start=cursor, end=cursor + word_duration))
        cursor += word_duration

    return timed


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
