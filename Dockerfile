FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY paperboy/ ./paperboy/
RUN pip wheel --wheel-dir /wheels ".[api,email]"

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PAPERBOY_APP_ROOT=/app \
    PAPERBOY_ROOT=/app/data \
    PAPERBOY_DB=/app/data/events.db

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install /wheels/* && rm -rf /wheels
COPY config/ ./config/
COPY product/ ./product/
COPY examples/ ./examples/

RUN useradd -m -u 1000 paperboy && \
    mkdir -p /app/data && \
    chown -R paperboy:paperboy /app
USER paperboy

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "paperboy.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
