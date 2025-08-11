import json
import time
from typing import Dict, Generator, Optional

import requests


class SGLangError(RuntimeError):
    pass


class SGLangChatClient:
    """Tiny client for SGLang's OpenAI-compatible endpoints.

    Expects base_url like: http://host:port/v1
    """

    def __init__(
        self,
        base_url: Optional[str],
        api_key: Optional[str] = None,
        request_timeout: float = 300.0,
        retry: int = 2,
        backoff: float = 1.5,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key
        self.timeout = request_timeout
        self.retry = retry
        self.backoff = backoff

    # --- HTTP helpers
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # --- Non-streaming
    def chat_completions(self, payload: Dict) -> Dict:
        if not self.base_url:
            raise SGLangError("SGLANG_BASE_URL not configured")
        url = f"{self.base_url}/chat/completions" if self.base_url.endswith("/v1") else f"{self.base_url}/v1/chat/completions"
        body = json.dumps(payload)

        last_exc: Optional[Exception] = None
        for attempt in range(self.retry + 1):
            try:
                resp = requests.post(url, data=body, headers=self._headers(), timeout=self.timeout)
                if resp.status_code >= 400:
                    raise SGLangError(f"HTTP {resp.status_code}: {resp.text}")
                return resp.json()
            except Exception as e:  # network or parse
                last_exc = e
                if attempt < self.retry:
                    time.sleep(self.backoff ** attempt)
                    continue
                raise SGLangError(str(last_exc))

    # --- Streaming (SSE-like)
    def stream_chat_completions(self, payload: Dict) -> Generator[Dict, None, None]:
        if not self.base_url:
            raise SGLangError("SGLANG_BASE_URL not configured")
        url = f"{self.base_url}/chat/completions" if self.base_url.endswith("/v1") else f"{self.base_url}/v1/chat/completions"
        body = json.dumps(payload)

        last_exc: Optional[Exception] = None
        for attempt in range(self.retry + 1):
            try:
                with requests.post(
                    url,
                    data=body,
                    headers={**self._headers(), "Accept": "text/event-stream"},
                    timeout=self.timeout,
                    stream=True,
                ) as resp:
                    if resp.status_code >= 400:
                        raise SGLangError(f"HTTP {resp.status_code}: {resp.text}")
                    for line in resp.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        # OpenAI-compatible streams typically use 'data: {...}' lines
                        if line.startswith("data: "):
                            data = line[len("data: ") :].strip()
                        else:
                            data = line.strip()
                        if data == "[DONE]":
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            # Occasionally servers may send keepalives or partials; ignore
                            continue
                return
            except Exception as e:
                last_exc = e
                if attempt < self.retry:
                    time.sleep(self.backoff ** attempt)
                    continue
                raise SGLangError(str(last_exc))
