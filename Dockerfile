# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY backend/openapi.json /app/backend/openapi.json
RUN ORVAL_API_URL=../backend/openapi.json npx orval --config orval.config.ts
RUN npm run build-only

FROM python:3.13-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app/backend

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the app (issue #150). The app is network-based
# (Postgres/SQLite, Qdrant/Weaviate, Redis) and writes no local files
# (PYTHONDONTWRITEBYTECODE=1), so it only needs read access to /app and write
# access to the world-writable /tmp.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

# Install uv to a world-accessible location (not /root/.local/bin, which lives
# in root's mode-0700 home and is invisible to the non-root user).
ENV UV_INSTALL_DIR=/usr/local/bin
RUN curl -Ls https://astral.sh/uv/install.sh | sh
ENV PATH="/usr/local/bin:${PATH}"

# Build the venv as the non-root user so it owns the .venv it creates.
# /app/backend is root-owned; hand it to appuser (chown needs root privilege)
# so `uv sync` can write .venv into the working directory.
COPY backend/pyproject.toml backend/uv.lock ./
RUN chown -R appuser:appuser /app/backend
USER appuser
RUN uv sync --frozen
USER root
ENV VIRTUAL_ENV=/app/backend/.venv
ENV PATH="/app/backend/.venv/bin:${PATH}"

COPY VERSION /app/VERSION
COPY backend/ ./
COPY docker/ /app/docker/

# Copy built frontend assets
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

ENV FRONTEND_DIST=/app/frontend/dist

# Run the app as the non-root user.
USER appuser

EXPOSE 8000
CMD ["/app/docker/entrypoint.sh"]
