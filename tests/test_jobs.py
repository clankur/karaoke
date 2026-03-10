"""Tests for the background job manager."""

import time
from unittest.mock import patch

import pytest

from karaoke.jobs import GenerateConfig, JobManager, JobStatus


def _config(url="https://youtube.com/watch?v=abc", **kwargs):
    return GenerateConfig(url=url, **kwargs)


@pytest.fixture
def job_manager(tmp_path):
    return JobManager(tmp_path / "output")


@patch("karaoke.jobs.generate_karaoke")
def test_create_job_returns_id(mock_gen, job_manager):
    mock_gen.return_value = None
    job_id = job_manager.create_job(_config())
    assert isinstance(job_id, str)
    assert len(job_id) == 12


@patch("karaoke.jobs.generate_karaoke")
def test_get_job_returns_state(mock_gen, job_manager):
    mock_gen.return_value = None
    job_id = job_manager.create_job(_config())
    job = job_manager.get_job(job_id)
    assert job is not None
    assert job.job_id == job_id
    assert job.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED)


def test_get_nonexistent_job_returns_none(job_manager):
    assert job_manager.get_job("nonexistent") is None


@patch("karaoke.jobs.generate_karaoke")
def test_job_completes_successfully(mock_gen, job_manager):
    mock_gen.return_value = None
    job_id = job_manager.create_job(_config())

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
    job_id = job_manager.create_job(_config())

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
    config = GenerateConfig(
        url="https://youtube.com/watch?v=abc",
        whisper_model="large",
        language="ja",
        demucs_model="htdemucs_ft",
        words_per_line=5,
        keep_vocals=False,
        vocals_volume=0.5,
        use_synced_lyrics=False,
    )
    job_manager.create_job(config)

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
def test_progress_updates_via_callback(mock_gen, job_manager):
    """Verify the on_progress callback updates job stage and message."""
    captured_stages = []

    def fake_pipeline(**kwargs):
        on_progress = kwargs.get("on_progress")
        assert on_progress is not None, "on_progress callback must be provided"
        on_progress("downloading", "Downloading from https://youtube.com")
        captured_stages.append("downloading")
        on_progress("separating", "Separating vocals and instrumental")
        captured_stages.append("separating")

    mock_gen.side_effect = fake_pipeline
    job_id = job_manager.create_job(_config())

    for _ in range(50):
        job = job_manager.get_job(job_id)
        if job.status == JobStatus.COMPLETED:
            break
        time.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    assert job.stage == "done"
    assert captured_stages == ["downloading", "separating"]


@patch("karaoke.jobs.generate_karaoke")
def test_output_dir_created(mock_gen, tmp_path):
    output_dir = tmp_path / "nested" / "output"
    JobManager(output_dir)
    assert output_dir.exists()
