# Placewise API image (FastAPI + Python 3.12, dependencies managed by uv).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first, so code changes don't invalidate this cached layer.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Then the app itself.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Prompts are part of the app (mounted over in dev for live edits).
COPY prompts ./prompts

# Run as a non-root user. /app/storage must exist and be owned by the app user BEFORE a named
# volume is mounted there, so fresh volumes inherit that ownership (uploads failed when it was root-owned).
RUN useradd --create-home --uid 1000 app && mkdir -p /app/storage/uploads && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/livez', timeout=2)" || exit 1

# keep-alive above the web proxy's idle timeout, so a reused connection is never closed mid-request
CMD ["uvicorn", "placewise.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "75"]
