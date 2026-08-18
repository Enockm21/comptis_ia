#!/usr/bin/env bash
# Start the Comptis backend with env vars from .env (arm64 compatible)
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${REPO}/logs/backend.log"
mkdir -p "${REPO}/logs"
cd "$REPO"
echo "Starting Comptis backend on http://localhost:8000 (logs → $LOG)"
exec arch -arm64 env $(grep -v '^#' .env | grep -v '^$' | xargs) \
  uv run uvicorn comptis.interface.api.main:app --reload --port 8000 >> "$LOG" 2>&1
