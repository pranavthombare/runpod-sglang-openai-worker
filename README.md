# RunPod Serverless - SGLang OpenAI Chat Completions Proxy

This worker exposes a RunPod serverless handler that forwards requests to an SGLang OpenAI-compatible `/v1/chat/completions` endpoint. It supports both streaming and non-streaming responses.

## Features

- OpenAI-compatible input passthrough (messages, temperature, max_tokens, tools, etc.)
- Convenience `prompt` input converted to a single user message
- Streaming and non-streaming modes (`input.stream: true|false`)
- Environment-based configuration

## Inputs

Provide inputs under `input` in RunPod requests:

- messages: Array of OpenAI chat messages
- prompt: Optional convenience string; used if messages is absent
- model: Optional; defaults to `SGLANG_MODEL` env var
- stream: true for streaming, false for a single response
- Any other OpenAI chat params are forwarded (temperature, top_p, max_tokens, stop, tools, etc.)

## Environment Variables

- SGLANG_BASE_URL: Base URL to SGLang API (e.g., `http://host:30000/v1`). If you pass a URL not ending with `/v1`, it will be appended.
- SGLANG_API_KEY: Optional bearer token for SGLang.
- SGLANG_MODEL: Default model name used when `model` is not provided in input.
- SGLANG_TIMEOUT: Request timeout in seconds (default 300).

## Build and Push

```sh
# Build (amd64 is recommended for RunPod serverless)
docker build --platform linux/amd64 -t <your-dockerhub-username>/runpod-sglang-serverless:latest .

# Push
docker push <your-dockerhub-username>/runpod-sglang-serverless:latest
```

### GPU build with SGLang included (optional)

If you prefer a single container that can optionally run a local SGLang server and the worker, build the GPU image:

```sh
docker build -f Dockerfile.gpu --platform linux/amd64 -t <your-dockerhub-username>/runpod-sglang-serverless:gpu .
docker push <your-dockerhub-username>/runpod-sglang-serverless:gpu
```

Then set `SGLANG_SERVER_CMD` to start SGLang on container start, for example:

```sh
SGLANG_SERVER_CMD='python3 -m sglang.launch_server --host 0.0.0.0 --port 30000 \
  --model /models --trust-remote-code --tp 1 --max-model-len 32768'
```

If you’re instead pointing to an external SGLang service, leave `SGLANG_SERVER_CMD` empty and set `SGLANG_BASE_URL` to that service.

### About pre-downloading models

This worker proxies to an external SGLang server; model weights are owned and loaded by that server. If you want to avoid first-request download/compile latency, pre-bake the model into the SGLang server image during its Docker build (e.g., copy weights into the image, or run a setup script that downloads to the expected cache path). As a secondary option, this worker supports a warm-up call at startup to trigger model loading on the server:

- Set `WARMUP_ON_START=1` in the worker environment.
- Optionally set `WARMUP_MODEL` (defaults to `SGLANG_MODEL`), `WARMUP_PROMPT` (default `ping`), `WARMUP_MAX_TOKENS` (default `1`).

Note: Pre-baking in the SGLang server image is the most reliable way to ensure no cold start download time.

See `examples/sglang-server-baked/` for a sample approach that downloads Hugging Face model weights during Docker build and places them at `/models`. Avoid baking secrets into images: pass `HF_TOKEN` only at build time via a secure CI secret or use public models.

## Deploy on RunPod

- Create a new Serverless endpoint in the RunPod dashboard.
- Image: `<your-dockerhub-username>/runpod-sglang-serverless:latest`
- Entrypoint: default (Docker CMD runs `python -u handler.py`)
- Environment Variables: set `SGLANG_BASE_URL`, `SGLANG_API_KEY` (optional), `SGLANG_MODEL` (optional)
- Enable streaming on the endpoint if available. This repo sets `return_aggregate_stream: true` so the dashboard shows full output when the job completes and also streams partials to clients.

## Request Examples

### Non-streaming

```json
{
  "input": {
    "model": "Qwen2.5-7B-Instruct",
    "messages": [
      {"role": "user", "content": "Tell me a joke about databases."}
    ],
    "stream": false,
    "max_tokens": 256
  }
}
```

### Streaming

```json
{
  "input": {
    "model": "Qwen2.5-7B-Instruct",
    "messages": [
      {"role": "user", "content": "Write a haiku about servers."}
    ],
    "stream": true,
    "max_tokens": 128
  }
}
```

## Local smoke test

You can run the handler locally if you have an accessible SGLang server.

```sh
export SGLANG_BASE_URL=http://localhost:30000/v1
export SGLANG_MODEL=Qwen2.5-7B-Instruct
python -u handler.py
```

Then use the RunPod client or send JSON to your serverless endpoint when deployed.

## Notes

- The worker forwards OpenAI-style streaming chunks (data: {...} lines). The RunPod Python client `.stream()` can consume these.
- If you see empty streams in the dashboard, ensure your SGLang endpoint supports streaming and that `input.stream` is set to `true`.
