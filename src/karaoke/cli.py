"""CLI entry point for the karaoke video generator."""

import argparse
import logging
import sys
from pathlib import Path

from karaoke.pipeline import generate_karaoke


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate a karaoke video from a YouTube URL."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output.mp4"),
        help="Output video path (default: output.mp4)",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Directory for intermediate files (default: temp directory)",
    )
    parser.add_argument(
        "--whisper-model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Language code for lyrics (e.g., 'ja', 'ko', 'zh', 'hi', 'en'). "
             "Default: auto-detect.",
    )
    parser.add_argument(
        "--demucs-model",
        default="htdemucs",
        help="Demucs model name (default: htdemucs)",
    )
    parser.add_argument(
        "--words-per-line",
        type=int,
        default=7,
        help="Max words per subtitle line (default: 7)",
    )
    parser.add_argument(
        "--no-vocals",
        action="store_true",
        help="Strip vocals entirely (default: keep vocals at low volume for sync debugging)",
    )
    parser.add_argument(
        "--vocals-volume",
        type=float,
        default=0.3,
        help="Volume for vocals in output, 0.0-1.0 (default: 0.3)",
    )
    parser.add_argument(
        "--no-synced-lyrics",
        action="store_true",
        help="Ignore synced LRC timestamps and use plain lyrics instead (useful when timestamps are inaccurate)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        result = generate_karaoke(
            url=args.url,
            output_path=args.output,
            work_dir=args.work_dir,
            whisper_model=args.whisper_model,
            demucs_model=args.demucs_model,
            words_per_line=args.words_per_line,
            keep_vocals=not args.no_vocals,
            vocals_volume=args.vocals_volume,
            use_synced_lyrics=not args.no_synced_lyrics,
            language=args.language,
        )
        print(f"Karaoke video saved to: {result.output_path}")
    except Exception as e:
        logging.error("%s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
