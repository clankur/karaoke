"""Download stage: fetch audio and video from YouTube using yt-dlp."""

import logging
from pathlib import Path

import yt_dlp

from karaoke.models import DownloadResult

logger = logging.getLogger(__name__)


def download(url: str, output_dir: Path) -> DownloadResult:
    """Download audio and video from a YouTube URL.

    Args:
        url: YouTube video URL.
        output_dir: Directory to save downloaded files.

    Returns:
        DownloadResult with paths to the downloaded video and audio files.

    Raises:
        RuntimeError: If yt-dlp fails to download.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract metadata first
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            raise RuntimeError(f"yt-dlp failed to extract info from {url}: {e}") from e

    video_id = info["id"]
    title = info.get("title", video_id)

    video_path = output_dir / f"{video_id}.mp4"
    audio_path = output_dir / f"{video_id}.wav"

    # Reuse existing files if both are present from a previous run
    if video_path.exists() and audio_path.exists():
        logger.info("Reusing cached download for '%s' (%s)", title, video_id)
        return DownloadResult(
            video_path=video_path,
            audio_path=audio_path,
            title=title,
            video_id=video_id,
        )

    if video_path.exists() or audio_path.exists():
        logger.info("Partial download found for '%s'; re-downloading both files", title)

    # Download video
    video_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(video_path),
        "merge_output_format": "mp4",
        "quiet": True,
    }
    _run_ytdlp(url, video_opts, "video")

    # Download audio as WAV
    audio_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / f"{video_id}.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
        "quiet": True,
    }
    _run_ytdlp(url, audio_opts, "audio")

    if not video_path.exists():
        raise RuntimeError(f"yt-dlp did not produce expected video file: {video_path}")
    if not audio_path.exists():
        raise RuntimeError(f"yt-dlp did not produce expected audio file: {audio_path}")

    logger.info("Downloaded '%s' (%s)", title, video_id)
    return DownloadResult(
        video_path=video_path,
        audio_path=audio_path,
        title=title,
        video_id=video_id,
    )


def _run_ytdlp(url: str, opts: dict, label: str) -> None:
    """Run yt-dlp with the given options, raising on failure."""
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            raise RuntimeError(f"yt-dlp failed to download {label} from {url}: {e}") from e
