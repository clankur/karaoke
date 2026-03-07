"""Render stage: generate ASS subtitles and burn them into video with ffmpeg."""

import logging
import subprocess
from pathlib import Path

from karaoke.models import AlignmentResult, RenderResult, TimedLine

logger = logging.getLogger(__name__)


def render(
    video_path: Path,
    instrumental_path: Path,
    alignment: AlignmentResult,
    output_path: Path,
) -> RenderResult:
    """Render the final karaoke video.

    Generates ASS subtitles with karaoke timing, then uses ffmpeg to burn them
    onto the video with the instrumental audio track.

    Args:
        video_path: Path to the original video file.
        instrumental_path: Path to the instrumental audio track.
        alignment: Word-level timed lyrics from the alignment stage.
        output_path: Where to write the final karaoke video.

    Returns:
        RenderResult with the output file path.

    Raises:
        FileNotFoundError: If input files don't exist.
        RuntimeError: If ffmpeg fails.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not instrumental_path.exists():
        raise FileNotFoundError(f"Instrumental file not found: {instrumental_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    ass_path = output_path.with_suffix(".ass")
    _generate_ass(alignment, ass_path)

    _burn_subtitles(video_path, instrumental_path, ass_path, output_path)

    # Clean up intermediate ASS file
    ass_path.unlink(missing_ok=True)

    logger.info("Karaoke video rendered: %s", output_path)
    return RenderResult(output_path=output_path)


def _generate_ass(alignment: AlignmentResult, output_path: Path) -> None:
    """Generate an ASS subtitle file with karaoke highlighting tags."""
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1920\n"
        "PlayResY: 1080\n"
        "WrapStyle: 0\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Karaoke,Arial,60,&H00FFFFFF,&H0000FFFF,"
        "&H00000000,&H80000000,1,0,0,0,"
        "100,100,0,0,1,3,1,"
        "2,20,20,50,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events: list[str] = []
    for line in alignment.lines:
        if not line.words:
            continue
        start = _format_ass_time(line.start)
        end = _format_ass_time(line.end)
        text = _build_karaoke_text(line)
        events.append(f"Dialogue: 0,{start},{end},Karaoke,,0,0,0,,{text}")

    output_path.write_text(header + "\n".join(events) + "\n")
    logger.info("Generated ASS subtitle: %s", output_path)


def _build_karaoke_text(line: TimedLine) -> str:
    """Build ASS karaoke text with \\kf tags for progressive highlighting."""
    parts: list[str] = []
    for word in line.words:
        duration_cs = max(1, int((word.end - word.start) * 100))
        parts.append(f"{{\\kf{duration_cs}}}{word.text} ")
    return "".join(parts).rstrip()


def _format_ass_time(seconds: float) -> str:
    """Format seconds as ASS timestamp (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _burn_subtitles(
    video_path: Path,
    audio_path: Path,
    ass_path: Path,
    output_path: Path,
) -> None:
    """Use ffmpeg to burn ASS subtitles onto video with instrumental audio."""
    # Escape special characters in the ASS path for ffmpeg filter
    escaped_ass = str(ass_path).replace("\\", "\\\\").replace(":", "\\:")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-vf", f"ass={escaped_ass}",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path),
    ]

    logger.info("Running ffmpeg to render karaoke video")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit code {result.returncode}):\n{result.stderr}"
        )
