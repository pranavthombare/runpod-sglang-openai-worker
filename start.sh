#!/usr/bin/env sh
set -e

PORT="${SGLANG_PORT:-30000}"

# If no explicit command but a model path exists, build a default server command
if [ -z "${SGLANG_SERVER_CMD}" ]; then
  if [ -n "${MODEL_PATH}" ] || [ -d "/models" ]; then
    MPATH="${MODEL_PATH:-/models}"
    SGLANG_SERVER_CMD="python3 -m sglang.launch_server --host 0.0.0.0 --port ${PORT} --model-path ${MPATH} ${SGLANG_EXTRA_ARGS}"
  fi
fi

if [ -n "${SGLANG_SERVER_CMD}" ]; then
  echo "Starting local SGLang server: ${SGLANG_SERVER_CMD}"
  # shellcheck disable=SC2086
  sh -lc "${SGLANG_SERVER_CMD}" &
  SERVER_PID=$!
  echo "SGLang server PID: ${SERVER_PID}"
  # Wait for health by polling /v1/models via Python requests (already installed)
  python3 - <<PY
import os, sys, time
import requests

base = f"http://127.0.0.1:{int(os.getenv('SGLANG_PORT', '30000'))}"
url = f"{base}/v1/models"
deadline = time.time() + float(os.getenv('SGLANG_HEALTH_TIMEOUT', '120'))
interval = float(os.getenv('SGLANG_HEALTH_INTERVAL', '1.5'))
while time.time() < deadline:
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            print("SGLang server is up")
            sys.exit(0)
    except Exception:
        pass
    time.sleep(interval)
print("Timed out waiting for SGLang server", file=sys.stderr)
sys.exit(1)
PY
  # Default base URL to local server if not provided
  if [ -z "${SGLANG_BASE_URL}" ]; then
    export SGLANG_BASE_URL="http://127.0.0.1:${PORT}/v1"
  fi
fi

echo "Using SGLANG_BASE_URL=${SGLANG_BASE_URL}"
exec python -u handler.py
