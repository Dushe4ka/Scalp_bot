#!/usr/bin/env bash
# Start Phase 2 Celery engine workers (example TRADE_ENGINE_COUNT=2).
set -euo pipefail
cd "$(dirname "$0")/.."

COUNT="${TRADE_ENGINE_COUNT:-2}"
echo "Starting $COUNT trade engine workers..."

for ((i=0; i<COUNT; i++)); do
  CELERY_ENGINE_ID="$i" celery -A celery_app.celery_config worker \
    -Q "trade_engine_${i}" \
    -n "engine${i}@%h" \
    --concurrency=1 \
    -l info &
done

echo "Engine workers started in background. PIDs: $!"
wait
