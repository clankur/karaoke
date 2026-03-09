"""Web API: FastAPI application for the karaoke UI."""

import logging

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from karaoke.search import search_videos

logger = logging.getLogger(__name__)


class VideoSearchResultResponse(BaseModel):
    video_id: str
    title: str
    thumbnail_url: str
    channel: str
    duration_seconds: int
    url: str


class SearchResponse(BaseModel):
    results: list[VideoSearchResultResponse]


class ErrorResponse(BaseModel):
    detail: str


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title="Karaoke", version="0.1.0")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @application.get("/api/search", response_model=SearchResponse)
    def search(
        q: str = Query(min_length=1),
        max_results: int = Query(default=5, ge=1, le=10),
    ) -> SearchResponse:
        try:
            results = search_videos(q, max_results=max_results)
        except RuntimeError as e:
            from fastapi.responses import JSONResponse

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

    return application


app = create_app()


def main() -> None:
    """Entry point for the karaoke-api console script."""
    import uvicorn

    uvicorn.run("karaoke.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
