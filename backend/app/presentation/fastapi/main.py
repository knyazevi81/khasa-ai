import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.infrastructure.config.config import get_settings
from app.infrastructure.logging.setup import configure_logging
from app.presentation.fastapi.middleware.exception import ExceptionMiddleware
from app.presentation.fastapi.middleware.request_id import RequestIdMiddleware
from app.presentation.fastapi.routers.auth import router as auth_router
from app.presentation.fastapi.routers.chats import router as chats_router
from app.presentation.fastapi.routers.llm import router as llm_router
from app.presentation.fastapi.routers.ping import router as ping_router
from app.presentation.fastapi.routers.users import router as users_router

settings = get_settings()
logger = logging.getLogger("khasa")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    logger.info("khasa: started")
    yield
    logger.info("khasa: stopped")


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_TITLE,
        description=settings.PROJECT_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(ExceptionMiddleware, logger=logging.getLogger("exception_middleware"))
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(users_router, prefix=prefix)
    app.include_router(llm_router, prefix=prefix)
    app.include_router(chats_router, prefix=prefix)
    app.include_router(ping_router, prefix=prefix)

    @app.get("/health/live")
    async def liveness() -> dict:
        return {"status": "alive"}

    @app.get("/health/ready")
    async def readiness() -> dict:
        return {"status": "ready"}

    Instrumentator().instrument(app).expose(app)
    return app


app = create_application()
