"""Background job manager for karaoke generation."""

import logging
import re
import threading
import time
import uuid
from enum import Enum
from pathlib import Path

from karaoke.pipeline import generate_karaoke

logger = logging.getLogger(__name__)

_STAGE_NAMES = {
    "1": "downloading",
    "2": "lyrics",
    "3": "separating",
    "4": "aligning",
    "5": "rendering",
}

_STAGE_PATTERN = re.compile(r"Stage (\d)/5: (.+)")


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


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


class _JobProgressHandler(logging.Handler):
    """Intercepts pipeline log messages to update job progress."""

    def __init__(self, job: JobState, lock: threading.Lock) -> None:
        super().__init__()
        self._job = job
        self._lock = lock

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        match = _STAGE_PATTERN.match(msg)
        if match:
            stage_num, description = match.groups()
            with self._lock:
                self._job.stage = _STAGE_NAMES.get(stage_num, f"stage-{stage_num}")
                self._job.progress_message = description


class JobManager:
    """Manages background karaoke generation jobs."""

    def __init__(self, output_dir: Path) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def create_job(
        self,
        url: str,
        whisper_model: str = "base",
        language: str | None = None,
        demucs_model: str = "htdemucs",
        words_per_line: int = 7,
        keep_vocals: bool = True,
        vocals_volume: float = 0.3,
        use_synced_lyrics: bool = True,
    ) -> str:
        """Create and start a generation job. Returns the job ID."""
        job_id = uuid.uuid4().hex[:12]
        output_path = self._output_dir / f"{job_id}.mp4"
        job = JobState(job_id, output_path)

        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._run,
            args=(job, url, whisper_model, language, demucs_model,
                  words_per_line, keep_vocals, vocals_volume, use_synced_lyrics),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_job(self, job_id: str) -> JobState | None:
        """Get the current state of a job, or None if not found."""
        with self._lock:
            return self._jobs.get(job_id)

    def _run(
        self,
        job: JobState,
        url: str,
        whisper_model: str,
        language: str | None,
        demucs_model: str,
        words_per_line: int,
        keep_vocals: bool,
        vocals_volume: float,
        use_synced_lyrics: bool,
    ) -> None:
        """Execute the pipeline in a background thread."""
        pipeline_logger = logging.getLogger("karaoke.pipeline")
        handler = _JobProgressHandler(job, self._lock)
        pipeline_logger.addHandler(handler)

        with self._lock:
            job.status = JobStatus.RUNNING

        try:
            generate_karaoke(
                url=url,
                output_path=job.output_path,
                whisper_model=whisper_model,
                language=language,
                demucs_model=demucs_model,
                words_per_line=words_per_line,
                keep_vocals=keep_vocals,
                vocals_volume=vocals_volume,
                use_synced_lyrics=use_synced_lyrics,
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
        finally:
            pipeline_logger.removeHandler(handler)
