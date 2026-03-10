"""Search stage: find YouTube videos by query using yt-dlp."""

import logging

import yt_dlp

from karaoke.models import VideoSearchResult

logger = logging.getLogger(__name__)

_YTDLP_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "extract_flat": True,
}


def search_videos(query: str, max_results: int = 5) -> list[VideoSearchResult]:
    """Search YouTube for videos matching a query.

    Args:
        query: Search terms.
        max_results: Maximum number of results to return (1-10).

    Returns:
        List of VideoSearchResult with metadata for each match.

    Raises:
        ValueError: If query is empty.
        RuntimeError: If yt-dlp fails to search.
    """
    if not query.strip():
        raise ValueError("Search query must not be empty")

    max_results = max(1, min(max_results, 10))

    with yt_dlp.YoutubeDL(_YTDLP_OPTS) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        except yt_dlp.utils.DownloadError as e:
            raise RuntimeError(f"yt-dlp search failed for '{query}': {e}") from e

    entries = info.get("entries") or []
    results = []
    for entry in entries:
        if entry is None:
            continue
        video_id = entry.get("id", "")
        results.append(
            VideoSearchResult(
                video_id=video_id,
                title=entry.get("title", ""),
                thumbnail_url=entry.get("thumbnail", ""),
                channel=entry.get("channel") or entry.get("uploader", ""),
                duration_seconds=int(entry.get("duration") or 0),
                url=entry.get("webpage_url") or entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
            )
        )

    logger.info("Found %d results for '%s'", len(results), query)
    return results
