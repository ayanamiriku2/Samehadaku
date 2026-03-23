#!/bin/bash
# Start script for VPS deployment (tanpa Docker)
# Usage: ./start.sh
#
# Prerequisites:
#   sudo apt update && sudo apt install -y python3 python3-pip python3-venv
#
# Setup:
#   python3 -m venv venv
#   source venv/bin/activate
#   pip install -r requirements.txt
#
# Run:
#   ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Defaults
export PORT=${PORT:-8000}
export HOST=${HOST:-0.0.0.0}
export WORKERS=${WORKERS:-4}

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Starting mirror proxy on $HOST:$PORT with $WORKERS workers"
echo "Source: ${SOURCE_DOMAIN:-v2.samehadaku.how}"
echo "Mirror: ${MIRROR_DOMAIN:-localhost:$PORT}"

exec uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --proxy-headers \
    --forwarded-allow-ips='*'
