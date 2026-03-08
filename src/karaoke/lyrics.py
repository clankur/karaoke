"""Lyrics fetcher: look up song lyrics online before falling back to transcription."""

import logging
import re

import syncedlyrics

from karaoke.models import LyricsResult, SyncedLine

logger = logging.getLogger(__name__)

# Matches LRC timestamp tags like [00:12.34] or [01:23.456]
_LRC_TAG_RE = re.compile(r"\[(\d+):(\d+)\.(\d+)\]")
# Matches any bracketed tag (timestamps, metadata like [by:someone])
_BRACKET_TAG_RE = re.compile(r"\[[^\]]*\]")


def fetch_lyrics(title: str) -> LyricsResult | None:
    """Fetch lyrics for a song by title, preferring synced (LRC) format.

    Tries to get synced lyrics with timestamps first, then falls back to
    plain text. Returns a LyricsResult with parsed timestamps when available.

    Args:
        title: Song title (and optionally artist), e.g. "Bohemian Rhapsody Queen".

    Returns:
        LyricsResult with plain text and optional synced timestamps, or None if not found.
    """
    logger.info("Searching for lyrics: '%s'", title)

    # Try synced lyrics first (default mode returns LRC when available)
    result = _search_lyrics(title)
    if not result:
        logger.info("No lyrics found for '%s'", title)
        return None

    # Try to parse as LRC format (has timestamps)
    synced_lines = _parse_lrc(result)
    if synced_lines:
        plain_text = "\n".join(line.text for line in synced_lines)
        logger.info(
            "Found synced lyrics for '%s' (%d lines with timestamps)",
            title,
            len(synced_lines),
        )
        return LyricsResult(plain_text=plain_text, synced_lines=synced_lines)

    # Fall back to treating as plain text
    plain_lines = _strip_to_plain(result)
    if not plain_lines:
        logger.info("Lyrics result was empty after parsing for '%s'", title)
        return None

    plain_text = "\n".join(plain_lines)
    logger.info("Found plain lyrics for '%s' (%d lines)", title, len(plain_lines))
    return LyricsResult(plain_text=plain_text)


def _search_lyrics(title: str) -> str | None:
    """Search for lyrics using syncedlyrics, handling errors."""
    try:
        return syncedlyrics.search(title)
    except Exception as e:
        logger.warning("Lyrics search failed: %s", e)
        return None


def _parse_lrc(text: str) -> list[SyncedLine] | None:
    """Parse LRC-formatted lyrics into SyncedLine objects.

    Returns None if the text doesn't appear to be LRC format.
    """
    lines: list[SyncedLine] = []
    has_timestamps = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        # Try to extract an LRC timestamp
        match = _LRC_TAG_RE.match(stripped)
        if match:
            has_timestamps = True
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            # Handle both 2-digit centiseconds and 3-digit milliseconds
            frac_str = match.group(3)
            if len(frac_str) == 3:
                frac = int(frac_str) / 1000.0
            else:
                frac = int(frac_str) / 100.0
            timestamp = minutes * 60.0 + seconds + frac

            # Strip all bracket tags to get the text
            lyric_text = _BRACKET_TAG_RE.sub("", stripped).strip()
            if lyric_text:
                lines.append(SyncedLine(timestamp=timestamp, text=lyric_text))
        else:
            # Line without timestamp — strip any other bracket tags
            lyric_text = _BRACKET_TAG_RE.sub("", stripped).strip()
            if lyric_text:
                lines.append(SyncedLine(timestamp=0.0, text=lyric_text))

    if not has_timestamps or not lines:
        return None

    return lines


def _strip_to_plain(text: str) -> list[str]:
    """Strip LRC tags and return plain text lines."""
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        # Remove all bracket tags
        stripped = _BRACKET_TAG_RE.sub("", stripped).strip()
        if stripped:
            lines.append(stripped)
    return lines
