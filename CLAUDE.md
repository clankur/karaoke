# CLAUDE.md

This file provides guidance for Claude Code (claude.ai/claude-code) when working with this codebase.

## Project Overview

This project generates karaoke videos from YouTube song URLs. It handles downloading audio/video, separating vocals from instrumentals, aligning lyrics with timestamps, and rendering the final karaoke video with synchronized highlighted text.

## Coding Principles

**CRITICAL RULES - You MUST follow these without exception:**

### 1. Pipeline Authority
- The processing pipeline (download → separate → align → render) is the source of truth for all transformations.
- **NEVER** put processing logic in the UI or API layer. Those layers ONLY: accept input, invoke the pipeline, and return/display results.
- Each pipeline stage should have a clear input/output contract. If you're tempted to do audio/video manipulation outside the pipeline, STOP and put it in the appropriate pipeline stage instead.

### 2. Error Handling
- **NEVER** silently swallow errors with bare `except:` or empty catch blocks.
- Errors MUST be raised, logged, or explicitly handled. Fail loudly.
- External tool failures (yt-dlp, ffmpeg, etc.) MUST produce clear error messages indicating which tool failed and why.

### 3. Testing Requirements
- **Every bug fix MUST include a regression test** in `tests/`. No exceptions.
- **Every new feature MUST have unit tests** in `tests/`. No "I'll test it manually" — write pytest tests.
- Use fixtures and mocks for external dependencies (YouTube downloads, ffmpeg calls, ML model inference).
- Run `uv run pytest` before considering any change complete.

### 4. No Backwards Compatibility Concerns
- **DO NOT** write migration code, compatibility shims, or preserve old formats.
- If your change breaks cached/intermediate files, that's fine — users can re-run the pipeline from scratch.
- Just make the clean implementation.

### 5. Code Quality

#### No String-Encoded Data
- **NEVER** pack multiple values into a single string (e.g., `f"{start_time},{end_time},{lyric}"` that gets split elsewhere).
- Use structured data: dataclasses, Pydantic models, typed dicts, or separate fields instead.

#### Dependency Isolation
- Wrap calls to external tools (yt-dlp, ffmpeg, demucs, etc.) behind clean interfaces so they can be swapped, mocked, or upgraded independently.
- **DO NOT** scatter raw subprocess calls throughout the codebase.

### 6. Media File Handling
- **NEVER** hardcode file paths or formats. Use configurable output directories and support common audio/video formats.
- Temporary/intermediate files MUST be cleaned up or stored in a clearly designated temp/cache directory.
- Large media files (audio, video) MUST NOT be committed to the repository.
