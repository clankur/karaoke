"""Tests for the FastAPI web API."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from karaoke.api import create_app
from karaoke.models import VideoSearchResult


@pytest.fixture
def client():
    app = create_app()
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
