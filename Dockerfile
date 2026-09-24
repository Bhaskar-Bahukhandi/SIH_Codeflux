FROM node:22-bookworm-slim AS dashboard-builder

WORKDIR /build/dashboard
COPY apps/dashboard/package.json ./
RUN npm install --no-audit --no-fund
COPY apps/dashboard/ ./
RUN npm run build


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DASHBOARD_ROOT=/app/dashboard \
    MEDIA_ROOT=/data/media \
    OCR_INFERENCE_ENGINE=paddle \
    OCR_LANGUAGE=en \
    OCR_MODEL_VERSION=PP-OCRv5 \
    OCR_DEVICE=cpu \
    OCR_MIN_CONFIDENCE=0.0 \
    OCR_DETECTION_MAX_DIMENSION=960 \
    OCR_ENABLE_MKLDNN=false \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/services/api
COPY services/api/ ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ".[ocr]"

COPY scripts/prefetch_ocr_models.py /app/scripts/prefetch_ocr_models.py
RUN python /app/scripts/prefetch_ocr_models.py

COPY --from=dashboard-builder /build/dashboard/dist /app/dashboard

EXPOSE 8000

CMD ["/bin/sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
