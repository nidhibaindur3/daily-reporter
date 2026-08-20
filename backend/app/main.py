from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.market import router as market_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.container import build_runtime


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    runtime = build_runtime(get_settings())
    application.state.market_service = runtime.market_service
    try:
        yield
    finally:
        runtime.close()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Daily Digest API",
        description=(
            "Backend API for deterministic market data and evidence-backed "
            "Research Discovery."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(health_router, prefix="/api")
    application.include_router(market_router, prefix="/api")
    application.include_router(v1_router, prefix="/api/v1")
    return application


app = create_app()
