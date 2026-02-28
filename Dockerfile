# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
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

# Install uv for dependency management
RUN curl -Ls https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen
ENV VIRTUAL_ENV=/app/backend/.venv
ENV PATH="/app/backend/.venv/bin:${PATH}"

COPY VERSION /app/VERSION
COPY backend/ ./
COPY docker/ /app/docker/

# Copy built frontend assets
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

ENV FRONTEND_DIST=/app/frontend/dist

EXPOSE 8000
CMD ["/app/docker/entrypoint.sh"]
