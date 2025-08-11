import os
import threading
import logging
import runpod

from sglang_client import SGLangChatClient, SGLangError


# Configure client from environment
client = SGLangChatClient(
    base_url=os.getenv("SGLANG_BASE_URL"),
    api_key=os.getenv("SGLANG_API_KEY"),
    request_timeout=float(os.getenv("SGLANG_TIMEOUT", "300")),
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("runpod-sglang-serverless")


def _warmup_background():
    """Optionally send a tiny request to SGLang to trigger model load on cold start."""
    try:
        if not os.getenv("WARMUP_ON_START"):
            return
        if not client.base_url:
            log.info("WARMUP_ON_START set but SGLANG_BASE_URL is missing; skipping warmup")
            return
        model = os.getenv("WARMUP_MODEL") or os.getenv("SGLANG_MODEL")
        prompt = os.getenv("WARMUP_PROMPT", "ping")
        max_tokens = int(os.getenv("WARMUP_MAX_TOKENS", "1"))
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": max_tokens,
        }
        if model:
            payload["model"] = model
        log.info("Starting warmup request to SGLang server...")
        # Fire-and-forget; errors are just logged
        try:
            _ = client.chat_completions(payload)
            log.info("Warmup completed")
        except Exception as e:
            log.warning("Warmup failed: %s", e)
    except Exception:
        # Never fail startup due to warmup
        pass


# Kick off warmup in a daemon thread
threading.Thread(target=_warmup_background, daemon=True).start()


def _normalize_input(job_input: dict) -> dict:
    """Create an OpenAI-compatible payload for /v1/chat/completions.

    Accepted fields are passed through; if only `prompt` is provided,
    it is converted to a single user message.
    """
    payload = {}
    allowed = [
        "model",
        "messages",
        "temperature",
        "top_p",
        "max_tokens",
        "stream",
        "stop",
    "stream_options",
        "presence_penalty",
        "frequency_penalty",
        "logit_bias",
        "user",
        "n",
        "tools",
        "tool_choice",
        "response_format",
        "seed",
    # SGLang extension for OpenAI API
    "extra_body",
    ]
    for k in allowed:
        if k in job_input:
            payload[k] = job_input[k]

    # Convenience: support `prompt` if `messages` not provided
    if "messages" not in payload and isinstance(job_input.get("prompt"), str):
        payload["messages"] = [{"role": "user", "content": job_input["prompt"]}]

    # Default model from env if not provided
    if "model" not in payload and os.getenv("SGLANG_MODEL"):
        payload["model"] = os.getenv("SGLANG_MODEL")

    return payload


def _streaming(job):
    job_input = job.get("input", {}) or {}
    payload = _normalize_input(job_input)

    if not client.base_url:
        yield {"error": "Missing SGLANG_BASE_URL env var"}
        return
    if not payload.get("messages"):
        yield {"error": "Missing 'messages' or 'prompt' in input"}
        return

    # Ensure backend streams so we can relay chunks
    payload["stream"] = True

    # Optional initial status for clients
    yield {"status": "started"}

    try:
        for chunk in client.stream_chat_completions(payload):
            # chunk is OpenAI-style SSE JSON; forward as-is
            yield chunk
        yield {"status": "completed"}
    except SGLangError as e:
        yield {"error": str(e), "type": "SGLANG_ERROR"}
    except Exception as e:
        # Avoid leaking internals; return message only
        yield {"error": str(e), "type": "UNKNOWN"}


def _non_streaming(job):
    job_input = job.get("input", {}) or {}
    payload = _normalize_input(job_input)

    if not client.base_url:
        return {"error": "Missing SGLANG_BASE_URL env var"}
    if not payload.get("messages"):
        return {"error": "Missing 'messages' or 'prompt' in input"}

    # Force non-stream on backend
    payload["stream"] = False

    try:
        result = client.chat_completions(payload)
        # result should already be OpenAI-compatible JSON
        return result
    except SGLangError as e:
        return {"error": str(e), "type": "SGLANG_ERROR"}
    except Exception as e:
        return {"error": str(e), "type": "UNKNOWN"}


def handler(job):
    """RunPod entrypoint. If input.stream is true, yields streaming chunks; otherwise returns a single JSON."""
    job_input = job.get("input", {}) or {}
    if bool(job_input.get("stream", False)):
        for item in _streaming(job):
            yield item
    else:
        return _non_streaming(job)


if __name__ == "__main__":
    runpod.serverless.start({
        "handler": handler,
        # Aggregate stream into final output for sync clients; live stream still delivered incrementally
        "return_aggregate_stream": True,
    })
