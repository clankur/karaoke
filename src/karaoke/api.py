"""Web API: FastAPI application for the karaoke UI."""

import logging
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from karaoke.jobs import JobManager, JobStatus
from karaoke.search import search_videos

logger = logging.getLogger(__name__)


# --- Response models ---

class VideoSearchResultResponse(BaseModel):
    video_id: str
    title: str
    thumbnail_url: str
    channel: str
    duration_seconds: int
    url: str


class SearchResponse(BaseModel):
    results: list[VideoSearchResultResponse]


class GenerateRequest(BaseModel):
    url: str
    whisper_model: str = "base"
    language: str | None = None
    demucs_model: str = "htdemucs"
    words_per_line: int = 7
    keep_vocals: bool = True
    vocals_volume: float = 0.3
    use_synced_lyrics: bool = True


class GenerateResponse(BaseModel):
    job_id: str


class JobResponse(BaseModel):
    job_id: str
    status: str
    stage: str | None
    progress_message: str | None
    error: str | None


def create_app(output_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Karaoke", version="0.1.0")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    job_manager = JobManager(output_dir or Path("output"))

    @application.get("/api/search", response_model=SearchResponse)
    def search(
        q: str = Query(min_length=1),
        max_results: int = Query(default=5, ge=1, le=10),
    ) -> SearchResponse:
        try:
            results = search_videos(q, max_results=max_results)
        except RuntimeError as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})

        return SearchResponse(
            results=[
                VideoSearchResultResponse(
                    video_id=r.video_id,
                    title=r.title,
                    thumbnail_url=r.thumbnail_url,
                    channel=r.channel,
                    duration_seconds=r.duration_seconds,
                    url=r.url,
                )
                for r in results
            ]
        )

    @application.post("/api/generate", response_model=GenerateResponse, status_code=202)
    def generate(request: GenerateRequest) -> GenerateResponse:
        job_id = job_manager.create_job(
            url=request.url,
            whisper_model=request.whisper_model,
            language=request.language,
            demucs_model=request.demucs_model,
            words_per_line=request.words_per_line,
            keep_vocals=request.keep_vocals,
            vocals_volume=request.vocals_volume,
            use_synced_lyrics=request.use_synced_lyrics,
        )
        return GenerateResponse(job_id=job_id)

    @application.get("/api/jobs/{job_id}", response_model=JobResponse)
    def get_job(job_id: str) -> JobResponse:
        job = job_manager.get_job(job_id)
        if job is None:
            return JSONResponse(status_code=404, content={"detail": "Job not found"})
        return JobResponse(
            job_id=job.job_id,
            status=job.status.value,
            stage=job.stage,
            progress_message=job.progress_message,
            error=job.error,
        )

    @application.get("/api/jobs/{job_id}/download")
    def download_job(job_id: str) -> FileResponse:
        job = job_manager.get_job(job_id)
        if job is None:
            return JSONResponse(status_code=404, content={"detail": "Job not found"})
        if job.status != JobStatus.COMPLETED:
            return JSONResponse(status_code=409, content={"detail": "Job not yet completed"})
        return FileResponse(
            path=str(job.output_path),
            media_type="video/mp4",
            filename=f"karaoke-{job_id}.mp4",
        )

    return application


app = create_app()


def main() -> None:
    """Entry point for the karaoke-api console script."""
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run("karaoke.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
