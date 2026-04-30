"""CORS middleware configuration.

Requirement 12.7: Restrict allowed origins to the frontend domain.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


def configure_cors(app: FastAPI) -> None:
    """Add CORS middleware to the FastAPI application.

    Uses ``settings.cors_allowed_origins`` to restrict which origins
    may make cross-origin requests.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
