"""
内容生成 LLM 配置共享模块
允许从设置中动态配置模型、API Key 和 Base URL，
避免每个生成器硬编码 DeepSeek。
"""
import os

_content_model: str = 'deepseek-chat'
_content_api_key: str | None = None
_content_base_url: str | None = None


def get_content_llm_config():
    """获取内容生成 LLM 配置，优先使用设置的值，否则回退到环境变量"""
    api_key = _content_api_key or os.environ.get('DEEPSEEK_API_KEY', '')
    base_url = _content_base_url or 'https://api.deepseek.com'
    return _content_model, api_key, base_url


def set_content_llm_config(model: str = '', api_key: str = '', base_url: str = ''):
    """从设置更新内容生成 LLM 配置"""
    global _content_model, _content_api_key, _content_base_url
    if model:
        _content_model = model
    if api_key:
        _content_api_key = api_key
    if base_url:
        _content_base_url = base_url
