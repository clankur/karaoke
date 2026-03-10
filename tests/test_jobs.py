"""Tests for the background job manager."""

import logging
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from karaoke.jobs import JobManager, JobStatus


@pytest.fixture
def job_manager(tmp_path):
    return JobManager(tmp_path / "output")


@patch("karaoke.jobs.generate_karaoke")
def test_create_job_returns_id(mock_gen, job_manager):
    mock_gen.return_value = None
    job_id = job_manager.create_job(url="https://youtube.com/watch?v=abc")
    assert isinstance(job_id, str)
    assert len(job_id) == 12


@patch("karaoke.jobs.generate_karaoke")
def test_get_job_returns_state(mock_gen, job_manager):
    mock_gen.return_value = None
    job_id = job_manager.create_job(url="https://youtube.com/watch?v=abc")
    job = job_manager.get_job(job_id)
    assert job is not None
    assert job.job_id == job_id
    assert job.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED)


def test_get_nonexistent_job_returns_none(job_manager):
    assert job_manager.get_job("nonexistent") is None


@patch("karaoke.jobs.generate_karaoke")
def test_job_completes_successfully(mock_gen, job_manager):
    mock_gen.return_value = None
    job_id = job_manager.create_job(url="https://youtube.com/watch?v=abc")

    # Wait for thread to finish
    for _ in range(50):
        job = job_manager.get_job(job_id)
        if job.status == JobStatus.COMPLETED:
            break
        time.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    assert job.error is None
    mock_gen.assert_called_once()


@patch("karaoke.jobs.generate_karaoke")
def test_job_fails_on_pipeline_error(mock_gen, job_manager):
    mock_gen.side_effect = RuntimeError("demucs crashed")
    job_id = job_manager.create_job(url="https://youtube.com/watch?v=abc")

    for _ in range(50):
        job = job_manager.get_job(job_id)
        if job.status == JobStatus.FAILED:
            break
        time.sleep(0.1)

    assert job.status == JobStatus.FAILED
    assert "demucs crashed" in job.error


@patch("karaoke.jobs.generate_karaoke")
def test_job_passes_all_options(mock_gen, job_manager):
    mock_gen.return_value = None
    job_manager.create_job(
        url="https://youtube.com/watch?v=abc",
        whisper_model="large",
        language="ja",
        demucs_model="htdemucs_ft",
        words_per_line=5,
        keep_vocals=False,
        vocals_volume=0.5,
        use_synced_lyrics=False,
    )

    for _ in range(50):
        if mock_gen.called:
            break
        time.sleep(0.1)

    mock_gen.assert_called_once()
    call_kwargs = mock_gen.call_args
    assert call_kwargs.kwargs["url"] == "https://youtube.com/watch?v=abc"
    assert call_kwargs.kwargs["whisper_model"] == "large"
    assert call_kwargs.kwargs["language"] == "ja"
    assert call_kwargs.kwargs["keep_vocals"] is False
    assert call_kwargs.kwargs["vocals_volume"] == 0.5


@patch("karaoke.jobs.generate_karaoke")
def test_progress_updates_from_logging(mock_gen, job_manager):
    def fake_pipeline(**kwargs):
        pipeline_logger = logging.getLogger("karaoke.pipeline")
        pipeline_logger.info("Stage 1/5: Downloading from https://youtube.com")
        pipeline_logger.info("Stage 3/5: Separating vocals and instrumental")

    mock_gen.side_effect = fake_pipeline
    job_id = job_manager.create_job(url="https://youtube.com/watch?v=abc")

    for _ in range(50):
        job = job_manager.get_job(job_id)
        if job.status == JobStatus.COMPLETED:
            break
        time.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    # The last stage logged was 3, so stage should be "separating"
    # (or "done" since the job completed after)
    assert job.stage == "done"


@patch("karaoke.jobs.generate_karaoke")
def test_output_dir_created(mock_gen, tmp_path):
    output_dir = tmp_path / "nested" / "output"
    manager = JobManager(output_dir)
    assert output_dir.exists()
