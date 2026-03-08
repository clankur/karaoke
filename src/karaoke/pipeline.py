"""Pipeline orchestrator: download -> separate -> align -> render."""

import logging
import tempfile
from pathlib import Path

from karaoke.align import align
from karaoke.download import download
from karaoke.lyrics import fetch_lyrics
from karaoke.models import LyricsResult, RenderResult
from karaoke.render import render
from karaoke.separate import separate

logger = logging.getLogger(__name__)


def generate_karaoke(
    url: str,
    output_path: Path,
    work_dir: Path | None = None,
    whisper_model: str = "base",
    demucs_model: str = "htdemucs",
    words_per_line: int = 7,
    keep_vocals: bool = True,
    vocals_volume: float = 0.3,
    use_synced_lyrics: bool = True,
) -> RenderResult:
    """Run the full karaoke generation pipeline.

    Args:
        url: YouTube video URL.
        output_path: Where to write the final karaoke video.
        work_dir: Directory for intermediate files. Uses a temp dir if None.
        whisper_model: Whisper model size for transcription.
        demucs_model: Demucs model name for source separation.
        words_per_line: Max words per karaoke subtitle line.
        keep_vocals: If True, mix vocals into the output at reduced volume
            so you can verify lyric sync.
        vocals_volume: Volume level for mixed-in vocals (0.0-1.0).
        use_synced_lyrics: If False, ignore synced LRC timestamps and use
            plain lyrics instead. Useful when LRC timestamps are inaccurate.

    Returns:
        RenderResult with the output file path.
    """
    if work_dir is not None:
        return _run_pipeline(
            url, output_path, work_dir, whisper_model, demucs_model,
            words_per_line, keep_vocals, vocals_volume, use_synced_lyrics,
        )

    with tempfile.TemporaryDirectory(prefix="karaoke_") as tmp:
        return _run_pipeline(
            url, output_path, Path(tmp), whisper_model, demucs_model,
            words_per_line, keep_vocals, vocals_volume, use_synced_lyrics,
        )


def _should_skip_separation(keep_vocals: bool, vocals_volume: float) -> bool:
    """Return True when source separation is unnecessary.

    When vocals are kept at full volume the render stage would reproduce
    the original audio, so the expensive demucs separation can be skipped.
    """
    return keep_vocals and vocals_volume >= 1.0


def _run_pipeline(
    url: str,
    output_path: Path,
    work_dir: Path,
    whisper_model: str,
    demucs_model: str,
    words_per_line: int,
    keep_vocals: bool,
    vocals_volume: float,
    use_synced_lyrics: bool,
) -> RenderResult:
    """Execute each pipeline stage sequentially."""
    logger.info("Stage 1/5: Downloading from %s", url)
    dl = download(url, work_dir / "download")

    logger.info("Stage 2/5: Looking up lyrics for '%s'", dl.title)
    lyrics = fetch_lyrics(dl.title)

    if lyrics and not use_synced_lyrics and lyrics.has_synced_timestamps:
        logger.info("Ignoring synced LRC timestamps (--no-synced-lyrics)")
        lyrics = LyricsResult(plain_text=lyrics.plain_text)

    if _should_skip_separation(keep_vocals, vocals_volume):
        logger.info("Stage 3/5: Skipping separation (vocals_volume=%.1f, using original audio)", vocals_volume)
        audio_for_alignment = dl.audio_path
        instrumental_for_render = dl.audio_path
        vocals_for_render = None
    else:
        logger.info("Stage 3/5: Separating vocals and instrumental")
        sep = separate(dl.audio_path, work_dir / "separated", model=demucs_model)
        audio_for_alignment = sep.vocals_path
        instrumental_for_render = sep.instrumental_path
        vocals_for_render = sep.vocals_path if keep_vocals else None

    logger.info("Stage 4/5: Aligning lyrics with timestamps")
    alignment = align(
        audio_for_alignment,
        lyrics=lyrics,
        model_size=whisper_model,
        words_per_line=words_per_line,
    )

    logger.info("Stage 5/5: Rendering karaoke video")
    result = render(
        dl.video_path,
        instrumental_for_render,
        alignment,
        output_path,
        vocals_path=vocals_for_render,
        vocals_volume=vocals_volume,
    )

    logger.info("Done! Karaoke video saved to %s", result.output_path)
    return result
