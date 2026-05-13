import logging
import sys

from app.infrastructure.config.config import get_settings


def configure_logging() -> None:
    settings = get_settings()

    fmt = logging.Formatter(settings.LOGGING_FORMAT, datefmt=settings.LOGGING_DATEFMT)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL)

    # уменьшаем шум uvicorn access-логов
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
