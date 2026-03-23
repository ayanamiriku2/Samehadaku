FROM python:3.12-slim

# Install system deps for curl_cffi
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Default env vars (override at deploy time)
ENV SOURCE_DOMAIN=v2.samehadaku.how \
    SOURCE_SCHEME=https \
    MIRROR_DOMAIN=localhost:8000 \
    MIRROR_SCHEME=https \
    CACHE_ENABLED=true \
    CACHE_DIR=/tmp/mirror_cache \
    CACHE_TTL_HTML=300 \
    CACHE_TTL_ASSETS=86400 \
    PORT=8000 \
    HOST=0.0.0.0 \
    WORKERS=4 \
    IMPERSONATE_BROWSER=chrome \
    REQUEST_TIMEOUT=30

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host $HOST --port $PORT --workers $WORKERS --proxy-headers --forwarded-allow-ips='*'"]
