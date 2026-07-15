"""
内容生成 LLM 配置共享模块
允许从设置中动态配置模型、API Key 和 Base URL，
避免每个生成器硬编码 DeepSeek。
"""
import os
import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator

import requests as req

logger = logging.getLogger(__name__)

_content_model: str = 'deepseek-chat'
_content_api_key: str | None = None
_content_base_url: str | None = None
_content_provider_type: str = 'openai'
_scoped_content_config: ContextVar[dict | None] = ContextVar('scoped_content_config', default=None)


def get_content_llm_config():
    """获取内容生成 LLM 配置，优先使用设置的值，否则回退到环境变量"""
    scoped = _scoped_content_config.get() or {}
    model = scoped.get('model') or _content_model
    api_key = scoped.get('api_key') or _content_api_key
    if not api_key:
        try:
            from app import SERVER_API_KEYS, _get_provider_for_model
            pid, _, _ = _get_provider_for_model(model)
            if pid and pid in SERVER_API_KEYS:
                api_key = SERVER_API_KEYS[pid]
        except ImportError:
            pass
    if not api_key:
        api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    base_url = scoped.get('base_url') or _content_base_url or 'https://api.deepseek.com'
    return model, api_key, base_url


def get_content_provider_type():
    """获取内容生成 provider 类型"""
    scoped = _scoped_content_config.get() or {}
    return scoped.get('provider_type') or _content_provider_type


@contextmanager
def content_llm_config_scope(*, model: str = '', api_key: str = '', base_url: str = '', provider_type: str = ''):
    """隔离单次请求或后台任务的内容模型配置，避免并发请求互相覆盖。"""
    token = _scoped_content_config.set({
        'model': model, 'api_key': api_key, 'base_url': base_url, 'provider_type': provider_type,
    })
    try:
        yield
    finally:
        _scoped_content_config.reset(token)


def set_content_llm_config(model: str = '', api_key: str = '', base_url: str = '', provider_type: str = ''):
    """从设置更新内容生成 LLM 配置"""
    global _content_model, _content_api_key, _content_base_url, _content_provider_type
    if model:
        _content_model = model
    if api_key:
        _content_api_key = api_key
    if base_url:
        _content_base_url = base_url
    if provider_type:
        _content_provider_type = provider_type


def content_llm_call(
    messages: list,
    model: str = '',
    temperature: float = 0.7,
    max_tokens: int = 4000,
    api_key: str = '',
    base_url: str = '',
    provider_type: str = '',
) -> str:
    """统一的 LLM 调用，根据 provider_type 自动选择 OpenAI 或 Anthropic 兼容接口。

    支持按调用覆盖 model/api_key/base_url/provider_type（来自前端请求体），
    未传时回退到模块全局/环境变量。
    """
    from openai import OpenAI

    cfg_model, cfg_api_key, cfg_base_url = get_content_llm_config()
    model = model or cfg_model
    api_key = api_key or cfg_api_key
    base_url = base_url or cfg_base_url
    ptype = provider_type or get_content_provider_type()

    if ptype == 'anthropic':
        return _anthropic_call(base_url, api_key, model, messages, temperature, max_tokens)
    else:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=120)
        has_system = any(m.get('role') == 'system' for m in messages)
        if not has_system:
            messages = [{"role": "system", "content": "你是智创空间智慧课堂的学习内容生成智能体，面向学生输出严谨、清晰、可学习的资料。"}] + messages
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=120,
        )
        choice = response.choices[0] if response.choices else None
        content = choice.message.content if (choice and choice.message) else None
        if not content:
            finish_reason = getattr(choice, "finish_reason", None) if choice else None
            usage = getattr(response, "usage", None)
            prompt_chars = sum(len(str(m.get("content", ""))) for m in messages)
            logger.warning(
                "[content_llm_call] LLM returned empty content: model=%s "
                "finish_reason=%s prompt_chars=%s usage=%s",
                model,
                finish_reason,
                prompt_chars,
                usage,
            )
        return content or ''


def _anthropic_call(base_url: str, api_key: str, model: str, messages: list,
                    temperature: float, max_tokens: int) -> str:
    """Anthropic 兼容 API 调用"""
    system_content = ''
    chat_messages = []
    for m in messages:
        if m.get('role') == 'system':
            system_content = m.get('content', '')
        else:
            chat_messages.append(m)

    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'messages': chat_messages,
        'temperature': temperature,
    }
    if system_content:
        payload['system'] = system_content

    resp = req.post(
        f"{base_url}/v1/messages",
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    text = ''
    for block in data.get('content', []):
        if block.get('type') == 'text':
            text += block.get('text', '')
    return text


def content_llm_call_stream(
    messages: list,
    model: str = '',
    temperature: float = 0.7,
    max_tokens: int = 4000,
    api_key: str = '',
    base_url: str = '',
    provider_type: str = '',
) -> Iterator[str]:
    """流式 LLM 调用，逐 chunk yield 文本片段（兼容 OpenAI / Anthropic 协议）。"""
    from openai import OpenAI

    cfg_model, cfg_api_key, cfg_base_url = get_content_llm_config()
    model = model or cfg_model
    api_key = api_key or cfg_api_key
    base_url = base_url or cfg_base_url
    ptype = provider_type or get_content_provider_type()

    if ptype == 'anthropic':
        yield from _anthropic_call_stream(
            base_url, api_key, model, messages, temperature, max_tokens
        )
        return

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120)
    has_system = any(m.get('role') == 'system' for m in messages)
    if not has_system:
        messages = [{"role": "system", "content": "你是智创空间智慧课堂的学习内容生成智能体，面向学生输出严谨、清晰、可学习的资料。"}] + messages
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=120,
        stream=True,
    )
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


def _anthropic_call_stream(
    base_url: str, api_key: str, model: str, messages: list,
    temperature: float, max_tokens: int,
) -> Iterator[str]:
    """Anthropic 兼容 API 流式调用。"""
    system_content = ''
    chat_messages = []
    for m in messages:
        if m.get('role') == 'system':
            system_content = m.get('content', '')
        else:
            chat_messages.append(m)

    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'messages': chat_messages,
        'temperature': temperature,
        'stream': True,
    }
    if system_content:
        payload['system'] = system_content

    with req.post(
        f"{base_url}/v1/messages",
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json=payload,
        timeout=120,
        stream=True,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line or not line.startswith(b'data: '):
                continue
            data = line[6:].decode('utf-8')
            if data == '[DONE]':
                break
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if event.get('type') == 'content_block_delta':
                delta = event.get('delta', {})
                if delta.get('type') == 'text_delta':
                    text = delta.get('text', '')
                    if text:
                        yield text
