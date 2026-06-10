# Python base with a Debian userland so we can apt-get Poppler.
FROM python:3.12-slim

# System dependency: Poppler provides pdftoppm, which pdf2image calls to
# rasterize PDF pages. Without it, extraction fails at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching: deps change less often than code).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY app ./app

# Cloud Run provides the port via $PORT (defaults to 8080). Bind to it.
ENV PORT=8080
EXPOSE 8080

# Use shell form so $PORT expands. Single worker is fine for a demo.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]