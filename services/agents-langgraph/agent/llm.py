import logging
from typing import Protocol

import httpx

from agent.config import Settings

log = logging.getLogger(__name__)

DEFAULTS = {
    "ollama": ("http://localhost:11434", "llama3.2"),
    "anthropic": ("https://api.anthropic.com", "claude-haiku-4-5"),
    "openai": ("https://api.openai.com", "gpt-4o-mini"),
}


class Explainer(Protocol):
    async def explain(self, prompt: str) -> str | None: ...


class NoExplainer:
    async def explain(self, prompt: str) -> str | None:
        return None


class HttpExplainer:
    """Writes a short explanation of a decision already taken by the rules; never decides."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        default_url, default_model = DEFAULTS[settings.llm_provider]
        self._provider = settings.llm_provider
        self._model = settings.llm_model or default_model
        self._client = httpx.AsyncClient(
            base_url=settings.llm_base_url or default_url,
            timeout=settings.llm_timeout_seconds,
            transport=transport,
        )
        self._api_key = settings.llm_api_key

    async def explain(self, prompt: str) -> str | None:
        try:
            response = await self._post(prompt)
            response.raise_for_status()
            return self._extract(response.json()).strip() or None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            log.warning("llm explanation unavailable: %s", exc)
            return None

    async def _post(self, prompt: str) -> httpx.Response:
        if self._provider == "ollama":
            body = {"model": self._model, "prompt": prompt, "stream": False}
            return await self._client.post("/api/generate", json=body)
        messages = [{"role": "user", "content": prompt}]
        if self._provider == "anthropic":
            headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01"}
            body = {"model": self._model, "max_tokens": 300, "messages": messages}
            return await self._client.post("/v1/messages", json=body, headers=headers)
        headers = {"authorization": f"Bearer {self._api_key}"}
        body = {"model": self._model, "messages": messages}
        return await self._client.post("/v1/chat/completions", json=body, headers=headers)

    def _extract(self, data: dict) -> str:
        if self._provider == "ollama":
            return data["response"]
        if self._provider == "anthropic":
            return data["content"][0]["text"]
        return data["choices"][0]["message"]["content"]


def build_explainer(settings: Settings) -> Explainer:
    if settings.llm_provider == "none":
        return NoExplainer()
    return HttpExplainer(settings)
