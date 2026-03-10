"""Tests for the FastAPI web API."""

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from karaoke.api import create_app
from karaoke.models import VideoSearchResult


@pytest.fixture
def client(tmp_path):
    app = create_app(output_dir=tmp_path / "output")
    return TestClient(app)


def _make_result(video_id="abc123"):
    return VideoSearchResult(
        video_id=video_id,
        title="Test Song",
        thumbnail_url="https://img.youtube.com/vi/abc123/0.jpg",
        channel="Test Channel",
        duration_seconds=240,
        url=f"https://www.youtube.com/watch?v={video_id}",
    )


@patch("karaoke.api.search_videos")
def test_search_endpoint_success(mock_search, client):
    mock_search.return_value = [_make_result(), _make_result("def456")]

    resp = client.get("/api/search", params={"q": "test song"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 2
    assert data["results"][0]["video_id"] == "abc123"
    assert data["results"][1]["video_id"] == "def456"
    mock_search.assert_called_once_with("test song", max_results=5)


def test_search_endpoint_missing_query(client):
    resp = client.get("/api/search")
    assert resp.status_code == 422


def test_search_endpoint_empty_query(client):
    resp = client.get("/api/search", params={"q": ""})
    assert resp.status_code == 422


@patch("karaoke.api.search_videos")
def test_search_endpoint_max_results_param(mock_search, client):
    mock_search.return_value = []

    resp = client.get("/api/search", params={"q": "test", "max_results": 3})

    assert resp.status_code == 200
    mock_search.assert_called_once_with("test", max_results=3)


@patch("karaoke.api.search_videos")
def test_search_endpoint_ytdlp_failure(mock_search, client):
    mock_search.side_effect = RuntimeError("yt-dlp search failed")

    resp = client.get("/api/search", params={"q": "fail"})

    assert resp.status_code == 500
    assert "yt-dlp search failed" in resp.json()["detail"]


# --- Generation endpoint tests ---

@patch("karaoke.jobs.generate_karaoke")
def test_generate_endpoint_returns_job_id(mock_gen, client):
    mock_gen.return_value = None
    resp = client.post("/api/generate", json={"url": "https://youtube.com/watch?v=abc"})
    assert resp.status_code == 202
    assert "job_id" in resp.json()
    assert isinstance(resp.json()["job_id"], str)


def test_generate_endpoint_missing_url(client):
    resp = client.post("/api/generate", json={})
    assert resp.status_code == 422


@patch("karaoke.jobs.generate_karaoke")
def test_job_status_endpoint(mock_gen, client):
    mock_gen.return_value = None
    resp = client.post("/api/generate", json={"url": "https://youtube.com/watch?v=abc"})
    job_id = resp.json()["job_id"]

    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] in ("pending", "running", "completed")


def test_job_status_not_found(client):
    resp = client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404


def test_job_download_not_found(client):
    resp = client.get("/api/jobs/nonexistent/download")
    assert resp.status_code == 404


@patch("karaoke.jobs.generate_karaoke")
def test_job_download_not_ready(mock_gen, client):
    # Make pipeline hang so the job stays running
    import threading
    barrier = threading.Event()
    mock_gen.side_effect = lambda **kwargs: barrier.wait(timeout=5)

    resp = client.post("/api/generate", json={"url": "https://youtube.com/watch?v=abc"})
    job_id = resp.json()["job_id"]

    # Give thread time to start
    time.sleep(0.1)

    resp = client.get(f"/api/jobs/{job_id}/download")
    assert resp.status_code == 409
    barrier.set()  # unblock the thread


@patch("karaoke.jobs.generate_karaoke")
def test_job_download_completed(mock_gen, client, tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)

    def fake_pipeline(**kwargs):
        # Write a fake output file
        kwargs["output_path"].write_bytes(b"fake mp4 data")

    mock_gen.side_effect = fake_pipeline

    resp = client.post("/api/generate", json={"url": "https://youtube.com/watch?v=abc"})
    job_id = resp.json()["job_id"]

    # Wait for job to complete
    for _ in range(50):
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] == "completed":
            break
        time.sleep(0.1)

    resp = client.get(f"/api/jobs/{job_id}/download")
    assert resp.status_code == 200
    assert resp.content == b"fake mp4 data"
