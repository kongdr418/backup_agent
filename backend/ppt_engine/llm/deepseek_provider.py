"""DeepSeek / OpenAI-compatible LLM provider using the openai SDK."""

from __future__ import annotations

import base64
import time
from collections.abc import AsyncIterator

from httpx import Timeout
from openai import AsyncOpenAI
from pydantic import BaseModel

from ppt_engine.config import (
    LLM_CONNECT_TIMEOUT,
    LLM_POOL_TIMEOUT,
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


def normalize_openai_base_url(base_url: str | None) -> str | None:
    """Return an SDK base URL from a user-entered OpenAI-compatible URL."""
    if not base_url:
        return None
    normalized = base_url.strip().rstrip("/")
    suffix = "/chat/completions"
    if normalized.lower().endswith(suffix):
        normalized = normalized[: -len(suffix)].rstrip("/")
    return normalized or None


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider wrapping AsyncOpenAI (OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = "https://api.deepseek.com",
        provider_name: str = "deepseek",
        deepseek_settings: dict | None = None,
    ) -> None:
        normalized_base_url = normalize_openai_base_url(base_url)
        timeout = Timeout(
            connect=LLM_CONNECT_TIMEOUT,
            read=LLM_READ_TIMEOUT,
            write=LLM_WRITE_TIMEOUT,
            pool=LLM_POOL_TIMEOUT,
        )
        # max_retries=0 — use our own call_with_retry instead of SDK retries
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=normalized_base_url,
            timeout=timeout,
            max_retries=0,
        )
        self._provider_name = provider_name
        self._base_url = (normalized_base_url or "").rstrip("/")
        self._deepseek_settings = deepseek_settings

    def _is_deepseek_request(self, model: str | None = None) -> bool:
        return (
            self._provider_name == "deepseek"
            or "api.deepseek.com" in self._base_url
            or (model or "").startswith("deepseek")
        )

    def _apply_deepseek_thinking_kwargs(self, kwargs: dict, model: str) -> None:
        settings = self._deepseek_settings
        if settings is None:
            if model != "deepseek-v4-pro":
                return
            thinking_enabled = True
            reasoning_effort = "max"
        else:
            thinking_enabled = bool(settings.get("thinking_enabled", True))
            reasoning_effort = str(settings.get("reasoning_effort") or "max")
            if reasoning_effort not in {"high", "max"}:
                reasoning_effort = "max"

        kwargs["extra_body"] = {
            "thinking": {"type": "enabled" if thinking_enabled else "disabled"}
        }
        if thinking_enabled:
            kwargs["reasoning_effort"] = reasoning_effort
            kwargs.pop("temperature", None)

    def _build_chat_kwargs(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float,
        max_tokens: int | None,
        stream: bool = False,
    ) -> dict:
        is_deepseek = self._is_deepseek_request(model)
        kwargs: dict = {
            "model": model,
            "messages": self._convert_messages(messages),
        }
        kwargs["temperature"] = temperature
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if is_deepseek:
            self._apply_deepseek_thinking_kwargs(kwargs, model)
        if stream:
            kwargs["stream"] = True
        return kwargs

    def _fallback_chat_kwargs(self, kwargs: dict) -> list[dict]:
        fallbacks: list[dict] = []
        without_extras = dict(kwargs)
        removed = False
        for key in ("reasoning_effort", "extra_body"):
            if key in without_extras:
                without_extras.pop(key, None)
                removed = True
        if removed:
            fallbacks.append(without_extras)
        return fallbacks

    def _is_parameter_compat_error(self, exc: BaseException) -> bool:
        if isinstance(exc, TypeError):
            return True
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        response = getattr(exc, "response", None)
        if response is not None:
            status = status or getattr(response, "status_code", None)
        if status != 400:
            return False
        text = str(exc).lower()
        return any(
            marker in text
            for marker in (
                "max_tokens",
                "reasoning_effort",
                "unsupported",
                "unrecognized",
                "unknown parameter",
                "unexpected keyword",
            )
        )

    async def _create_chat_completion(self, kwargs: dict):
        try:
            return await call_with_retry(
                lambda: self._client.chat.completions.create(**kwargs)
            )
        except BaseException as exc:
            fallbacks = self._fallback_chat_kwargs(kwargs)
            if not fallbacks or not self._is_parameter_compat_error(exc):
                raise
            for index, fallback in enumerate(fallbacks):
                try:
                    return await call_with_retry(
                        lambda: self._client.chat.completions.create(**fallback)
                    )
                except BaseException as fallback_exc:
                    if index >= len(fallbacks) - 1 or not self._is_parameter_compat_error(fallback_exc):
                        raise
            raise

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict]:
        result = []
        for msg in messages:
            if isinstance(msg.content, str):
                result.append({"role": msg.role, "content": msg.content})
            else:
                parts = []
                for block in msg.content:
                    if block.type == "text" and block.text:
                        parts.append({"type": "text", "text": block.text})
                    elif block.type == "image" and block.image_data:
                        b64 = base64.b64encode(block.image_data).decode()
                        media = block.image_media_type or "image/png"
                        parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media};base64,{b64}",
                            },
                        })
                result.append({"role": msg.role, "content": parts})
        return result

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: type[BaseModel] | None = None,
    ) -> LLMResponse:
        kwargs = self._build_chat_kwargs(
            messages, model, temperature=temperature, max_tokens=max_tokens
        )
        t0 = time.monotonic()
        resp = await self._create_chat_completion(kwargs)
        duration_ms = int((time.monotonic() - t0) * 1000)

        content = resp.choices[0].message.content or ""
        usage = None
        if resp.usage:
            usage = TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
            )
        return LLMResponse(content=content, usage=usage, raw=resp)

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        kwargs = self._build_chat_kwargs(
            messages, model, temperature=temperature, max_tokens=max_tokens, stream=True
        )
        try:
            stream = await self._client.chat.completions.create(**kwargs)
        except BaseException as exc:
            fallbacks = self._fallback_chat_kwargs(kwargs)
            if not fallbacks or not self._is_parameter_compat_error(exc):
                raise
            for index, fallback in enumerate(fallbacks):
                try:
                    stream = await self._client.chat.completions.create(**fallback)
                    break
                except BaseException as fallback_exc:
                    if index >= len(fallbacks) - 1 or not self._is_parameter_compat_error(fallback_exc):
                        raise
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield LLMStreamChunk(
                    delta=delta.content,
                    finish_reason=chunk.choices[0].finish_reason,
                )

    async def validate(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="deepseek",
            display_name="DeepSeek",
            default_base_url="https://api.deepseek.com",
            models=[
                ModelInfo(
                    id="deepseek-v4-flash",
                    display_name="DeepSeek V4 Flash",
                    supports_vision=True,
                    supports_structured_output=True,
                    context_window=128000,
                ),
                ModelInfo(
                    id="deepseek-v4-pro",
                    display_name="DeepSeek V4 Pro",
                    supports_vision=True,
                    supports_structured_output=True,
                    context_window=128000,
                ),
            ],
        )
