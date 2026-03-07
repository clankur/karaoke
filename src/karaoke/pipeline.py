"""Pipeline orchestrator: download -> separate -> align -> render."""

import logging
import tempfile
from pathlib import Path

from karaoke.align import align
from karaoke.download import download
from karaoke.models import RenderResult
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
) -> RenderResult:
    """Run the full karaoke generation pipeline.

    Args:
        url: YouTube video URL.
        output_path: Where to write the final karaoke video.
        work_dir: Directory for intermediate files. Uses a temp dir if None.
        whisper_model: Whisper model size for transcription.
        demucs_model: Demucs model name for source separation.
        words_per_line: Max words per karaoke subtitle line.

    Returns:
        RenderResult with the output file path.
    """
    if work_dir is not None:
        return _run_pipeline(
            url, output_path, work_dir, whisper_model, demucs_model, words_per_line
        )

    with tempfile.TemporaryDirectory(prefix="karaoke_") as tmp:
        return _run_pipeline(
            url, output_path, Path(tmp), whisper_model, demucs_model, words_per_line
        )


def _run_pipeline(
    url: str,
    output_path: Path,
    work_dir: Path,
    whisper_model: str,
    demucs_model: str,
    words_per_line: int,
) -> RenderResult:
    """Execute each pipeline stage sequentially."""
    logger.info("Stage 1/4: Downloading from %s", url)
    dl = download(url, work_dir / "download")

    logger.info("Stage 2/4: Separating vocals and instrumental")
    sep = separate(dl.audio_path, work_dir / "separated", model=demucs_model)

    logger.info("Stage 3/4: Aligning lyrics with timestamps")
    alignment = align(
        sep.vocals_path,
        model_size=whisper_model,
        words_per_line=words_per_line,
    )

    logger.info("Stage 4/4: Rendering karaoke video")
    result = render(dl.video_path, sep.instrumental_path, alignment, output_path)

    logger.info("Done! Karaoke video saved to %s", result.output_path)
    return result
