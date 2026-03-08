"""Lyrics fetcher: look up song lyrics online before falling back to transcription."""

import logging

import syncedlyrics

logger = logging.getLogger(__name__)


def fetch_lyrics(title: str) -> str | None:
    """Fetch plain-text lyrics for a song by title.

    Args:
        title: Song title (and optionally artist), e.g. "Bohemian Rhapsody Queen".

    Returns:
        Plain-text lyrics as a string, or None if not found.
    """
    logger.info("Searching for lyrics: '%s'", title)
    try:
        result = syncedlyrics.search(title, plain_only=True)
    except Exception as e:
        logger.warning("Lyrics search failed: %s", e)
        return None

    if not result:
        logger.info("No lyrics found for '%s'", title)
        return None

    # syncedlyrics may return LRC-formatted text even with plain_only;
    # strip any timestamp prefixes like [00:12.34]
    lines: list[str] = []
    for line in result.splitlines():
        stripped = line.strip()
        # Remove LRC timestamp tags
        while stripped.startswith("[") and "]" in stripped:
            stripped = stripped[stripped.index("]") + 1 :].strip()
        if stripped:
            lines.append(stripped)

    if not lines:
        logger.info("Lyrics result was empty after parsing for '%s'", title)
        return None

    lyrics = "\n".join(lines)
    logger.info("Found lyrics for '%s' (%d lines)", title, len(lines))
    return lyrics
