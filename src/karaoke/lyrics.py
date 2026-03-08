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
# Matches parenthetical/bracketed noise in YouTube titles
_TITLE_PAREN_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
# Matches common YouTube video suffixes
_TITLE_SUFFIX_RE = re.compile(
    r"\s*[-|]\s*("
    r"official\s*(music\s*)?video|"
    r"official\s*audio|"
    r"lyric\s*video|"
    r"lyrics?|"
    r"audio|"
    r"music\s*video|"
    r"full\s*video|"
    r"hd|hq|4k"
    r")\s*$",
    re.IGNORECASE,
)
# Whitespace collapsing
_MULTI_SPACE_RE = re.compile(r"\s{2,}")


def _clean_title(title: str) -> list[str]:
    """Generate search queries from a YouTube title, most specific to least.

    YouTube titles often contain noise like "(Official Video)", pipe-separated
    metadata, and actor/album names. This function produces multiple cleaned
    variants to try against lyrics providers.

    Returns:
        List of unique search query strings, ordered from most to least specific.
    """
    queries: list[str] = []

    # Variant 1: strip parenthetical tags and common suffixes, keep pipe content
    cleaned = _TITLE_PAREN_RE.sub("", title)
    cleaned = _TITLE_SUFFIX_RE.sub("", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned).strip()
    if cleaned:
        queries.append(cleaned)

    # Variant 2: first pipe/dash segment only (usually the song name)
    if "|" in title or " - " in title:
        # Split on pipe first, then dash
        first_segment = re.split(r"\s*[|]\s*", title)[0]
        first_segment = re.split(r"\s*-\s*", first_segment)[0]
        first_segment = _TITLE_PAREN_RE.sub("", first_segment)
        first_segment = _MULTI_SPACE_RE.sub(" ", first_segment).strip()
        if first_segment and first_segment not in queries:
            queries.append(first_segment)

    # If nothing was cleaned (simple title), use as-is
    if not queries:
        queries.append(title.strip())

    return queries


def fetch_lyrics(title: str, artist: str | None = None) -> LyricsResult | None:
    """Fetch lyrics for a song by title, preferring synced (LRC) format.

    Generates multiple search queries from the title (cleaning YouTube noise)
    and tries each one until lyrics are found.

    Args:
        title: Song title, e.g. "Bohemian Rhapsody" or a full YouTube title.
        artist: Optional artist name for more specific search.

    Returns:
        LyricsResult with plain text and optional synced timestamps, or None if not found.
    """
    queries: list[str] = []

    # If artist is provided, try "title artist" first
    if artist:
        queries.append(f"{title} {artist}")

    # Add cleaned variants of the title
    queries.extend(q for q in _clean_title(title) if q not in queries)

    for query in queries:
        logger.info("Searching for lyrics: '%s'", query)
        result = _search_lyrics(query)
        if not result:
            continue

        # Try to parse as LRC format (has timestamps)
        synced_lines = _parse_lrc(result)
        if synced_lines:
            plain_text = "\n".join(line.text for line in synced_lines)
            logger.info(
                "Found synced lyrics for '%s' (%d lines with timestamps)",
                query,
                len(synced_lines),
            )
            return LyricsResult(plain_text=plain_text, synced_lines=synced_lines)

        # Fall back to treating as plain text
        plain_lines = _strip_to_plain(result)
        if plain_lines:
            plain_text = "\n".join(plain_lines)
            logger.info("Found plain lyrics for '%s' (%d lines)", query, len(plain_lines))
            return LyricsResult(plain_text=plain_text)

    logger.info("No lyrics found for '%s'", title)
    return None


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
