"""Background job manager for karaoke generation."""

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from karaoke.pipeline import generate_karaoke

logger = logging.getLogger(__name__)

_MAX_COMPLETED_JOBS = 50


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GenerateConfig:
    """Configuration for a karaoke generation job."""

    url: str
    whisper_model: str = "base"
    language: str | None = None
    demucs_model: str = "htdemucs"
    words_per_line: int = 7
    keep_vocals: bool = True
    vocals_volume: float = 0.3
    use_synced_lyrics: bool = True


class JobState:
    """Mutable state for a single generation job."""

    def __init__(self, job_id: str, output_path: Path) -> None:
        self.job_id = job_id
        self.status = JobStatus.PENDING
        self.stage: str | None = None
        self.progress_message: str | None = None
        self.output_path = output_path
        self.error: str | None = None
        self.created_at = time.time()


class JobManager:
    """Manages background karaoke generation jobs."""

    def __init__(self, output_dir: Path) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def create_job(self, config: GenerateConfig) -> str:
        """Create and start a generation job. Returns the job ID."""
        job_id = uuid.uuid4().hex[:12]
        output_path = self._output_dir / f"{job_id}.mp4"
        job = JobState(job_id, output_path)

        with self._lock:
            self._jobs[job_id] = job
            self._prune_old_jobs()

        thread = threading.Thread(
            target=self._run,
            args=(job, config),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_job(self, job_id: str) -> JobState | None:
        """Get the current state of a job, or None if not found."""
        with self._lock:
            return self._jobs.get(job_id)

    def _prune_old_jobs(self) -> None:
        """Remove oldest completed/failed jobs when over the limit. Must hold lock."""
        finished = [
            (j.created_at, jid)
            for jid, j in self._jobs.items()
            if j.status in (JobStatus.COMPLETED, JobStatus.FAILED)
        ]
        if len(finished) <= _MAX_COMPLETED_JOBS:
            return
        finished.sort()
        for _, jid in finished[: len(finished) - _MAX_COMPLETED_JOBS]:
            del self._jobs[jid]

    def _run(self, job: JobState, config: GenerateConfig) -> None:
        """Execute the pipeline in a background thread."""
        with self._lock:
            job.status = JobStatus.RUNNING

        def on_progress(stage: str, description: str) -> None:
            with self._lock:
                job.stage = stage
                job.progress_message = description

        try:
            generate_karaoke(
                url=config.url,
                output_path=job.output_path,
                whisper_model=config.whisper_model,
                language=config.language,
                demucs_model=config.demucs_model,
                words_per_line=config.words_per_line,
                keep_vocals=config.keep_vocals,
                vocals_volume=config.vocals_volume,
                use_synced_lyrics=config.use_synced_lyrics,
                on_progress=on_progress,
            )
            with self._lock:
                job.status = JobStatus.COMPLETED
                job.stage = "done"
                job.progress_message = "Karaoke video ready"
        except Exception as e:
            with self._lock:
                job.status = JobStatus.FAILED
                job.error = str(e)
            logger.error("Job %s failed: %s", job.job_id, e)
