"""Structured data types for the karaoke pipeline."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SyncedLine:
    """A single lyrics line with its timestamp from LRC format."""

    timestamp: float
    text: str


@dataclass
class LyricsResult:
    """Output of the lyrics fetch stage."""

    plain_text: str
    synced_lines: list[SyncedLine] | None = None

    @property
    def has_synced_timestamps(self) -> bool:
        return self.synced_lines is not None and len(self.synced_lines) > 0


@dataclass
class DownloadResult:
    """Output of the download stage."""

    video_path: Path
    audio_path: Path
    title: str
    video_id: str
    track: str | None = None
    artist: str | None = None


@dataclass
class SeparationResult:
    """Output of the source separation stage."""

    vocals_path: Path
    instrumental_path: Path


@dataclass
class TimedWord:
    """A single word with its start and end timestamps in seconds."""

    text: str
    start: float
    end: float


@dataclass
class TimedLine:
    """A line of lyrics with word-level timestamps."""

    words: list[TimedWord] = field(default_factory=list)

    @property
    def start(self) -> float:
        return self.words[0].start if self.words else 0.0

    @property
    def end(self) -> float:
        return self.words[-1].end if self.words else 0.0

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass
class AlignmentResult:
    """Output of the lyrics alignment stage."""

    lines: list[TimedLine]


@dataclass
class RenderResult:
    """Output of the render stage."""

    output_path: Path
