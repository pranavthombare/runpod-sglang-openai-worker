ARG BASE_IMAGE=python:3.10-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install minimal deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY handler.py sglang_client.py start.sh ./
RUN chmod +x start.sh

# Default envs (can be overridden by RunPod)
ENV SGLANG_BASE_URL="" \
    SGLANG_API_KEY="" \
    SGLANG_MODEL="" \
    SGLANG_TIMEOUT=300

CMD ["./start.sh"]
