"""Alignment stage: align lyrics to vocals with word-level timestamps."""

import logging
from pathlib import Path

import stable_whisper

from karaoke.models import AlignmentResult, LyricsResult, SyncedLine, TimedLine, TimedWord

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "base"
WORDS_PER_LINE = 7
SIMULTANEOUS_THRESHOLD = 0.5  # seconds — lines closer than this are simultaneous


def align(
    vocals_path: Path,
    lyrics: LyricsResult | None = None,
    model_size: str = DEFAULT_MODEL_SIZE,
    words_per_line: int = WORDS_PER_LINE,
) -> AlignmentResult:
    """Align lyrics to vocals with word-level timestamps.

    When synced lyrics with LRC timestamps are available, uses whisper
    alignment for word-level timing and LRC timestamps for line grouping.
    Falls back to character-proportional word timing if whisper fails.

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

    logger.info("Loading whisper model '%s'", model_size)
    model = stable_whisper.load_model(model_size)

    if lyrics and lyrics.has_synced_timestamps:
        # Use whisper for word-level timing, LRC timestamps for line grouping
        logger.info("Aligning synced lyrics to vocals for word-level timing")
        try:
            result = model.align(str(vocals_path), lyrics.plain_text)
            all_words = _extract_words(result)
            lines = _group_words_by_synced_lines(
                all_words, lyrics.synced_lines, words_per_line
            )
            logger.info("Aligned %d words into %d lines using LRC timestamps", len(all_words), len(lines))
            return AlignmentResult(lines=lines)
        except Exception as e:
            logger.warning(
                "Whisper alignment failed, using LRC timestamps with estimated word timing: %s", e
            )
            lines = _lines_from_synced(lyrics.synced_lines, words_per_line)
            logger.info("Created %d lines from LRC timestamps (estimated word timing)", len(lines))
            return AlignmentResult(lines=lines)

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

    all_words = _extract_words(result)
    lines = _group_words_into_lines(all_words, words_per_line)
    logger.info("Aligned %d words into %d lines", len(all_words), len(lines))
    return AlignmentResult(lines=lines)


def _extract_words(result) -> list[TimedWord]:
    """Extract TimedWord list from a stable-whisper result."""
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
    return all_words


def _detect_simultaneous_lines(
    synced_lines: list[SyncedLine],
    threshold: float = SIMULTANEOUS_THRESHOLD,
) -> list[tuple[SyncedLine, bool]]:
    """Tag each SyncedLine as primary (False) or background (True).

    When consecutive lines have timestamps within threshold, the first
    is primary and subsequent ones are background.
    """
    if not synced_lines:
        return []

    result: list[tuple[SyncedLine, bool]] = [(synced_lines[0], False)]
    for i in range(1, len(synced_lines)):
        gap = synced_lines[i].timestamp - synced_lines[i - 1].timestamp
        if gap < threshold:
            # If previous was also background, this is still background
            # (part of the same simultaneous group)
            result.append((synced_lines[i], True))
        else:
            result.append((synced_lines[i], False))

    return result


def _group_words_by_synced_lines(
    words: list[TimedWord],
    synced_lines: list[SyncedLine],
    words_per_line: int,
) -> list[TimedLine]:
    """Group whisper-aligned words into lines using LRC timestamps as boundaries.

    Each word is assigned to the LRC line whose timestamp range contains it.
    This combines whisper's accurate word-level timing with LRC's accurate
    line-level timing. Background lines (simultaneous vocals) get estimated
    timing and are marked with is_background=True.
    """
    if not words or not synced_lines:
        return []

    tagged = _detect_simultaneous_lines(synced_lines)

    # Separate primary and background lines, tracking which primary each background belongs to
    primary_lines: list[SyncedLine] = []
    # Map from primary index to list of background SyncedLines
    background_map: dict[int, list[SyncedLine]] = {}
    for sline, is_bg in tagged:
        if is_bg:
            if primary_lines:
                primary_idx = len(primary_lines) - 1
                background_map.setdefault(primary_idx, []).append(sline)
        else:
            primary_lines.append(sline)

    if not primary_lines:
        return []

    # Build time boundaries from primary lines only
    boundaries: list[tuple[float, float, str]] = []
    for i, sline in enumerate(primary_lines):
        line_start = sline.timestamp
        if i + 1 < len(primary_lines):
            line_end = primary_lines[i + 1].timestamp
        else:
            line_end = float("inf")
        boundaries.append((line_start, line_end, sline.text))

    # Assign each word to the primary LRC line it falls within
    line_words: list[list[TimedWord]] = [[] for _ in boundaries]
    boundary_idx = 0

    for word in words:
        word_mid = (word.start + word.end) / 2.0
        # Advance to the correct boundary
        while (
            boundary_idx < len(boundaries) - 1
            and word_mid >= boundaries[boundary_idx][1]
        ):
            boundary_idx += 1
        line_words[boundary_idx].append(word)

    # Convert to TimedLines, inserting background lines after their primary
    result: list[TimedLine] = []
    for idx, group in enumerate(line_words):
        if not group:
            # Still need to check for background lines even if primary has no words
            bg_lines = background_map.get(idx, [])
            if bg_lines:
                start = boundaries[idx][0]
                end = boundaries[idx][1] if boundaries[idx][1] != float("inf") else start + 3.0
                for bg_sline in bg_lines:
                    bg_words = bg_sline.text.split()
                    if bg_words:
                        timed = _distribute_word_timing(bg_words, start, end)
                        result.append(TimedLine(words=timed, is_background=True))
            continue

        # Add primary line chunks
        for i in range(0, len(group), words_per_line):
            chunk = group[i : i + words_per_line]
            if chunk:
                result.append(TimedLine(words=chunk))

        # Add background lines for this primary
        bg_lines = background_map.get(idx, [])
        if bg_lines:
            primary_start = group[0].start
            primary_end = group[-1].end
            for bg_sline in bg_lines:
                bg_words = bg_sline.text.split()
                if bg_words:
                    timed = _distribute_word_timing(bg_words, primary_start, primary_end)
                    result.append(TimedLine(words=timed, is_background=True))

    return result


def _lines_from_synced(
    synced_lines: list[SyncedLine], words_per_line: int
) -> list[TimedLine]:
    """Convert synced lyrics lines into TimedLines with estimated word timing.

    Used as a fallback when whisper alignment fails but we still have
    LRC timestamps. Word timing is distributed proportionally by character count.
    Background lines (simultaneous vocals) share the primary line's time range.
    """
    tagged = _detect_simultaneous_lines(synced_lines)
    result: list[TimedLine] = []

    # Build list of primary lines with their backgrounds
    primary_entries: list[tuple[SyncedLine, list[SyncedLine]]] = []
    for sline, is_bg in tagged:
        if is_bg:
            if primary_entries:
                primary_entries[-1][1].append(sline)
        else:
            primary_entries.append((sline, []))

    for entry_idx, (sline, bg_lines) in enumerate(primary_entries):
        # Determine end time from next primary line
        if entry_idx + 1 < len(primary_entries):
            line_end = primary_entries[entry_idx + 1][0].timestamp
        else:
            line_end = sline.timestamp + 3.0

        words_text = sline.text.split()
        if not words_text:
            continue

        for chunk_start in range(0, len(words_text), words_per_line):
            chunk = words_text[chunk_start : chunk_start + words_per_line]
            chunk_fraction_start = chunk_start / len(words_text)
            chunk_fraction_end = min((chunk_start + len(chunk)) / len(words_text), 1.0)
            chunk_time_start = sline.timestamp + (line_end - sline.timestamp) * chunk_fraction_start
            chunk_time_end = sline.timestamp + (line_end - sline.timestamp) * chunk_fraction_end

            timed_words = _distribute_word_timing(chunk, chunk_time_start, chunk_time_end)
            result.append(TimedLine(words=timed_words))

        # Add background lines
        for bg_sline in bg_lines:
            bg_words = bg_sline.text.split()
            if bg_words:
                timed_words = _distribute_word_timing(bg_words, sline.timestamp, line_end)
                result.append(TimedLine(words=timed_words, is_background=True))

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
