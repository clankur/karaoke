# Karaoke Video Generator

Generate karaoke videos from YouTube URLs. Downloads the video, separates vocals from instrumentals, transcribes lyrics with word-level timestamps, and renders a karaoke video with synchronized highlighted text.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- [ffmpeg](https://ffmpeg.org/) installed and on your PATH

## Setup

```bash
# Clone the repo
git clone <repo-url>
cd karaoke

# Install dependencies
uv sync
```

## Usage

```bash
# Basic usage — generates output.mp4 in the current directory
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID"

# Specify output path
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID" -o my_karaoke.mp4

# Keep intermediate files (downloaded video, separated stems, etc.)
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID" --work-dir ./workdir

# Use a larger Whisper model for better transcription accuracy
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID" --whisper-model medium

# Adjust words per subtitle line
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID" --words-per-line 5

# Specify language for non-English songs
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID" --language ja

# Strip vocals entirely from the output
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID" --no-vocals

# Keep vocals but at a lower volume
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID" --vocals-volume 0.1

# Ignore synced LRC timestamps (use plain lyrics instead)
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID" --no-synced-lyrics

# Enable verbose logging
uv run karaoke "https://www.youtube.com/watch?v=VIDEO_ID" -v
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `output.mp4` | Output video path |
| `--work-dir` | temp directory | Directory for intermediate files (cleaned up if not set) |
| `--whisper-model` | `base` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large` |
| `--demucs-model` | `htdemucs` | Demucs model for source separation |
| `--language` | auto-detect | Language code for lyrics (e.g., `ja`, `ko`, `zh`, `hi`, `en`) |
| `--words-per-line` | `7` | Max words per subtitle line |
| `--no-vocals` | off | Strip vocals entirely from the output |
| `--vocals-volume` | `0.3` | Volume for vocals in output, `0.0`–`1.0` |
| `--no-synced-lyrics` | off | Ignore synced LRC timestamps and use plain lyrics instead |
| `-v, --verbose` | off | Enable debug logging |

## How It Works

1. **Download** — Fetches video and audio from YouTube using yt-dlp
2. **Separate** — Splits audio into vocals and instrumentals using demucs
3. **Align** — Transcribes vocals with word-level timestamps using stable-ts (Whisper)
4. **Render** — Generates ASS subtitles with karaoke highlighting and burns them onto the video with the instrumental track using ffmpeg

## Running Tests

```bash
# All tests
uv run pytest

# Single test file
uv run pytest tests/test_align.py

# Single test with verbose output
uv run pytest tests/test_render.py::test_name -v
```
