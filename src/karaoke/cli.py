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
        )
        print(f"Karaoke video saved to: {result.output_path}")
    except Exception as e:
        logging.error("%s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
