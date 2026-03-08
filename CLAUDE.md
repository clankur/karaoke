# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Generates karaoke videos from YouTube song URLs. The pipeline downloads audio/video, separates vocals from instrumentals (demucs), aligns lyrics with word-level timestamps (stable-ts/whisper), and renders the final video with synchronized highlighted ASS subtitles (ffmpeg).

## Development Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_align.py

# Run a single test
uv run pytest tests/test_align.py::test_name -v

# Run the CLI
uv run karaoke <youtube-url> -o output.mp4
```

## Architecture

**Pipeline stages** (`src/karaoke/pipeline.py` orchestrates all four):

1. **Download** (`download.py`) — Uses `yt-dlp` Python API to fetch video (mp4) and audio (wav) from YouTube. Returns `DownloadResult`.
2. **Separate** (`separate.py`) — Runs `demucs` via subprocess to split audio into `vocals.wav` and `no_vocals.wav`. Returns `SeparationResult`.
3. **Align** (`align.py`) — Uses `stable_whisper` (Python API) to transcribe vocals with word-level timestamps, then groups words into lines. Returns `AlignmentResult`.
4. **Render** (`render.py`) — Generates ASS subtitle file with `\kf` karaoke tags, then runs `ffmpeg` subprocess to burn subtitles onto video with instrumental audio. Returns `RenderResult`.

**Data flow**: All inter-stage contracts are dataclasses in `models.py` (`DownloadResult`, `SeparationResult`, `TimedWord`, `TimedLine`, `AlignmentResult`, `RenderResult`). Stages communicate only through these types.

**Entry points**: CLI in `cli.py` (registered as `karaoke` console script). The CLI only parses args and calls `generate_karaoke()` — no processing logic in the CLI layer.

**External tools**: `yt-dlp` (Python API), `demucs` (subprocess), `stable-ts`/`whisper` (Python API), `ffmpeg` (subprocess). The subprocess-based tools (`demucs`, `ffmpeg`) are wrapped in private helper functions within their respective modules.

## Coding Principles

**CRITICAL RULES — follow without exception:**

### Pipeline Authority
- The pipeline is the source of truth for all transformations. **NEVER** put processing logic in the UI or API layer.
- Each stage has a clear input/output contract via dataclasses in `models.py`.

### Error Handling
- **NEVER** silently swallow errors. Fail loudly with clear messages indicating which external tool failed and why.

### Testing
- **Every bug fix MUST include a regression test.** Every new feature MUST have unit tests.
- Use fixtures and mocks for external dependencies (YouTube downloads, ffmpeg, ML inference).
- Run `uv run pytest` before considering any change complete.

### No Backwards Compatibility
- Do not write migration code or compatibility shims. Breaking cached/intermediate files is fine — users re-run the pipeline.

### No String-Encoded Data
- Never pack multiple values into a single string. Use dataclasses, Pydantic models, or typed dicts.

### Dependency Isolation
- Wrap external tool calls behind clean interfaces. Do not scatter raw subprocess calls throughout the codebase.

### Media File Handling
- Never hardcode file paths or formats. Use configurable output directories.
- Temp/intermediate files go in a designated temp/cache directory and must be cleaned up.
- Large media files must not be committed to the repository.
