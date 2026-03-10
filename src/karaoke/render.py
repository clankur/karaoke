"""Render stage: generate ASS subtitles and burn them into video with ffmpeg."""

import logging
import subprocess
from pathlib import Path

from karaoke.models import AlignmentResult, RenderResult, TimedLine
from karaoke.text_utils import is_cjk_char

_CJK_LANGUAGES = {"ja", "zh", "ko"}
_NON_LATIN_LANGUAGES = {
    "hi", "th", "ar", "he", "bn", "ta", "te", "ml", "kn", "gu", "pa",
    "mr", "ne", "si", "my", "km", "lo", "ka", "am", "ti", "ur",
}
_DEFAULT_FONT = "Arial"
_CJK_FONT = "Noto Sans CJK"
_UNICODE_FONT = "Noto Sans"


def _select_font(language: str | None) -> str:
    """Select an appropriate font based on language."""
    if not language:
        return _DEFAULT_FONT
    lang = language[:2].lower()
    if lang in _CJK_LANGUAGES:
        return _CJK_FONT
    if lang in _NON_LATIN_LANGUAGES:
        return _UNICODE_FONT
    return _DEFAULT_FONT

logger = logging.getLogger(__name__)


def render(
    video_path: Path,
    instrumental_path: Path,
    alignment: AlignmentResult,
    output_path: Path,
    vocals_path: Path | None = None,
    vocals_volume: float = 0.3,
    language: str | None = None,
) -> RenderResult:
    """Render the final karaoke video.

    Generates ASS subtitles with karaoke timing, then uses ffmpeg to burn them
    onto the video with the audio track. When vocals_path is provided, the
    vocals are mixed in at reduced volume so you can verify lyric sync.

    Args:
        video_path: Path to the original video file.
        instrumental_path: Path to the instrumental audio track.
        alignment: Word-level timed lyrics from the alignment stage.
        output_path: Where to write the final karaoke video.
        vocals_path: Optional path to vocals track to mix in for sync debugging.
        vocals_volume: Volume level for vocals (0.0-1.0). Default 0.3.

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
    if vocals_path is not None and not vocals_path.exists():
        raise FileNotFoundError(f"Vocals file not found: {vocals_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    ass_path = output_path.with_suffix(".ass")
    font = _select_font(language)
    _generate_ass(alignment, ass_path, font_name=font)

    _burn_subtitles(
        video_path, instrumental_path, ass_path, output_path,
        vocals_path=vocals_path, vocals_volume=vocals_volume,
    )

    # Clean up intermediate ASS file
    ass_path.unlink(missing_ok=True)

    logger.info("Karaoke video rendered: %s", output_path)
    return RenderResult(output_path=output_path)


def _generate_ass(
    alignment: AlignmentResult, output_path: Path, font_name: str = "Arial"
) -> None:
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
        f"Style: Karaoke,{font_name},60,&H00FFFFFF,&H0000FFFF,"
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


def _is_cjk_text(text: str) -> bool:
    """Check if text consists entirely of CJK characters."""
    return bool(text) and all(is_cjk_char(c) for c in text)


def _cap_last_word_duration(line: TimedLine) -> float:
    """Return a capped duration for the last word to avoid highlight drag during silence.

    If the last word's duration is disproportionately long compared to the other
    words, caps it at 2x the median duration of the other words.
    """
    if len(line.words) < 2:
        return line.words[-1].end - line.words[-1].start

    last_dur = line.words[-1].end - line.words[-1].start
    other_durations = sorted(w.end - w.start for w in line.words[:-1])
    median_dur = other_durations[len(other_durations) // 2]

    cap = max(median_dur * 2.0, 0.5)
    return min(last_dur, cap)


def _build_karaoke_text(line: TimedLine) -> str:
    """Build ASS karaoke text with \\kf tags for progressive highlighting.

    Inserts spaces between words for Latin text, but omits spaces between
    adjacent CJK characters for natural rendering. Accounts for silence gaps
    between words by assigning gap time to separators, keeping the highlight
    timeline synchronized with the audio.
    """
    parts: list[str] = []
    last_idx = len(line.words) - 1
    for i, word in enumerate(line.words):
        if i == last_idx and len(line.words) >= 2:
            duration_cs = max(1, int(_cap_last_word_duration(line) * 100))
        else:
            duration_cs = max(1, int((word.end - word.start) * 100))
        parts.append(f"{{\\kf{duration_cs}}}{word.text}")
        # Add separator with gap timing between words
        if i < last_idx:
            next_word = line.words[i + 1]
            gap_cs = max(0, int((next_word.start - word.end) * 100))
            is_cjk_pair = _is_cjk_text(word.text) and _is_cjk_text(next_word.text)
            if is_cjk_pair:
                if gap_cs > 0:
                    parts.append(f"{{\\kf{gap_cs}}}")
            else:
                if gap_cs > 0:
                    parts.append(f"{{\\kf{gap_cs}}} ")
                else:
                    parts.append(" ")
    return "".join(parts)


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
    vocals_path: Path | None = None,
    vocals_volume: float = 0.3,
) -> None:
    """Use ffmpeg to burn ASS subtitles onto video with audio.

    When vocals_path is provided, mixes vocals at reduced volume with the
    instrumental so you can hear the original singer for sync verification.
    """
    escaped_ass = str(ass_path).replace("\\", "\\\\").replace(":", "\\:")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
    ]

    if vocals_path:
        # Add vocals as a third input and mix with instrumental
        cmd.extend(["-i", str(vocals_path)])
        cmd.extend([
            "-filter_complex",
            f"[1:a]volume=1.0[inst];[2:a]volume={vocals_volume}[vox];[inst][vox]amix=inputs=2:duration=longest[aout]",
            "-vf", f"ass={escaped_ass}",
            "-map", "0:v:0",
            "-map", "[aout]",
        ])
        logger.info("Mixing vocals at %.0f%% volume for sync debugging", vocals_volume * 100)
    else:
        cmd.extend([
            "-vf", f"ass={escaped_ass}",
            "-map", "0:v:0",
            "-map", "1:a:0",
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path),
    ])

    logger.info("Running ffmpeg to render karaoke video")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit code {result.returncode}):\n{result.stderr}"
        )
