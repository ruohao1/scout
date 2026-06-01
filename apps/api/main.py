from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.chat import router as chat_router
from .routes.explanations import router as explanations_router
from .routes.health import router as health_router
from .routes.jobs import router as jobs_router
from .routes.profiles import router as profiles_router
from .routes.ranking import router as ranking_router
from .routes.search import router as search_router


def create_app() -> FastAPI:
    app = FastAPI(title="Scout API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)
    app.include_router(explanations_router)
    app.include_router(health_router)
    app.include_router(jobs_router)
    app.include_router(profiles_router)
    app.include_router(ranking_router)
    app.include_router(search_router)
    return app


app = create_app()
