"""Anthropic-compatible LLM provider using httpx."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import httpx
from pydantic import BaseModel

from ppt_engine.config import (
    LLM_CONNECT_TIMEOUT,
    LLM_READ_TIMEOUT,
    LLM_WRITE_TIMEOUT,
)

from .base import LLMProvider
from .retry import call_with_retry
from .types import (
    ContentBlock,
    LLMMessage,
    LLMResponse,
    LLMStreamChunk,
    ModelInfo,
    ProviderInfo,
    TokenUsage,
)


class AnthropicProvider(LLMProvider):
    """Provider for Anthropic-compatible APIs (e.g. Zhipu GLM)."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = "https://open.bigmodel.cn/api/anthropic",
        provider_name: str = "zhipu",
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or "https://open.bigmodel.cn/api/anthropic").rstrip("/")
        self._provider_name = provider_name
        self._timeout = httpx.Timeout(
            connect=LLM_CONNECT_TIMEOUT,
            read=LLM_READ_TIMEOUT,
            write=LLM_WRITE_TIMEOUT,
            pool=30.0,
        )

    def _convert_messages(self, messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        """Extract system prompt and convert messages to Anthropic format."""
        system = ""
        chat_msgs = []
        for msg in messages:
            if msg.role == "system":
                system = msg.content if isinstance(msg.content, str) else ""
            else:
                if isinstance(msg.content, str):
                    chat_msgs.append({"role": msg.role, "content": msg.content})
                else:
                    parts = []
                    for block in msg.content:
                        if block.type == "text" and block.text:
                            parts.append({"type": "text", "text": block.text})
                    chat_msgs.append({"role": msg.role, "content": parts})
        return system, chat_msgs

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: type[BaseModel] | None = None,
    ) -> LLMResponse:
        system, chat_msgs = self._convert_messages(messages)
        payload: dict = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "messages": chat_msgs,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system

        t0 = time.monotonic()
        data = await self._request(payload)
        duration_ms = int((time.monotonic() - t0) * 1000)

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        usage = None
        raw_usage = data.get("usage")
        if raw_usage:
            usage = TokenUsage(
                prompt_tokens=raw_usage.get("input_tokens", 0),
                completion_tokens=raw_usage.get("output_tokens", 0),
            )

        return LLMResponse(content=text, usage=usage, raw=data)

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        system, chat_msgs = self._convert_messages(messages)
        payload: dict = {
            "model": model,
            "max_tokens": max_tokens or 4096,
            "messages": chat_msgs,
            "temperature": temperature,
            "stream": True,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield LLMStreamChunk(delta=delta.get("text", ""))
                    except json.JSONDecodeError:
                        continue

    async def validate(self) -> bool:
        try:
            await self._request({
                "model": "glm-4.5-flash",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            })
            return True
        except Exception:
            return False

    async def _request(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text}")
            return resp.json()

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="anthropic",
            display_name="Anthropic Compatible",
            default_base_url="https://open.bigmodel.cn/api/anthropic",
            models=[
                ModelInfo(
                    id="glm-5.1",
                    display_name="GLM-5.1",
                    supports_vision=False,
                    supports_structured_output=False,
                    context_window=131072,
                ),
            ],
        )
