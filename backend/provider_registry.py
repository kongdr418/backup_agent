from __future__ import annotations

import os

# ==================== 模型 Provider 注册表 ====================

PROVIDERS = {
    'minimax': {
        'id': 'minimax',
        'name': 'MiniMax',
        'type': 'minimax',
        'defaultBaseUrl': 'https://api.minimaxi.com/v1',
        'models': [
            {'id': 'MiniMax-M3', 'name': 'MiniMax M3 (多模态)', 'contextWindow': 262144, 'maxOutput': 16384},
            {'id': 'MiniMax-M2.7', 'name': 'MiniMax M2.7', 'contextWindow': 131072, 'maxOutput': 8192},
            {'id': 'MiniMax-M2.5', 'name': 'MiniMax M2.5', 'contextWindow': 131072, 'maxOutput': 8192},
            {'id': 'MiniMax-M2.5-highspeed', 'name': 'MiniMax M2.5 高速', 'contextWindow': 16384, 'maxOutput': 4096},
        ],
        'requiresApiKey': True,
        'supportsReasoning': True,
    },
    'deepseek': {
        'id': 'deepseek',
        'name': 'DeepSeek',
        'type': 'openai',
        'defaultBaseUrl': 'https://api.deepseek.com',
        'models': [
            {'id': 'deepseek-v4-pro', 'name': 'DeepSeek V4 Pro', 'contextWindow': 1048576, 'maxOutput': 384000},
            {'id': 'deepseek-v4-flash', 'name': 'DeepSeek V4 Flash', 'contextWindow': 1048576, 'maxOutput': 384000},
        ],
        'requiresApiKey': True,
    },
    'openai': {
        'id': 'openai',
        'name': 'OpenAI',
        'type': 'openai',
        'defaultBaseUrl': 'https://api.openai.com/v1',
        'models': [
            {'id': 'gpt-5.4-mini', 'name': 'GPT-5.4 Mini', 'contextWindow': 400000, 'maxOutput': 16384},
            {'id': 'gpt-5.4', 'name': 'GPT-5.4', 'contextWindow': 1050000, 'maxOutput': 32768},
            {'id': 'gpt-5.4-nano', 'name': 'GPT-5.4 Nano', 'contextWindow': 400000, 'maxOutput': 16384},
            {'id': 'o3', 'name': 'o3', 'contextWindow': 200000, 'maxOutput': 100000},
            {'id': 'o4-mini', 'name': 'o4 Mini', 'contextWindow': 200000, 'maxOutput': 100000},
            {'id': 'gpt-4o', 'name': 'GPT-4o', 'contextWindow': 128000, 'maxOutput': 16384},
            {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini', 'contextWindow': 128000, 'maxOutput': 16384},
        ],
        'requiresApiKey': True,
    },
    'moonshot': {
        'id': 'moonshot',
        'name': 'Moonshot (Kimi)',
        'type': 'openai',
        'defaultBaseUrl': 'https://api.moonshot.cn/v1',
        'models': [
            {'id': 'kimi-k2.6', 'name': 'Kimi K2.6', 'contextWindow': 262144, 'maxOutput': 8192},
            {'id': 'kimi-k2-thinking', 'name': 'Kimi K2 Thinking', 'contextWindow': 131072, 'maxOutput': 8192},
            {'id': 'moonshot-v1-8k', 'name': 'Moonshot v1 8K', 'contextWindow': 8192, 'maxOutput': 4096},
            {'id': 'moonshot-v1-32k', 'name': 'Moonshot v1 32K', 'contextWindow': 32768, 'maxOutput': 4096},
            {'id': 'moonshot-v1-128k', 'name': 'Moonshot v1 128K', 'contextWindow': 131072, 'maxOutput': 4096},
        ],
        'requiresApiKey': True,
    },
    'zhipu': {
        'id': 'zhipu',
        'name': '智谱 GLM',
        'type': 'anthropic',
        'defaultBaseUrl': 'https://open.bigmodel.cn/api/anthropic',
        'models': [
            {'id': 'glm-5.1', 'name': 'GLM-5.1', 'contextWindow': 131072, 'maxOutput': 8192},
            {'id': 'glm-4.5', 'name': 'GLM-4.5', 'contextWindow': 131072, 'maxOutput': 8192},
            {'id': 'glm-4.5-air', 'name': 'GLM-4.5 Air', 'contextWindow': 131072, 'maxOutput': 8192},
            {'id': 'glm-4.5-flash', 'name': 'GLM-4.5 Flash', 'contextWindow': 131072, 'maxOutput': 4096},
            {'id': 'glm-4-plus', 'name': 'GLM-4 Plus', 'contextWindow': 131072, 'maxOutput': 4096},
        ],
        'requiresApiKey': True,
    },
    'qwen': {
        'id': 'qwen',
        'name': '通义千问',
        'type': 'openai',
        'defaultBaseUrl': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'models': [
            {'id': 'qwen3.6-max-preview', 'name': 'Qwen3.6 Max Preview', 'contextWindow': 262144, 'maxOutput': 8192},
            {'id': 'qwen3.6-plus', 'name': 'Qwen3.6 Plus', 'contextWindow': 1048576, 'maxOutput': 8192},
            {'id': 'qwen3.6-flash', 'name': 'Qwen3.6 Flash', 'contextWindow': 1048576, 'maxOutput': 8192},
            {'id': 'qwen-max', 'name': 'Qwen Max', 'contextWindow': 32768, 'maxOutput': 8192},
            {'id': 'qwen-plus', 'name': 'Qwen Plus', 'contextWindow': 131072, 'maxOutput': 8192},
        ],
        'requiresApiKey': True,
    },
    'siliconflow': {
        'id': 'siliconflow',
        'name': 'SiliconFlow',
        'type': 'openai',
        'defaultBaseUrl': 'https://api.siliconflow.cn/v1',
        'models': [
            {'id': 'deepseek-ai/DeepSeek-V4-Flash', 'name': 'DeepSeek V4 Flash (SF)', 'contextWindow': 1048576, 'maxOutput': 384000},
            {'id': 'deepseek-ai/DeepSeek-V3.2', 'name': 'DeepSeek V3.2 (SF)', 'contextWindow': 65536, 'maxOutput': 8192},
            {'id': 'Qwen/Qwen3.6-35B-A3B', 'name': 'Qwen3.6 35B (SF)', 'contextWindow': 131072, 'maxOutput': 8192},
            {'id': 'Qwen/Qwen3.6-27B', 'name': 'Qwen3.6 27B (SF)', 'contextWindow': 131072, 'maxOutput': 8192},
            {'id': 'deepseek-ai/DeepSeek-R1', 'name': 'DeepSeek R1 (SF)', 'contextWindow': 65536, 'maxOutput': 8192},
        ],
        'requiresApiKey': True,
    },
    'mimo': {
        'id': 'mimo',
        'name': '小米 MiMo',
        'type': 'openai',
        'defaultBaseUrl': 'https://api.xiaomimimo.com/v1',
        'models': [
            {'id': 'mimo-v2.5-pro', 'name': 'MiMo V2.5 Pro', 'contextWindow': 1048576, 'maxOutput': 131072},
            {'id': 'mimo-v2.5', 'name': 'MiMo V2.5 Omni', 'contextWindow': 1048576, 'maxOutput': 131072},
        ],
        'requiresApiKey': True,
    },
    'xfyun': {
        'id': 'xfyun',
        'name': '科大讯飞星火 X2',
        'type': 'openai',
        'defaultBaseUrl': 'https://spark-api-open.xf-yun.com/x2/',
        'models': [
            {'id': 'spark-x', 'name': 'Spark X2', 'contextWindow': 65536, 'maxOutput': 131072},
        ],
        'requiresApiKey': True,
        'supportsReasoning': True,
    },
    'xfyun-v2': {
        'id': 'xfyun-v2',
        'name': '科大讯飞星火 v2',
        'type': 'openai',
        'defaultBaseUrl': 'https://spark-api-open.xf-yun.com/v2/',
        'models': [
            {'id': 'spark-x', 'name': 'Spark X1.5 / v2', 'contextWindow': 65536, 'maxOutput': 131072},
        ],
        'requiresApiKey': True,
        'supportsReasoning': True,
    },
}

# ==================== TTS Provider 注册表 ====================

TTS_PROVIDERS = {
    'mimo-tts': {
        'id': 'mimo-tts',
        'name': '小米 MiMo TTS',
        'type': 'mimo-tts',
        'defaultBaseUrl': 'https://api.xiaomimimo.com/v1',
        'models': [
            {'id': 'mimo-v2.5-tts', 'name': 'MiMo V2.5 TTS'},
        ],
        'voices': [
            {'id': 'mimo_default', 'name': '默认'},
            {'id': '冰糖', 'name': '冰糖'},
            {'id': '茉莉', 'name': '茉莉'},
            {'id': '苏打', 'name': '苏打'},
            {'id': '白桦', 'name': '白桦'},
            {'id': 'Mia', 'name': 'Mia'},
            {'id': 'Chloe', 'name': 'Chloe'},
            {'id': 'Milo', 'name': 'Milo'},
            {'id': 'Dean', 'name': 'Dean'},
        ],
        'requiresApiKey': True,
    },
    'openai-tts': {
        'id': 'openai-tts',
        'name': 'OpenAI TTS',
        'type': 'openai-tts',
        'defaultBaseUrl': 'https://api.openai.com/v1',
        'models': [
            {'id': 'gpt-4o-mini-tts', 'name': 'GPT-4o Mini TTS'},
            {'id': 'tts-1', 'name': 'TTS-1'},
            {'id': 'tts-1-hd', 'name': 'TTS-1 HD'},
        ],
        'voices': [
            {'id': 'alloy', 'name': 'Alloy'},
            {'id': 'ash', 'name': 'Ash'},
            {'id': 'coral', 'name': 'Coral'},
            {'id': 'echo', 'name': 'Echo'},
            {'id': 'fable', 'name': 'Fable'},
            {'id': 'nova', 'name': 'Nova'},
            {'id': 'onyx', 'name': 'Onyx'},
            {'id': 'sage', 'name': 'Sage'},
            {'id': 'shimmer', 'name': 'Shimmer'},
            {'id': 'verse', 'name': 'Verse'},
        ],
        'requiresApiKey': True,
    },
    'glm-tts': {
        'id': 'glm-tts',
        'name': '智谱 GLM TTS',
        'type': 'openai-tts',
        'defaultBaseUrl': 'https://open.bigmodel.cn/api/paas/v4',
        'models': [
            {'id': 'glm-tts', 'name': 'GLM TTS'},
        ],
        'voices': [
            {'id': 'tongtong', 'name': '彤彤'},
            {'id': 'chuichui', 'name': '锤锤'},
            {'id': 'xiaochen', 'name': '小陈'},
            {'id': 'jam', 'name': 'Jam'},
            {'id': 'kazi', 'name': 'Kazi'},
            {'id': 'douji', 'name': '豆几'},
            {'id': 'luodo', 'name': '罗多'},
        ],
        'requiresApiKey': True,
    },
    'edge-tts': {
        'id': 'edge-tts',
        'name': '微软 Edge TTS',
        'type': 'edge-tts',
        'defaultBaseUrl': '',
        'models': [
            {'id': '', 'name': 'Edge TTS'},
        ],
        'voices': [
            {'id': 'zh-CN-XiaoxiaoNeural', 'name': '晓晓 (女声)', 'lang': 'zh-CN'},
            {'id': 'zh-CN-XiaoyiNeural', 'name': '小艺 (女声)', 'lang': 'zh-CN'},
            {'id': 'zh-CN-YunxiNeural', 'name': '云希 (男声)', 'lang': 'zh-CN'},
            {'id': 'zh-CN-YunyangNeural', 'name': '云扬 (男声)', 'lang': 'zh-CN'},
            {'id': 'zh-CN-liaoning-XiaobeiNeural', 'name': '辽宁小贝', 'lang': 'zh-CN'},
            {'id': 'zh-CN-shaanxi-XiaoniNeural', 'name': '陕西小妮', 'lang': 'zh-CN'},
            {'id': 'zh-HK-HiuMaanNeural', 'name': '香港小文', 'lang': 'zh-HK'},
            {'id': 'zh-TW-HsiaoChenNeural', 'name': '台湾小珍', 'lang': 'zh-TW'},
            {'id': 'zh-TW-YunJheNeural', 'name': '台湾云哲', 'lang': 'zh-TW'},
            {'id': 'en-US-AriaNeural', 'name': 'Aria (美音)', 'lang': 'en'},
            {'id': 'en-US-GuyNeural', 'name': 'Guy (美音)', 'lang': 'en'},
            {'id': 'en-US-JennyNeural', 'name': 'Jenny (美音)', 'lang': 'en'},
            {'id': 'en-GB-SoniaNeural', 'name': 'Sonia (英音)', 'lang': 'en'},
            {'id': 'en-GB-RyanNeural', 'name': 'Ryan (英音)', 'lang': 'en'},
            {'id': 'en-AU-NatashaNeural', 'name': 'Natasha (澳音)', 'lang': 'en'},
            {'id': 'ja-JP-NanamiNeural', 'name': '七海 (日语)', 'lang': 'ja'},
            {'id': 'ko-KR-SunHiNeural', 'name': 'SunHi (韩语)', 'lang': 'ko'},
        ],
        'requiresApiKey': False,
    },
}

# 服务端已配置的 API Keys（来自环境变量）
SERVER_API_KEYS = {}
if os.environ.get('MINIMAX_API_KEY'):
    SERVER_API_KEYS['minimax'] = os.environ['MINIMAX_API_KEY']
if os.environ.get('DEEPSEEK_API_KEY'):
    SERVER_API_KEYS['deepseek'] = os.environ['DEEPSEEK_API_KEY']
if os.environ.get('MIMO_API_KEY'):
    SERVER_API_KEYS['mimo'] = os.environ['MIMO_API_KEY']
    SERVER_API_KEYS['mimo-tts'] = os.environ['MIMO_API_KEY']
if os.environ.get('ZHIPU_API_KEY'):
    SERVER_API_KEYS['glm-tts'] = os.environ['ZHIPU_API_KEY']
if os.environ.get('XFYUN_API_KEY'):
    SERVER_API_KEYS['xfyun'] = os.environ['XFYUN_API_KEY']
    SERVER_API_KEYS['xfyun-v2'] = os.environ['XFYUN_API_KEY']
elif os.environ.get('XFYUN_API_PASSWORD'):
    SERVER_API_KEYS['xfyun'] = os.environ['XFYUN_API_PASSWORD']
    SERVER_API_KEYS['xfyun-v2'] = os.environ['XFYUN_API_PASSWORD']


def _get_provider_for_model(model_id: str):
    """根据 model ID 查找所属 provider"""
    for pid, p in PROVIDERS.items():
        for m in p['models']:
            if m['id'] == model_id:
                return pid, p, m
    return None, None, None

# ==================== 设置 API ====================

DEFAULT_SETTINGS = {
    'mimo_voice': 'mimo_default',
    'mimo_style': '',
    'aspect_ratio': '3:4',
    'cover_style': 'infographic',
    'chat_model': 'MiniMax-M2.5-highspeed',
    'chat_provider': 'minimax',
    'content_model': 'deepseek-v4-flash',
    'content_provider': 'deepseek',
    'classroom_critic_mode': 'standard',
    'ppt_model': 'deepseek-v4-flash',
    'ppt_provider': 'deepseek',
    'tts_provider': 'mimo-tts',
    'tts_model': 'mimo-v2.5-tts',
    'tts_voice': 'mimo_default',
}
