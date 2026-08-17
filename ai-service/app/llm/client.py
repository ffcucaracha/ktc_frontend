from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import LLMSettings


class LLMClientError(Exception):
    pass


class OpenAICompatibleLLMClient:
    def __init__(self, settings: LLMSettings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    async def complete_json(self, *, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._settings.timeout_seconds)
        headers = {"Content-Type": "application/json"}
        if self._settings.api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"
        try:
            response = await client.post(
                f"{self._settings.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self._settings.model,
                    "temperature": self._settings.temperature,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                },
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise LLMClientError("LLM returned non-text content")
            return _parse_json_object(content)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LLMClientError("OpenAI-compatible LLM request failed") from exc
        finally:
            if owns_client:
                await client.aclose()


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise LLMClientError("LLM response must be a JSON object")
    return value
