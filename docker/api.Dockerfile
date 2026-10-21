# Build context: the repository root (docker compose -f docker/compose.yaml build).

# The front-end, built once and served by the API.
FROM node:24-alpine AS web
WORKDIR /web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm exec vite build

FROM python:3.13-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PYTHON=/usr/local/bin/python3.13
WORKDIR /app
# Third-party dependencies first: this layer is rebuilt only when the lock changes. No BuildKit
# mount, so that the plain builder of a host builds it too.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-editable --no-cache
COPY shelfdrop ./shelfdrop
# No uv cache here: a cached wheel of shelfdrop would ship stale code while pyproject.toml is
# unchanged.
RUN uv sync --locked --no-dev --no-editable --no-cache

FROM python:3.13-slim-trixie
# ffmpeg merges the MP3 tracks of an audiobook into one M4B; poppler (pdftoppm) gives the first
# page of a PDF as its cover. The placement worker alone runs them.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg poppler-utils \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 shelfdrop \
    && useradd --system --uid 10001 --gid shelfdrop --no-create-home --shell /usr/sbin/nologin shelfdrop
COPY --from=builder /app/.venv /app/.venv
COPY --from=web /web/dist /app/static
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SHELFDROP_STATIC_DIR=/app/static \
    SHELFDROP_DATA_DIR=/data/shelfdrop
WORKDIR /app
# The directory of the database, owned by the user that writes there: a new named volume
# mounted on it takes this owner and this mode.
RUN mkdir -p /data/shelfdrop /var/lib/shelfdrop \
    && chown shelfdrop:shelfdrop /data/shelfdrop /var/lib/shelfdrop \
    && chmod 700 /data/shelfdrop /var/lib/shelfdrop
USER shelfdrop
EXPOSE 8000
CMD ["sh", "-c", "shelfdrop db upgrade && exec uvicorn --factory shelfdrop.main:create_app --host 0.0.0.0 --port 8000 --no-server-header"]
