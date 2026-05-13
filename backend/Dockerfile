# ── Base ──────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
 && rm -rf /var/lib/apt/lists/*

# uv (быстрый pip)
RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

# ── Dev ───────────────────────────────────────────────────────────────────────
FROM base AS dev
COPY . /app
EXPOSE 8000
CMD ["uvicorn", "app.presentation.fastapi.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Prod ──────────────────────────────────────────────────────────────────────
FROM base AS prod
COPY . /app
EXPOSE 8000
CMD ["uvicorn", "app.presentation.fastapi.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
