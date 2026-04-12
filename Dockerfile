# syntax=docker/dockerfile:1

# --- Frontend (Vite) ---
FROM node:20-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Python app ---
FROM python:3.11-slim-bookworm AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

COPY config.yaml ./
COPY --from=frontend /build/frontend/dist ./frontend/dist

EXPOSE 8000

# Bind 0.0.0.0 so the host can reach the container (use reverse proxy + auth if exposing publicly).
CMD ["uvicorn", "boardroom.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
