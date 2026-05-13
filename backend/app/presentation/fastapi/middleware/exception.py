import logging

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.domain.exceptions.base import AppException


class ExceptionMiddleware(BaseHTTPMiddleware):
    """
    Ловит AppException и мапит на JSON-ответ {code, message}.
    Любые незапланированные исключения → 500.
    """

    def __init__(self, app, logger: logging.Logger | None = None) -> None:
        super().__init__(app)
        self.logger = logger or logging.getLogger(__name__)

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except AppException as exc:
            return JSONResponse(
                status_code=exc.code,
                content={"detail": exc.message, "code": exc.code},
            )
        except Exception as exc:
            self.logger.exception("unhandled: %s", exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "code": 500},
            )
