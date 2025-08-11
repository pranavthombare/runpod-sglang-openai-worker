# syntax=docker/dockerfile:1.4
# Example: Bake a model into your SGLang server image
# Usage (public model):
#   DOCKER_BUILDKIT=1 docker build --platform linux/amd64 \
#     --build-arg MODEL_ID=Qwen/Qwen2.5-7B-Instruct \
#     --build-arg MODEL_REVISION=main \
#     -t your-namespace/sglang-baked:latest .
# Usage (private model with HF token as secret):
#   DOCKER_BUILDKIT=1 docker build --platform linux/amd64 \
#     --build-arg MODEL_ID=your/private-model \
#     --secret id=hf_token,env=HF_TOKEN \
#     -t your-namespace/sglang-baked:latest .

FROM python:3.10-slim

ARG MODEL_ID
ARG MODEL_REVISION=""
ENV HF_HOME=/root/.cache/huggingface \
    LOCAL_MODEL_DIR=/models \
    HF_HUB_ENABLE_HF_TRANSFER=1

WORKDIR /app

# Install deps to download models; adjust per your SGLang server needs
RUN pip install --no-cache-dir huggingface_hub

# Download weights at build time. If a secret hf_token is provided, it will be
# available at build time only and will not persist in the final image layers.
COPY download_model.py ./
ENV MODEL_ID=${MODEL_ID} \
    MODEL_REVISION=${MODEL_REVISION}

# Try with secret; fallback to no token if not provided
RUN --mount=type=secret,id=hf_token,required=false /bin/sh -lc 'if [ -f /run/secrets/hf_token ]; then \
        export HF_TOKEN="$(cat /run/secrets/hf_token)"; \
        echo "Using HF token from build secret"; \
    else \
        echo "No HF token secret provided; downloading public model if allowed"; \
    fi; \
    python download_model.py; \
    ls -lah /models'

# Copy your actual SGLang server code and set up serving as needed...
# COPY server.py ./
# RUN pip install sglang ...
# EXPOSE 30000
# CMD ["python", "server.py", "--model", "/models"]
