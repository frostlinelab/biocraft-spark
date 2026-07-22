# ── Stage 1: Build the React frontend ────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /build

# Install deps first (layer cached unless package.json changes)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy source and build → /build/dist/
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ──────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . /app/

# Overlay the built frontend from stage 1 (takes precedence over any host dist)
COPY --from=frontend-builder /build/dist /app/frontend/dist

EXPOSE 25568

CMD ["python", "manage.py", "runserver", "0.0.0.0:25568"]
