"""
内容生成 LLM 配置共享模块
允许从设置中动态配置模型、API Key 和 Base URL，
避免每个生成器硬编码 DeepSeek。
"""
import os
import json
import requests as req

_content_model: str = 'deepseek-chat'
_content_api_key: str | None = None
_content_base_url: str | None = None
_content_provider_type: str = 'openai'


def get_content_llm_config():
    """获取内容生成 LLM 配置，优先使用设置的值，否则回退到环境变量"""
    api_key = _content_api_key or os.environ.get('DEEPSEEK_API_KEY', '')
    base_url = _content_base_url or 'https://api.deepseek.com'
    return _content_model, api_key, base_url


def get_content_provider_type():
    """获取内容生成 provider 类型"""
    return _content_provider_type


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


def content_llm_call(messages: list, model: str = '', temperature: float = 0.7, max_tokens: int = 4000) -> str:
    """统一的 LLM 调用，根据 provider_type 自动选择 OpenAI 或 Anthropic 兼容接口"""
    from openai import OpenAI

    cfg_model, cfg_api_key, cfg_base_url = get_content_llm_config()
    model = model or cfg_model
    ptype = get_content_provider_type()

    if ptype == 'anthropic':
        return _anthropic_call(cfg_base_url, cfg_api_key, model, messages, temperature, max_tokens)
    else:
        client = OpenAI(api_key=cfg_api_key, base_url=cfg_base_url, timeout=120)
        has_system = any(m.get('role') == 'system' for m in messages)
        if not has_system:
            messages = [{"role": "system", "content": "你是一个专业的AI教师助手。"}] + messages
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ''


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
