"""
MiniMax Agent Web 应用
Flask 后端服务
"""

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
from minimax_agent import MiniMaxAgent
from memory_manager import MemoryManager
from video_generator import VideoGenerator
import json
import os
import shutil
import logging
import sys
import threading
from datetime import datetime

# ==================== 日志配置 ====================
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 配置根日志记录器
logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 创建 Flask 应用日志记录器
app_logger = logging.getLogger('MiniMaxAgent.app')
app_logger.setLevel(logging.DEBUG)

# 创建 API 日志记录器
api_logger = logging.getLogger('MiniMaxAgent.api')
api_logger.setLevel(logging.DEBUG)

# 请求日志记录器
request_logger = logging.getLogger('MiniMaxAgent.request')
request_logger.setLevel(logging.DEBUG)

# ==================== 全局记忆管理器 ====================
_memory_manager = None

def get_memory_manager():
    """获取全局记忆管理器实例"""
    global _memory_manager
    if _memory_manager is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        _memory_manager = MemoryManager(base_dir)
    return _memory_manager

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATORS_DIR = os.path.join(BACKEND_DIR, "generators")

# 视频生成任务追踪（内存字典，job_id → 状态）
video_jobs = {}

app = Flask(__name__)
CORS(app)

app_logger.info('=' * 60)
app_logger.info('MiniMax Agent Web 应用启动中...')
app_logger.info('=' * 60)

# API 密钥 - 从环境变量读取
API_KEY = os.environ.get('MINIMAX_API_KEY', '')

# 存储用户会话（简单实现，生产环境应使用 Redis 等）
sessions = {}


def get_agent(session_id: str, model: str = None) -> MiniMaxAgent:
    """获取或创建 Agent 实例"""
    if session_id not in sessions:
        agent = MiniMaxAgent(API_KEY, session_id, model=model)
        sessions[session_id] = agent
    elif model and sessions[session_id].model != model:
        # 模型变更时更新 agent 的模型
        sessions[session_id].model = model
    return sessions[session_id]


def _apply_content_llm_config(data: dict):
    """将请求中的内容生成模型配置同步到 shared_config，使讲稿/大纲/习题等生成器使用正确模型"""
    content_model = data.get('content_model', '')
    content_api_key = data.get('content_api_key', '')
    content_base_url = data.get('content_base_url', '')
    if content_model or content_api_key or content_base_url:
        try:
            from generators.shared_config import set_content_llm_config
            set_content_llm_config(model=content_model, api_key=content_api_key, base_url=content_base_url)
        except Exception:
            pass


# ==================== 健康检查 & API 信息 ====================

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'service': 'MiniMax Agent API',
        'version': '1.0.0',
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route('/api/info', methods=['GET'])
def api_info():
    """API 信息接口"""
    return jsonify({
        'name': 'MiniMax Agent API',
        'version': '1.0.0',
        'description': 'AI 教师助手后端服务',
        'endpoints': [
            {'path': '/api/health', 'method': 'GET', 'description': '健康检查'},
            {'path': '/api/info', 'method': 'GET', 'description': 'API 信息'},
            {'path': '/api/chat', 'method': 'POST', 'description': '非流式聊天'},
            {'path': '/api/chat/stream', 'method': 'POST', 'description': '流式聊天（SSE）'},
            {'path': '/api/clear', 'method': 'POST', 'description': '清空对话历史'},
            {'path': '/api/history', 'method': 'GET', 'description': '获取对话历史'},
            {'path': '/api/models', 'method': 'GET', 'description': '可用模型列表'},
            {'path': '/api/settings', 'method': 'GET/POST', 'description': '设置读写'},
            {'path': '/api/files', 'method': 'GET', 'description': '文件列表'},
            {'path': '/api/files/delete', 'method': 'POST', 'description': '删除文件'},
            {'path': '/api/files/rename', 'method': 'POST', 'description': '重命名文件'},
            {'path': '/api/files/clear', 'method': 'POST', 'description': '清空所有文件'},
            {'path': '/api/memory', 'method': 'GET', 'description': '记忆摘要'},
            {'path': '/api/memory/save', 'method': 'POST', 'description': '保存记忆'},
            {'path': '/api/memory/clear', 'method': 'POST', 'description': '清除长期记忆'},
            {'path': '/api/memory/clear-daily', 'method': 'POST', 'description': '清除会话记录'},
            {'path': '/api/memory/search', 'method': 'GET', 'description': '搜索记忆'},
            {'path': '/api/ppt-preview/<filename>', 'method': 'GET', 'description': 'PPT 预览图'},
            {'path': '/api/graphic/image/<filename>', 'method': 'GET', 'description': '封面图'},
            {'path': '/api/video/audio/<filename>', 'method': 'GET', 'description': '音频文件'},
        ]
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """非流式聊天接口"""
    request_logger.info('=' * 50)
    request_logger.info('[CHAT] 收到非流式聊天请求')
    request_logger.info(f'[CHAT] 请求数据: {request.json}')

    data = request.json
    message = data.get('message', '').strip()
    session_id = data.get('session_id', 'default')
    model = data.get('model', DEFAULT_SETTINGS.get('chat_model', 'MiniMax-M2.5-highspeed'))
    api_key = data.get('api_key', '')
    base_url = data.get('base_url', '')
    provider_type = data.get('provider_type', '')

    # 内容生成模型配置（用于讲稿、大纲、习题等生成器）
    _apply_content_llm_config(data)

    request_logger.info(f'[CHAT] session_id: {session_id}')
    request_logger.info(f'[CHAT] model: {model}')
    request_logger.info(f'[CHAT] has_client_api_key: {bool(api_key)}')
    request_logger.info(f'[CHAT] message: {message[:100]}...' if len(message) > 100 else f'[CHAT] message: {message}')

    if not message:
        request_logger.warning('[CHAT] 消息为空，返回 400')
        return jsonify({'error': '消息不能为空'}), 400

    request_logger.info('[CHAT] 获取 Agent 实例')
    agent = get_agent(session_id, model=model)

    request_logger.info('[CHAT] 调用 agent.chat() - stream=False')
    response = agent.chat(message, stream=False, model=model, api_key=api_key, base_url=base_url, provider_type=provider_type)
    request_logger.info(f'[CHAT] agent.chat() 返回，响应长度: {len(str(response))}')

    history = agent.get_history()
    request_logger.info(f'[CHAT] 当前对话历史长度: {len(history)}')

    request_logger.info('[CHAT] 返回响应')
    return jsonify({
        'response': response,
        'history': agent.get_history()
    })


@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """流式聊天接口"""
    request_logger.info('=' * 50)
    request_logger.info('[STREAM] 收到流式聊天请求')
    request_logger.info(f'[STREAM] 请求数据: {request.json}')

    data = request.json
    message = data.get('message', '').strip()
    session_id = data.get('session_id', 'default')
    model = data.get('model', DEFAULT_SETTINGS.get('chat_model', 'MiniMax-M2.5-highspeed'))
    api_key = data.get('api_key', '')
    base_url = data.get('base_url', '')
    provider_type = data.get('provider_type', '')

    # 内容生成模型配置（用于讲稿、大纲、习题等生成器）
    _apply_content_llm_config(data)

    request_logger.info(f'[STREAM] session_id: {session_id}')
    request_logger.info(f'[STREAM] model: {model}')
    request_logger.info(f'[STREAM] has_client_api_key: {bool(api_key)}')
    request_logger.info(f'[STREAM] message: {message[:100]}...' if len(message) > 100 else f'[STREAM] message: {message}')

    if not message:
        request_logger.warning('[STREAM] 消息为空，返回 400')
        return jsonify({'error': '消息不能为空'}), 400

    request_logger.info('[STREAM] 获取 Agent 实例')
    agent = get_agent(session_id, model=model)

    def generate():
        request_logger.info('[STREAM] 调用 agent.chat() - stream=True')
        result = agent.chat(message, stream=True, model=model, api_key=api_key, base_url=base_url, provider_type=provider_type)

        # 优先检查是否是 PPT 预览数据字典（注意：字典也有 __iter__，必须先检查）
        if isinstance(result, dict) and result.get('type') == 'ppt_preview':
            request_logger.info('[STREAM] 检测到 PPT 预览数据类型（直接字典）')
            request_logger.info(f'[STREAM] PPT 共 {result.get("total_pages", 0)} 页，准备分页发送')

            # 1. 发送开始信号（元数据）
            start_msg = {
                'type': 'ppt_preview_start',
                'filename': result.get('filename'),
                'total_pages': result.get('total_pages'),
                'message': result.get('message', '')
            }
            yield f"data: {json.dumps(start_msg, ensure_ascii=False)}\n\n"
            request_logger.info(f'[STREAM] 发送 ppt_preview_start: {result.get("filename")}')

            # 2. 逐页发送幻灯片数据（每页单独一条消息，避免大数据被分割）
            for slide in result.get('slides', []):
                slide_msg = {
                    'type': 'ppt_slide',
                    'page': slide.get('page'),
                    'base64': slide.get('base64'),
                    'title': slide.get('title', f'第 {slide.get("page")} 页')
                }
                yield f"data: {json.dumps(slide_msg, ensure_ascii=False)}\n\n"
                request_logger.debug(f'[STREAM] 发送 ppt_slide: page {slide.get("page")}')

            # 3. 发送结束信号
            yield f"data: {json.dumps({'type': 'ppt_preview_end'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            request_logger.info(f'[STREAM] PPT 预览数据分页发送完成，共 {result.get("total_pages", 0)} 页')

        # 检查是否是生成器/迭代器（PPT制作返回生成器：先输出大纲，再输出预览）
        elif hasattr(result, '__iter__') and not isinstance(result, (str, bytes, dict)):
            request_logger.info('[STREAM] 检测到生成器/迭代器类型')
            chunk_count = 0

            for item in result:
                chunk_count += 1

                # 情况1：PPT 预览数据字典（制作PPT的最终输出）
                if isinstance(item, dict) and item.get('type') == 'ppt_preview':
                    request_logger.info(f'[STREAM] 生成器 item {chunk_count}: PPT 预览数据，共 {item.get("total_pages", 0)} 页')

                    # 1. 发送开始信号（元数据）
                    start_msg = {
                        'type': 'ppt_preview_start',
                        'filename': item.get('filename'),
                        'total_pages': item.get('total_pages'),
                        'message': item.get('message', '')
                    }
                    yield f"data: {json.dumps(start_msg, ensure_ascii=False)}\n\n"

                    # 2. 逐页发送幻灯片数据
                    for slide in item.get('slides', []):
                        slide_msg = {
                            'type': 'ppt_slide',
                            'page': slide.get('page'),
                            'base64': slide.get('base64'),
                            'title': slide.get('title', f'第 {slide.get("page")} 页')
                        }
                        yield f"data: {json.dumps(slide_msg, ensure_ascii=False)}\n\n"

                    # 3. 发送结束信号
                    yield f"data: {json.dumps({'type': 'ppt_preview_end'}, ensure_ascii=False)}\n\n"

                # 情况2：字符串（大纲文本或其他消息）
                elif isinstance(item, str):
                    request_logger.debug(f'[STREAM] 生成器 item {chunk_count}: 字符串，长度 {len(item)}')
                    yield f"data: {json.dumps({'chunk': item}, ensure_ascii=False)}\n\n"

                # 情况3：字典（所有 *_complete 事件统一转发）
                elif isinstance(item, dict) and item.get('type', '').endswith('_complete'):
                    request_logger.info(f'[STREAM] 生成器 item {chunk_count}: 完成事件 type={item.get("type")}')
                    content_data = item.get('data', {})
                    yield f"data: {json.dumps({'type': item.get('type'), 'data': content_data}, ensure_ascii=False)}\n\n"

                # 情况4：音频数据（单独发送）- 大文件数据在流式传输中可能分割，需要特殊处理
                elif isinstance(item, dict) and item.get('type') == 'video_audio_data':
                    request_logger.info(f'[STREAM] 生成器 item {chunk_count}: 视频音频数据 (base64长度: {len(item.get("audio_base64", ""))})')
                    print(f"[DEBUG APP] 收到音频数据，准备发送，base64长度: {len(item.get('audio_base64', ''))}")
                    # 使用流式方式发送大数据，避免一次发送过多数据导致缓冲问题
                    audio_data = item.get('audio_base64', '')
                    voiceover_text = item.get('voiceover_text', '')
                    audio_filename = item.get('audio_filename', '')
                    # 分段发送音频数据
                    yield f"data: {json.dumps({'type': 'video_audio_data', 'audio_base64': audio_data, 'audio_filename': audio_filename, 'voiceover_text': voiceover_text}, ensure_ascii=False)}\n\n"

                # 情况5：图片数据（单独发送）
                elif isinstance(item, dict) and item.get('type') == 'graphic_image_data':
                    request_logger.info(f'[STREAM] 生成器 item {chunk_count}: 图文图片数据 (base64长度: {len(item.get("image_base64", ""))})')
                    print(f"[DEBUG APP] 收到图片数据，准备发送，base64长度: {len(item.get('image_base64', ''))}")
                    image_data = item.get('image_base64', '')
                    prompt = item.get('prompt', '')
                    image_filename = item.get('image_filename', '')
                    yield f"data: {json.dumps({'type': 'graphic_image_data', 'image_base64': image_data, 'image_filename': image_filename, 'prompt': prompt}, ensure_ascii=False)}\n\n"

                # 情况6：图文文案数据（小红书 markdown 文案）
                elif isinstance(item, dict) and item.get('type') == 'graphic_text_data':
                    xiaohongshu = item.get('xiaohongshu', '')
                    request_logger.info(f'[STREAM] 生成器 item {chunk_count}: 图文文案数据 (字符长度: {len(xiaohongshu)})')
                    yield f"data: {json.dumps({'type': 'graphic_text_data', 'xiaohongshu': xiaohongshu}, ensure_ascii=False)}\n\n"

                # 情况7：结构化进度事件（替代旧的 emoji 字符串进度）
                elif isinstance(item, dict) and item.get('type') == 'progress':
                    request_logger.debug(f"[STREAM] 生成器 item {chunk_count}: 进度 stage={item.get('stage')} percent={item.get('percent')} kind={item.get('kind')}")
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

                # 其他情况：忽略
                else:
                    request_logger.warning(f'[STREAM] 生成器 item {chunk_count}: 未知类型 {type(item)}')

            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            request_logger.info(f'[STREAM] 生成器处理完成，共 {chunk_count} 个 items')

        # 纯字符串响应
        elif isinstance(result, str):
            request_logger.info('[STREAM] 检测到字符串响应类型')
            yield f"data: {json.dumps({'chunk': result}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            request_logger.info('[STREAM] 字符串响应发送完成')

        # 其他情况（流式响应生成器）
        else:
            request_logger.info('[STREAM] 开始流式传输响应（原生流）')
            chunk_count = 0
            for chunk in result:
                chunk_count += 1
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                request_logger.debug(f'[STREAM] 发送 chunk {chunk_count}: {chunk[:50]}...' if len(chunk) > 50 else f'[STREAM] 发送 chunk {chunk_count}: {chunk}')
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            request_logger.info(f'[STREAM] 流式传输完成，共发送 {chunk_count} 个 chunks')

    request_logger.info('[STREAM] 返回流式响应')
    # 使用分块传输编码，确保大数据能够实时流式传输
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['X-Accel-Buffering'] = 'no'  # 禁用 Nginx 缓冲
    response.headers['Cache-Control'] = 'no-cache'
    return response


@app.route('/api/clear', methods=['POST'])
def clear_history():
    """清空对话历史"""
    request_logger.info('=' * 50)
    request_logger.info('[CLEAR] 收到清空历史请求')
    request_logger.info(f'[CLEAR] 请求数据: {request.json}')

    data = request.json
    session_id = data.get('session_id', 'default')
    request_logger.info(f'[CLEAR] session_id: {session_id}')

    if session_id in sessions:
        request_logger.info(f'[CLEAR] 清空 session {session_id} 的历史')
        sessions[session_id].clear_history()
        # 同时清除会话记录文件
        sessions[session_id].memory.clear_session_file()
        request_logger.info('[CLEAR] 历史已清空')
    else:
        request_logger.warning(f'[CLEAR] session {session_id} 不存在，无需清空')

    return jsonify({'success': True, 'message': '历史已清空'})


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取对话历史"""
    session_id = request.args.get('session_id', 'default')
    request_logger.info('=' * 50)
    request_logger.info(f'[HISTORY] 收到获取历史请求, session_id: {session_id}')

    agent = get_agent(session_id)
    history = agent.get_history()
    request_logger.info(f'[HISTORY] 返回历史记录，当前共 {len(history)} 条消息')

    return jsonify({
        'history': agent.get_history()
    })


# ==================== 模型 Provider 注册表 ====================

PROVIDERS = {
    'minimax': {
        'id': 'minimax',
        'name': 'MiniMax',
        'type': 'minimax',
        'defaultBaseUrl': 'https://api.minimax.chat/v1/text/chatcompletion_v2',
        'models': [
            {'id': 'MiniMax-M2.5-highspeed', 'name': 'MiniMax M2.5 高速', 'contextWindow': 16384, 'maxOutput': 4096},
        ],
        'requiresApiKey': True,
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
        'type': 'openai',
        'defaultBaseUrl': 'https://open.bigmodel.cn/api/paas/v4',
        'models': [
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
}

# ==================== TTS Provider 注册表 ====================

TTS_PROVIDERS = {
    'minimax-tts': {
        'id': 'minimax-tts',
        'name': 'MiniMax TTS (MiMo)',
        'type': 'minimax-tts',
        'defaultBaseUrl': 'https://api.xiaomimimo.com/v1',
        'models': [
            {'id': 'mimo-v2.5-tts', 'name': 'MiMo V2.5 TTS'},
        ],
        'voices': [
            {'id': 'mimo_default', 'name': '默认音色'},
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
}

# 服务端已配置的 API Keys（来自环境变量）
SERVER_API_KEYS = {}
if os.environ.get('MINIMAX_API_KEY'):
    SERVER_API_KEYS['minimax'] = os.environ['MINIMAX_API_KEY']
if os.environ.get('DEEPSEEK_API_KEY'):
    SERVER_API_KEYS['deepseek'] = os.environ['DEEPSEEK_API_KEY']
if os.environ.get('MIMO_API_KEY'):
    SERVER_API_KEYS['minimax-tts'] = os.environ['MIMO_API_KEY']


def _get_provider_for_model(model_id: str):
    """根据 model ID 查找所属 provider"""
    for pid, p in PROVIDERS.items():
        for m in p['models']:
            if m['id'] == model_id:
                return pid, p, m
    return None, None, None


@app.route('/api/models', methods=['GET'])
def get_models():
    """获取可用模型列表（兼容旧接口）"""
    models = []
    for pid, p in PROVIDERS.items():
        for m in p['models']:
            models.append({
                'id': m['id'],
                'name': m['name'],
                'description': f"{p['name']} · {m['id']}",
                'provider': pid,
            })
    return jsonify({'models': models})


@app.route('/api/providers', methods=['GET'])
def get_providers():
    """获取所有 provider 及模型列表（不含 API Key）"""
    result = {}
    for pid, p in PROVIDERS.items():
        result[pid] = {
            'id': p['id'],
            'name': p['name'],
            'type': p['type'],
            'defaultBaseUrl': p['defaultBaseUrl'],
            'models': p['models'],
            'requiresApiKey': p['requiresApiKey'],
            'isServerConfigured': pid in SERVER_API_KEYS,
        }
    return jsonify({'providers': result})


@app.route('/api/tts-providers', methods=['GET'])
def get_tts_providers():
    """获取所有 TTS provider 及模型/音色列表"""
    result = {}
    for pid, p in TTS_PROVIDERS.items():
        result[pid] = {
            'id': p['id'],
            'name': p['name'],
            'type': p['type'],
            'defaultBaseUrl': p['defaultBaseUrl'],
            'models': p['models'],
            'voices': p.get('voices', []),
            'requiresApiKey': p['requiresApiKey'],
            'isServerConfigured': pid in SERVER_API_KEYS,
        }
    return jsonify({'providers': result})


@app.route('/api/verify-model', methods=['POST'])
def verify_model():
    """验证模型连接 - 发送测试消息确认 API Key 可用"""
    data = request.json
    api_key = (data.get('apiKey') or '').strip()
    base_url = (data.get('baseUrl') or '').strip()
    model_id = (data.get('model') or '').strip()
    provider_id = (data.get('providerId') or '').strip()
    provider_type = (data.get('providerType') or 'openai').strip()

    # 如果用户未提供 API Key，但 provider 在服务端已配置，则使用服务端 Key
    if not api_key and provider_id in SERVER_API_KEYS:
        api_key = SERVER_API_KEYS[provider_id]

    if not api_key:
        return jsonify({'success': False, 'message': '请填写 API Key'}), 400

    if not model_id:
        return jsonify({'success': False, 'message': '请选择模型'}), 400

    if not base_url and provider_id in PROVIDERS:
        base_url = PROVIDERS[provider_id]['defaultBaseUrl']
    if not base_url and provider_id in TTS_PROVIDERS:
        base_url = TTS_PROVIDERS[provider_id]['defaultBaseUrl']

    if not base_url:
        return jsonify({'success': False, 'message': '无法确定 API 地址'}), 400

    try:
        if provider_type == 'minimax':
            return _verify_minimax(api_key, base_url, model_id)
        elif provider_type == 'minimax-tts':
            return _verify_minimax_tts(api_key, base_url, model_id)
        elif provider_type == 'openai-tts':
            return _verify_openai_tts(api_key, base_url, model_id)
        else:
            return _verify_openai_compatible(api_key, base_url, model_id)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def _verify_openai_compatible(api_key: str, base_url: str, model_id: str):
    """验证 OpenAI 兼容 API"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=15)

    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[{'role': 'user', 'content': 'Say "OK" if you can hear me.'}],
            max_tokens=64,
        )
        text = response.choices[0].message.content or ''
        return jsonify({
            'success': True,
            'message': '连接成功',
            'response': text.strip(),
        })
    except Exception as e:
        error_str = str(e)
        if '401' in error_str or 'Unauthorized' in error_str or 'Incorrect API key' in error_str:
            msg = 'API Key 无效或已过期'
        elif '404' in error_str or 'not found' in error_str.lower():
            msg = '模型未找到，请检查模型 ID 或 Base URL'
        elif '429' in error_str:
            msg = 'API 请求频率超限，请稍后再试'
        elif 'timeout' in error_str.lower() or 'timed out' in error_str.lower():
            msg = '连接超时，请检查网络或 Base URL'
        elif 'Connection' in error_str or 'ENOTFOUND' in error_str or 'ECONNREFUSED' in error_str:
            msg = '无法连接到 API 服务器，请检查 Base URL'
        else:
            msg = error_str
        return jsonify({'success': False, 'message': msg})


def _safe_json(resp):
    """安全解析 JSON 响应，失败则返回空字典"""
    try:
        return resp.json() if resp.text else {}
    except Exception:
        return {}


def _verify_minimax_tts(api_key: str, base_url: str, model_id: str):
    """验证 MiniMax TTS (MiMo) — chat completions + audio 格式"""
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    # OpenAI SDK 会自动拼接 /chat/completions，这里手动拼接
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        'model': model_id,
        'messages': [
            {'role': 'user', 'content': '请朗读'},
            {'role': 'assistant', 'content': 'OK'},
        ],
        'max_tokens': 64,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return jsonify({'success': True, 'message': '连接成功'})
        elif resp.status_code == 401 or resp.status_code == 403:
            return jsonify({'success': False, 'message': 'API Key 无效或已过期'})
        elif resp.status_code == 404:
            return jsonify({'success': False, 'message': f'端点不存在 (404)，请检查 Base URL: {url}'})
        else:
            error_data = _safe_json(resp)
            msg = error_data.get('error', {}).get('message', '') or resp.text[:200]
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def _verify_openai_tts(api_key: str, base_url: str, model_id: str):
    """验证 OpenAI TTS / GLM TTS — /audio/speech 端点"""
    url = f"{base_url.rstrip('/')}/audio/speech"
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': model_id,
        'input': 'OK',
        'voice': 'alloy',
        'response_format': 'mp3',
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            return jsonify({'success': True, 'message': '连接成功'})
        elif resp.status_code == 401 or resp.status_code == 403:
            return jsonify({'success': False, 'message': 'API Key 无效或已过期'})
        elif resp.status_code == 404:
            return jsonify({'success': False, 'message': f'端点不存在 (404)，请检查 Base URL: {url}'})
        else:
            error_data = _safe_json(resp)
            msg = error_data.get('error', {}).get('message', '') or resp.text[:200]
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def _verify_minimax(api_key: str, base_url: str, model_id: str):
    """验证 MiniMax API"""
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': model_id,
        'messages': [{'role': 'user', 'content': 'Say "OK" if you can hear me.'}],
        'max_tokens': 64,
    }
    try:
        resp = requests.post(base_url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            data = _safe_json(resp)
            text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            return jsonify({'success': True, 'message': '连接成功', 'response': text.strip()})
        elif resp.status_code == 401:
            return jsonify({'success': False, 'message': 'API Key 无效或已过期'})
        else:
            return jsonify({'success': False, 'message': f'HTTP {resp.status_code}: {resp.text[:200]}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


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
    'ppt_model': 'deepseek-v4-flash',
    'ppt_provider': 'deepseek',
    'tts_provider': 'minimax-tts',
    'tts_model': 'mimo-v2.5-tts',
    'tts_voice': 'mimo_default',
}

# 存储用户设置（简单实现，生产环境应使用数据库）
user_settings = {}

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取当前设置"""
    # 优先从 config.json 加载已保存的设置
    memory = get_memory_manager()
    config = memory.get_config()
    saved_settings = config.get('content_settings', {})
    settings = {**DEFAULT_SETTINGS, **saved_settings}

    return jsonify({
        'settings': settings,
        'options': {
            'chat_model': [
                {'value': 'MiniMax-M2.5-highspeed', 'label': 'MiniMax M2.5 高速'},
            ],
            'mimo_voice': [
                {'value': 'mimo_default', 'label': 'MiMo-默认'},
                {'value': 'default_zh', 'label': 'MiMo-中文女声'},
                {'value': 'default_en', 'label': 'MiMo-英文女声'}
            ],
            'mimo_style': [
                {'value': '', 'label': '无（默认）'},
                {'value': '开心', 'label': '开心'},
                {'value': '悲伤', 'label': '悲伤'},
                {'value': '生气', 'label': '生气'},
                {'value': '悄悄话', 'label': '悄悄话'},
                {'value': '东北话', 'label': '东北话'},
                {'value': '四川话', 'label': '四川话'},
                {'value': '粤语', 'label': '粤语'}
            ],
            'aspect_ratio': [
                {'value': '3:4', 'label': '3:4 竖图（小红书推荐）'},
                {'value': '1:1', 'label': '1:1 方图'}
            ],
            'cover_style': [
                {'value': 'infographic', 'label': '一图流文字版'},
                {'value': 'minimal', 'label': '极简纯图版'}
            ]
        }
    })


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """更新设置"""
    global DEFAULT_SETTINGS
    data = request.json
    new_settings = data.get('settings', {})

    # 更新设置
    for key, value in new_settings.items():
        if key in DEFAULT_SETTINGS:
            DEFAULT_SETTINGS[key] = value

    # 同步更新到所有已创建的 agent
    for session_id, agent in sessions.items():
        agent.update_content_settings(DEFAULT_SETTINGS)

    # 同步持久化到 config.json
    memory = get_memory_manager()
    config = memory.get_config()
    if 'content_settings' not in config:
        config['content_settings'] = {}
    config['content_settings'].update(new_settings)
    memory.update_config(config)

    request_logger.info(f'[SETTINGS] 设置已更新: {DEFAULT_SETTINGS}')
    return jsonify({'success': True, 'settings': DEFAULT_SETTINGS})


# ==================== 文件管理 API ====================

@app.route('/api/files', methods=['GET'])
def get_files():
    """获取所有生成的文件列表"""
    request_logger.info('[FILES] 获取文件列表')

    files = []

    # 扫描 PPT 文件
    ppt_dir = os.path.join(GENERATORS_DIR, "generated_ppt")
    if os.path.exists(ppt_dir):
        for f in os.listdir(ppt_dir):
            if f.endswith('.pptx') and not f.startswith('~$'):
                filepath = os.path.join(ppt_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'ppt_{f}',
                    'name': f,
                    'type': 'ppt',
                    'type_label': 'PPT',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '📊'
                })

    # 扫描 SVG PPT 导出的 PPTX 文件
    svg_ppt_dir = os.path.join(BACKEND_DIR, 'generated_svg_ppt')
    if os.path.exists(svg_ppt_dir):
        for job_dir in os.listdir(svg_ppt_dir):
            job_path = os.path.join(svg_ppt_dir, job_dir)
            if not os.path.isdir(job_path) or job_dir.startswith('temp_'):
                continue
            exports_dir = os.path.join(job_path, 'exports')
            if not os.path.exists(exports_dir):
                continue
            # 只取第一个 .pptx 文件
            pptx_files = [f for f in os.listdir(exports_dir)
                          if f.endswith('.pptx') and not f.startswith('~$')]
            if not pptx_files:
                continue
            f = pptx_files[0]
            filepath = os.path.join(exports_dir, f)
            stat = os.stat(filepath)
            # 读取 topic 作为友好文件名
            topic = None
            meta_path = os.path.join(job_path, 'metadata.json')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as mf:
                        meta = json.load(mf)
                    topic = meta.get('topic')
                except Exception:
                    pass
            display_name = f"{topic}.pptx" if topic else f
            files.append({
                'id': f'svg_ppt_{job_dir}',
                'name': display_name,
                'type': 'ppt',
                'type_label': 'PPT',
                'path': filepath,
                'size': stat.st_size,
                'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                'icon': '📊'
            })

    # 扫描讲义文件
    lecture_dir = os.path.join(GENERATORS_DIR, "generated_lectures")
    if os.path.exists(lecture_dir):
        for f in os.listdir(lecture_dir):
            if f.endswith('.md'):
                filepath = os.path.join(lecture_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'lecture_{f}',
                    'name': f,
                    'type': 'lecture',
                    'type_label': '讲义',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '📚'
                })

    # 扫描课程大纲文件
    outline_dir = os.path.join(GENERATORS_DIR, "generated_outlines")
    if os.path.exists(outline_dir):
        for f in os.listdir(outline_dir):
            if f.endswith(('.md', '.docx')):
                filepath = os.path.join(outline_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'outline_{f}',
                    'name': f,
                    'type': 'outline',
                    'type_label': '课程大纲',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '📋'
                })

    # 扫描讲稿文件
    speech_dir = os.path.join(GENERATORS_DIR, "generated_speeches")
    if os.path.exists(speech_dir):
        for f in os.listdir(speech_dir):
            if f.endswith(('.md', '.docx')):
                filepath = os.path.join(speech_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'speech_{f}',
                    'name': f,
                    'type': 'speech',
                    'type_label': '讲稿',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '🎤'
                })

    # 扫描习题集文件
    exercise_dir = os.path.join(GENERATORS_DIR, "generated_exercises")
    if os.path.exists(exercise_dir):
        for f in os.listdir(exercise_dir):
            if f.endswith(('.md', '.docx')):
                filepath = os.path.join(exercise_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'exercise_{f}',
                    'name': f,
                    'type': 'exercise',
                    'type_label': '习题集',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '✏️'
                })

    # 扫描课堂测验文件
    quiz_dir = os.path.join(GENERATORS_DIR, "generated_quizzes")
    if os.path.exists(quiz_dir):
        for f in os.listdir(quiz_dir):
            if f.endswith(('.md', '.docx')):
                filepath = os.path.join(quiz_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'quiz_{f}',
                    'name': f,
                    'type': 'quiz',
                    'type_label': '课堂测验',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '❓'
                })

    # 扫描知识卡片文件
    card_dir = os.path.join(GENERATORS_DIR, "generated_cards")
    if os.path.exists(card_dir):
        for f in os.listdir(card_dir):
            if f.endswith(('.md', '.docx')):
                filepath = os.path.join(card_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'card_{f}',
                    'name': f,
                    'type': 'knowledge_card',
                    'type_label': '知识卡片',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '🃏'
                })

    # 扫描思维导图文件
    mindmap_dir = os.path.join(GENERATORS_DIR, "generated_mindmaps")
    if os.path.exists(mindmap_dir):
        for f in os.listdir(mindmap_dir):
            if f.endswith('.md'):
                filepath = os.path.join(mindmap_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'mindmap_{f}',
                    'name': f,
                    'type': 'mindmap',
                    'type_label': '思维导图',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '🧠'
                })

    # 扫描图文内容文本文件
    content_text_dir = os.path.join(GENERATORS_DIR, "generated_content/text")
    if os.path.exists(content_text_dir):
        for f in os.listdir(content_text_dir):
            if f.endswith('.md'):
                filepath = os.path.join(content_text_dir, f)
                stat = os.stat(filepath)
                # 判断是视频脚本还是小红书文案
                type_label = '视频脚本' if f.startswith('video_script') else '小红书文案'
                files.append({
                    'id': f'content_text_{f}',
                    'name': f,
                    'type': 'content_text',
                    'type_label': type_label,
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '📝'
                })

    # 扫描音频文件
    content_audio_dir = os.path.join(GENERATORS_DIR, "generated_content/audio")
    if os.path.exists(content_audio_dir):
        for f in os.listdir(content_audio_dir):
            if f.endswith('.wav'):
                filepath = os.path.join(content_audio_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'content_audio_{f}',
                    'name': f,
                    'type': 'content_audio',
                    'type_label': '音频',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '🔊'
                })

    # 扫描图片文件
    content_image_dir = os.path.join(GENERATORS_DIR, "generated_content/images")
    if os.path.exists(content_image_dir):
        for f in os.listdir(content_image_dir):
            if f.endswith(('.jpeg', '.jpg', '.png')):
                filepath = os.path.join(content_image_dir, f)
                stat = os.stat(filepath)
                files.append({
                    'id': f'content_image_{f}',
                    'name': f,
                    'type': 'content_image',
                    'type_label': '封面图',
                    'path': filepath,
                    'size': stat.st_size,
                    'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '🖼️'
                })

    # 扫描微课视频文件
    video_dir = os.path.join(BACKEND_DIR, "generated_videos")
    if os.path.exists(video_dir):
        for item in os.listdir(video_dir):
            item_path = os.path.join(video_dir, item)
            # 跳过临时目录与非目录
            if not os.path.isdir(item_path) or item.startswith('temp_'):
                continue
            video_file = os.path.join(item_path, '07-video.mp4')
            if os.path.exists(video_file):
                stat = os.stat(video_file)
                size_mb = stat.st_size / (1024 * 1024)
                files.append({
                    'id': f'video_{item}',
                    'name': f'{item}.mp4',
                    'type': 'video',
                    'type_label': '微课视频',
                    'path': video_file,
                    'size': stat.st_size,
                    'size_formatted': f"{size_mb:.1f} MB" if size_mb >= 1 else f"{stat.st_size / 1024:.1f} KB",
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    'icon': '🎬'
                })

    # 按时间倒序排列
    files.sort(key=lambda x: x['created'], reverse=True)

    request_logger.info(f'[FILES] 找到 {len(files)} 个文件')
    return jsonify({'files': files})


@app.route('/api/files/delete', methods=['POST'])
def delete_file():
    """删除文件"""
    data = request.json
    file_path = data.get('path', '')

    request_logger.info(f'[FILES] 删除文件请求: {file_path}')

    if not file_path or not os.path.exists(file_path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404

    # 安全检查：确保文件在允许的目录中
    allowed_dirs = [os.path.join(GENERATORS_DIR, d) for d in [
        'generated_ppt', 'generated_lectures', 'generated_content',
        'generated_outlines', 'generated_speeches', 'generated_exercises',
        'generated_quizzes', 'generated_cards', 'generated_mindmaps'
    ]]
    # 微课视频在 BACKEND_DIR/generated_videos 下
    video_root = os.path.join(BACKEND_DIR, 'generated_videos')
    allowed_dirs.append(video_root)
    # SVG PPT 在 BACKEND_DIR/generated_svg_ppt 下
    svg_ppt_root = os.path.join(BACKEND_DIR, 'generated_svg_ppt')
    allowed_dirs.append(svg_ppt_root)
    abs_path = os.path.abspath(file_path)
    is_allowed = any(abs_path.startswith(d) for d in allowed_dirs)

    if not is_allowed:
        request_logger.warning(f'[FILES] 非法删除路径: {file_path}')
        return jsonify({'success': False, 'error': '无权删除此文件'}), 403

    try:
        # 视频文件：删除整个父目录（含中间产物）
        if abs_path.startswith(os.path.abspath(video_root)):
            parent_dir = os.path.dirname(abs_path)
            if os.path.isdir(parent_dir) and parent_dir.startswith(os.path.abspath(video_root)):
                shutil.rmtree(parent_dir)
                request_logger.info(f'[FILES] 视频目录已删除: {parent_dir}')
                return jsonify({'success': True, 'message': '视频已删除'})

        os.remove(abs_path)
        request_logger.info(f'[FILES] 文件已删除: {file_path}')
        return jsonify({'success': True, 'message': '文件已删除'})
    except Exception as e:
        request_logger.error(f'[FILES] 删除失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/files/rename', methods=['POST'])
def rename_file():
    """重命名文件"""
    data = request.json
    old_path = data.get('path', '')
    new_name = data.get('new_name', '')

    request_logger.info(f'[FILES] 重命名文件: {old_path} -> {new_name}')

    if not old_path or not os.path.exists(old_path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404

    if not new_name or '/' in new_name or '\\' in new_name:
        return jsonify({'success': False, 'error': '无效的文件名'}), 400

    # 安全检查
    allowed_dirs = [os.path.join(GENERATORS_DIR, d) for d in [
        'generated_ppt', 'generated_lectures', 'generated_content',
        'generated_outlines', 'generated_speeches', 'generated_exercises',
        'generated_quizzes', 'generated_cards', 'generated_mindmaps'
    ]]
    # SVG PPT 在 BACKEND_DIR/generated_svg_ppt 下
    svg_ppt_root = os.path.join(BACKEND_DIR, 'generated_svg_ppt')
    allowed_dirs.append(svg_ppt_root)
    abs_old = os.path.abspath(old_path)
    is_allowed = any(abs_old.startswith(d) for d in allowed_dirs)

    if not is_allowed:
        request_logger.warning(f'[FILES] 非法重命名路径: {old_path}')
        return jsonify({'success': False, 'error': '无权重命名此文件'}), 403

    try:
        # 获取文件扩展名
        old_ext = os.path.splitext(abs_old)[1]
        # 确保新文件名有正确的扩展名
        if not new_name.endswith(old_ext):
            new_name += old_ext

        new_path = os.path.join(os.path.dirname(abs_old), new_name)

        if os.path.exists(new_path):
            return jsonify({'success': False, 'error': '目标文件已存在'}), 400

        os.rename(abs_old, new_path)
        request_logger.info(f'[FILES] 文件已重命名: {abs_old} -> {new_path}')
        return jsonify({'success': True, 'message': '文件已重命名', 'new_path': new_path})
    except Exception as e:
        request_logger.error(f'[FILES] 重命名失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/files/clear', methods=['POST'])
def clear_all_files():
    """清空所有生成的文件"""
    data = request.json
    confirm = data.get('confirm', False)

    if not confirm:
        return jsonify({'success': False, 'error': '需要确认清空操作'}), 400

    request_logger.info('[FILES] 收到清空所有文件请求')

    allowed_dirs = [
        'generated_ppt', 'generated_lectures', 'generated_content',
        'generated_outlines', 'generated_speeches', 'generated_exercises',
        'generated_quizzes', 'generated_cards', 'generated_mindmaps',
        'generated_svg_ppt', 'generated_videos'
    ]
    deleted_count = 0
    errors = []

    for dir_name in allowed_dirs:
        if dir_name == 'generated_svg_ppt':
            # SVG PPT 在 BACKEND_DIR 下，不在 generators 子目录
            dir_path = os.path.join(BACKEND_DIR, 'generated_svg_ppt')
        elif dir_name == 'generated_videos':
            # 微课视频在 BACKEND_DIR 下
            dir_path = os.path.join(BACKEND_DIR, 'generated_videos')
        else:
            dir_path = os.path.join(GENERATORS_DIR, dir_name)
        if os.path.exists(dir_path):
            try:
                if dir_name == 'generated_svg_ppt':
                    # SVG PPT 以 job 目录存储，需要删整个目录
                    for job_id in os.listdir(dir_path):
                        job_path = os.path.join(dir_path, job_id)
                        abs_job = os.path.abspath(job_path)
                        if os.path.isdir(abs_job) and abs_job.startswith(os.path.abspath(dir_path)):
                            shutil.rmtree(abs_job)
                            deleted_count += 1
                elif dir_name == 'generated_videos':
                    # 视频以子目录存储（每个子目录含 07-video.mp4 与中间产物），整个目录删除
                    for sub in os.listdir(dir_path):
                        sub_path = os.path.join(dir_path, sub)
                        abs_sub = os.path.abspath(sub_path)
                        if os.path.isdir(abs_sub) and abs_sub.startswith(os.path.abspath(dir_path)):
                            try:
                                shutil.rmtree(abs_sub)
                                deleted_count += 1
                            except Exception as e:
                                errors.append(f'删除 {abs_sub} 失败: {e}')
                else:
                    for root, dirs, files in os.walk(dir_path):
                        for f in files:
                            file_path = os.path.join(root, f)
                            if os.path.isfile(file_path):
                                try:
                                    os.remove(file_path)
                                    deleted_count += 1
                                except Exception as e:
                                    errors.append(f'删除 {file_path} 失败: {e}')
            except Exception as e:
                errors.append(f'清空目录 {dir_path} 失败: {e}')

    request_logger.info(f'[FILES] 清空完成，共删除 {deleted_count} 个文件')
    if errors:
        request_logger.error(f'[FILES] 清空过程中的错误: {errors}')

    return jsonify({
        'success': True,
        'message': f'已清空 {deleted_count} 个文件',
        'deleted_count': deleted_count,
        'errors': errors
    })


@app.route('/api/files/download', methods=['GET'])
def download_file():
    """下载指定路径的文件"""
    filepath = request.args.get('path', '')
    if not filepath:
        return jsonify({'error': '缺少 path 参数'}), 400

    # 安全校验：只允许 generated_* 目录下的文件
    abs_path = os.path.abspath(filepath)
    base_dir = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
    if not abs_path.startswith(base_dir):
        return jsonify({'error': '非法路径'}), 403

    allowed_prefixes = [os.path.join(base_dir, d) for d in [
        'generated_ppt', 'generated_lectures', 'generated_content',
        'generated_outlines', 'generated_speeches', 'generated_exercises',
        'generated_quizzes', 'generated_cards', 'generated_mindmaps',
        'generated_svg_ppt', 'ppt_previews', 'generated_videos',
        os.path.join('generators', 'generated_exercises'),
        os.path.join('generators', 'generated_quizzes'),
        os.path.join('generators', 'generated_lectures'),
        os.path.join('generators', 'generated_outlines'),
        os.path.join('generators', 'generated_speeches'),
        os.path.join('generators', 'generated_cards'),
        os.path.join('generators', 'generated_mindmaps'),
        os.path.join('generators', 'generated_ppt'),
        os.path.join('generators', 'generated_content'),
    ]]
    if not any(abs_path.startswith(p) for p in allowed_prefixes):
        return jsonify({'error': '文件不在允许的目录中'}), 403

    if not os.path.isfile(abs_path):
        return jsonify({'error': '文件不存在'}), 404

    from flask import send_file as flask_send_file
    return flask_send_file(abs_path, as_attachment=True,
                           download_name=os.path.basename(abs_path))


@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    """上传 PPTX 文件"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'}), 400

    if not file.filename.endswith('.pptx'):
        return jsonify({'success': False, 'error': '只支持 PPTX 文件'}), 400

    # 保存到 uploads 目录（不在文件库扫描范围内）
    upload_dir = os.path.join(BACKEND_DIR, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    request_logger.info(f'[UPLOAD] 文件已上传: {filepath}')
    return jsonify({'success': True, 'path': filepath, 'name': filename})


@app.route('/api/files/read', methods=['GET'])
def read_file():
    """读取文本文件内容（用于预览）"""
    filepath = request.args.get('path', '')
    if not filepath:
        return jsonify({'error': '缺少 path 参数'}), 400

    abs_path = os.path.abspath(filepath)
    base_dir = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
    if not abs_path.startswith(base_dir):
        return jsonify({'error': '非法路径'}), 403

    if not os.path.isfile(abs_path):
        return jsonify({'error': '文件不存在'}), 404

    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content, 'filename': os.path.basename(abs_path)})
    except UnicodeDecodeError:
        return jsonify({'error': '文件不是文本格式'}), 400


# ==================== 记忆设置 API ====================

@app.route('/api/memory', methods=['GET'])
def get_memory_summary_api():
    """获取记忆摘要"""
    memory = get_memory_manager()
    summary = memory.get_memory_summary()
    return jsonify({'summary': summary})


@app.route('/api/memory/save', methods=['POST'])
def save_memory_api():
    """保存当前对话到记忆"""
    data = request.json
    session_id = data.get('session_id', 'default')
    agent = get_agent(session_id)
    result = agent._save_conversation_essence()
    return jsonify({'result': result})


@app.route('/api/memory/clear', methods=['POST'])
def clear_memory_api():
    """清除长期记忆"""
    memory = get_memory_manager()
    memory.clear_long_term_memory()
    return jsonify({'success': True})


@app.route('/api/memory/clear-daily', methods=['POST'])
def clear_daily_api():
    """清除当前会话记录"""
    data = request.json
    session_id = data.get('session_id', 'default')
    agent = get_agent(session_id)
    agent.clear_history()
    agent.memory.clear_session_file()
    return jsonify({'success': True})


@app.route('/api/memory/search', methods=['GET'])
def search_memory_api():
    """搜索记忆"""
    keyword = request.args.get('keyword', '')
    memory = get_memory_manager()
    results = memory.search_memory(keyword)
    return jsonify({'results': results})


# PPT 预览图加载
@app.route('/api/ppt-preview/<filename>', methods=['GET'])
def get_ppt_preview(filename):
    """加载 PPT 预览图"""
    import base64
    from urllib.parse import unquote
    filename = unquote(filename)
    # 移除 .pptx 扩展名，因为预览目录是用 stem（有别于 name）创建的
    name_without_ext = filename.replace('.pptx', '')
    preview_dir = os.path.join(os.path.dirname(__file__), 'ppt_previews', name_without_ext)
    slides = []
    if os.path.exists(preview_dir):
        for f in sorted(os.listdir(preview_dir)):
            if f.endswith('.png'):
                path = os.path.join(preview_dir, f)
                with open(path, 'rb') as img:
                    b64 = base64.b64encode(img.read()).decode('utf-8')
                    slides.append({'page': f.replace('slide_', '').replace('.png', ''), 'data': b64})
    return jsonify({'slides': slides})

# 图文封面图加载
@app.route('/api/graphic/image/<filename>', methods=['GET'])
def get_graphic_image(filename):
    """加载图文封面图"""
    import base64
    from urllib.parse import unquote
    filename = unquote(filename)
    print(f"[DEBUG] 加载图文图片请求: filename={filename}")
    path = os.path.join(GENERATORS_DIR, 'generated_content', 'images', filename)
    print(f"[DEBUG] 图片完整路径: {path}, 存在: {os.path.exists(path)}")
    if os.path.exists(path):
        with open(path, 'rb') as img:
            b64 = base64.b64encode(img.read()).decode('utf-8')
            return jsonify({'image': b64})
    return jsonify({'image': None})

# 视频音频加载
@app.route('/api/video/audio/<filename>', methods=['GET'])
def get_video_audio(filename):
    """加载视频音频"""
    import base64
    from urllib.parse import unquote
    filename = unquote(filename)
    path = os.path.join(GENERATORS_DIR, 'generated_content', 'audio', filename)
    if os.path.exists(path):
        with open(path, 'rb') as audio:
            b64 = base64.b64encode(audio.read()).decode('utf-8')
            return jsonify({'audio': b64})
    return jsonify({'audio': None})


# ==================== SVG PPT 端点 ====================

@app.route('/api/ppt-svg/generate', methods=['POST'])
def ppt_svg_generate():
    """SVG PPT 流式生成接口（SSE）"""
    data = request.json
    topic = data.get('topic', '').strip()
    language = data.get('language', 'zh')
    num_slides = data.get('num_slides')
    style = data.get('style', 'education')
    detail_level = data.get('detail_level', 'normal')
    model = data.get('model', 'deepseek-v4-flash')
    api_key = data.get('api_key')

    if not topic:
        return jsonify({'error': '课程主题不能为空'}), 400

    def generate():
        from ppt_engine.pipeline import PPTPipeline
        from ppt_engine.sse_bridge import SSEBridge

        pipeline = PPTPipeline()
        bridge = SSEBridge()
        bridge.run(pipeline.generate(
            topic,
            model=model,
            api_key=api_key,
            language=language,
            num_slides=num_slides,
            style=style,
            detail_level=detail_level,
        ))

        try:
            for event in bridge.events():
                # Forward SSE heartbeat comments directly
                if isinstance(event, str):
                    yield event
                    continue

                event_data = {
                    'type': f'ppt_svg_{event.status}',
                    'stage': event.stage,
                    'message': event.message,
                    'progress': event.progress,
                }
                if event.data:
                    if 'svg' in event.data:
                        event_data['slide'] = {
                            'page': event.data['page'],
                            'svg': event.data['svg'],
                        }
                    if 'output_path' in event.data:
                        event_data['output_path'] = event.data['output_path']
                    if 'job_id' in event.data:
                        event_data['job_id'] = event.data['job_id']
                    if 'total_slides' in event.data:
                        event_data['total_slides'] = event.data['total_slides']
                    if 'slide_count' in event.data:
                        event_data['slide_count'] = event.data['slide_count']
                    if 'pptx_filename' in event.data:
                        event_data['pptx_filename'] = event.data['pptx_filename']
                    if 'error' in event.data:
                        event_data['error'] = event.data['error']
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'ppt_svg_error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Cache-Control'] = 'no-cache'
    return response


@app.route('/api/ppt-svg/preview/<job_id>/<int:slide_num>', methods=['GET'])
def ppt_svg_preview(job_id, slide_num):
    """获取指定页的 SVG 内容"""
    import glob
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_svg_ppt', job_id)
    svg_dir = os.path.join(base_dir, 'svg_final')
    if not os.path.exists(svg_dir):
        svg_dir = os.path.join(base_dir, 'svg_output')
    if not os.path.exists(svg_dir):
        return jsonify({'error': '未找到生成结果'}), 404

    svg_files = sorted(glob.glob(os.path.join(svg_dir, '*.svg')))
    if slide_num < 1 or slide_num > len(svg_files):
        return jsonify({'error': f'页码 {slide_num} 超出范围 (1-{len(svg_files)})'}), 404

    svg_path = svg_files[slide_num - 1]
    with open(svg_path, 'r', encoding='utf-8') as f:
        svg_content = f.read()

    return jsonify({
        'job_id': job_id,
        'page': slide_num,
        'total_pages': len(svg_files),
        'svg': svg_content,
        'filename': os.path.basename(svg_path),
    })


@app.route('/api/ppt-svg/preview-all/<job_id>', methods=['GET'])
def ppt_svg_preview_all(job_id):
    """获取所有页的 SVG 内容"""
    import glob
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_svg_ppt', job_id)
    svg_dir = os.path.join(base_dir, 'svg_final')
    if not os.path.exists(svg_dir):
        svg_dir = os.path.join(base_dir, 'svg_output')
    if not os.path.exists(svg_dir):
        return jsonify({'error': '未找到生成结果'}), 404

    svg_files = sorted(glob.glob(os.path.join(svg_dir, '*.svg')))
    slides = []
    for i, svg_path in enumerate(svg_files, 1):
        with open(svg_path, 'r', encoding='utf-8') as f:
            slides.append({
                'page': i,
                'svg': f.read(),
                'filename': os.path.basename(svg_path),
            })

    return jsonify({
        'job_id': job_id,
        'total_pages': len(slides),
        'slides': slides,
    })


@app.route('/api/ppt-svg/download/<job_id>', methods=['GET'])
def ppt_svg_download(job_id):
    """下载生成的 PPTX 文件"""
    import glob
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_svg_ppt', job_id)
    exports_dir = os.path.join(base_dir, 'exports')
    if not os.path.exists(exports_dir):
        return jsonify({'error': '未找到导出文件'}), 404

    pptx_files = glob.glob(os.path.join(exports_dir, '*.pptx'))
    if not pptx_files:
        return jsonify({'error': 'PPTX 文件不存在'}), 404

    pptx_path = pptx_files[0]
    from flask import send_file
    return send_file(
        pptx_path,
        as_attachment=True,
        download_name=os.path.basename(pptx_path),
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
    )


@app.route('/api/ppt-svg/list', methods=['GET'])
def ppt_svg_list():
    """列出所有已生成的 SVG PPT"""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_svg_ppt')
    if not os.path.exists(base_dir):
        return jsonify({'jobs': []})

    jobs = []
    for job_dir in sorted(os.listdir(base_dir), reverse=True):
        meta_path = os.path.join(base_dir, job_dir, 'metadata.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            exports_dir = os.path.join(base_dir, job_dir, 'exports')
            has_pptx = os.path.exists(exports_dir) and any(
                f.endswith('.pptx') for f in os.listdir(exports_dir)
            ) if os.path.exists(exports_dir) else False
            meta['has_pptx'] = has_pptx
            jobs.append(meta)

    return jsonify({'jobs': jobs})


@app.route('/api/ppt-svg/<job_id>', methods=['DELETE'])
def ppt_svg_delete(job_id):
    """删除指定 SVG PPT 的全部输出"""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_svg_ppt')
    # 基本安全校验：job_id 不能含路径穿越字符
    if '..' in job_id or '/' in job_id or '\\' in job_id:
        return jsonify({'success': False, 'error': '非法 job_id'}), 400

    job_path = os.path.join(base_dir, job_id)
    if not os.path.exists(job_path):
        return jsonify({'success': False, 'error': '任务不存在'}), 404

    # 二次安全校验：必须确实位于 generated_svg_ppt 下
    abs_base = os.path.abspath(base_dir)
    abs_job = os.path.abspath(job_path)
    if not abs_job.startswith(abs_base):
        return jsonify({'success': False, 'error': '非法路径'}), 403

    try:
        shutil.rmtree(abs_job)
        request_logger.info(f'[PPT-SVG] 已删除任务目录: {abs_job}')
        return jsonify({'success': True, 'message': '已删除'})
    except Exception as e:
        request_logger.error(f'[PPT-SVG] 删除任务失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ppt-svg/clear-all', methods=['POST'])
def ppt_svg_clear_all():
    """清空所有 SVG PPT 历史"""
    data = request.json or {}
    confirm = data.get('confirm', False)
    if not confirm:
        return jsonify({'success': False, 'error': '需要确认清空操作'}), 400

    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_svg_ppt')
    if not os.path.exists(base_dir):
        return jsonify({'success': True, 'message': '已清空'})

    try:
        for job_id in os.listdir(base_dir):
            job_path = os.path.join(base_dir, job_id)
            abs_base = os.path.abspath(base_dir)
            abs_job = os.path.abspath(job_path)
            if abs_job.startswith(abs_base) and os.path.isdir(abs_job):
                shutil.rmtree(abs_job)
        request_logger.info('[PPT-SVG] 已清空所有 SVG PPT 历史')
        return jsonify({'success': True, 'message': '已清空'})
    except Exception as e:
        request_logger.error(f'[PPT-SVG] 清空失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== PPT 视频生成端点 ====================

@app.route('/api/ppt-video/generate', methods=['POST'])
def ppt_video_generate():
    """
    将 PPTX 文件转换为带配音和字幕的说课视频

    请求体:
    {
        "pptx_path": "PPT 文件路径（可选，默认从最新生成的 PPT 获取）",
        "topic": "视频主题（可选）",
        "voice": "配音语音（默认: mimo_default，可选: 冰糖/茉莉/苏打/白桦/Mia/Chloe/Milo/Dean）"
    }
    """
    data = request.json or {}

    # 获取 PPTX 路径
    pptx_path = data.get('pptx_path')
    topic = data.get('topic')
    voice = data.get('voice', 'mimo_default')
    tts_provider = data.get('tts_provider', '')
    tts_api_key = data.get('tts_api_key', '')
    tts_base_url = data.get('tts_base_url', '')
    tts_model = data.get('tts_model', '')

    # 如果没有指定路径，尝试获取最新生成的 PPT
    if not pptx_path:
        # 从 generated_ppt 目录获取最新的 pptx 文件
        ppt_dir = os.path.join(GENERATORS_DIR, 'generated_ppt')
        if os.path.exists(ppt_dir):
            pptx_files = [f for f in os.listdir(ppt_dir) if f.endswith('.pptx') and not f.startswith('~$')]
            if pptx_files:
                # 按修改时间排序，取最新的
                pptx_files.sort(key=lambda f: os.path.getmtime(os.path.join(ppt_dir, f)), reverse=True)
                pptx_path = os.path.join(ppt_dir, pptx_files[0])

    if not pptx_path or not os.path.exists(pptx_path):
        return jsonify({'success': False, 'error': '未找到 PPT 文件'}), 400

    # 生成 job_id（用于任务追踪）
    job_topic = topic or os.path.splitext(os.path.basename(pptx_path))[0]
    job_id = f"{datetime.now().strftime('%Y-%m-%d')}-{job_topic.replace(' ', '_').replace('/', '_')}"

    # 注册任务到追踪字典
    video_jobs[job_id] = {
        'status': 'generating',
        'progress': 0,
        'message': '准备开始...',
        'pptx_path': pptx_path,
        'voice': voice,
    }

    def _run_generation():
        """在后台线程中执行视频生成"""
        try:
            # 加载用户设置的 TTS 配置
            memory = get_memory_manager()
            config = memory.get_config()
            saved_settings = config.get('content_settings', {})
            tts_config = {
                'provider': tts_provider or saved_settings.get('tts_provider') or 'minimax-tts',
                'api_key': tts_api_key or os.environ.get('MIMO_API_KEY', ''),
                'base_url': tts_base_url or saved_settings.get('tts_base_url') or '',
                'model': tts_model or saved_settings.get('tts_model') or 'mimo-v2.5-tts',
                'voice': voice,
            }
            generator = VideoGenerator(tts_config=tts_config)

            def progress_callback(progress, message):
                if job_id in video_jobs:
                    video_jobs[job_id]['progress'] = progress
                    video_jobs[job_id]['message'] = message
                yield ""  # 占位，保持生成器格式

            result = generator.generate_video(
                pptx_path=pptx_path,
                topic=topic,
                voice=voice,
                progress_callback=progress_callback
            )

            # 消费生成器，触发实际执行
            for r in result:
                pass

            if job_id in video_jobs:
                video_jobs[job_id]['status'] = 'done'
                video_jobs[job_id]['progress'] = 1.0
                video_jobs[job_id]['message'] = '视频生成完成'

            request_logger.info(f'[PPT-VIDEO] 任务完成: {job_id}')

        except Exception as e:
            request_logger.error(f'[PPT-VIDEO] 生成失败: {e}')
            if job_id in video_jobs:
                video_jobs[job_id]['status'] = 'error'
                video_jobs[job_id]['message'] = str(e)

    # 启动后台线程，不依赖 HTTP 连接
    t = threading.Thread(target=_run_generation, daemon=True)
    t.start()

    # 立即返回 job_id，前端通过轮询获取进度
    return jsonify({'success': True, 'job_id': job_id})


@app.route('/api/ppt-video/status/<job_id>', methods=['GET'])
def ppt_video_status(job_id):
    """查询视频生成任务状态"""
    # 先查内存中的活跃任务
    if job_id in video_jobs:
        job = video_jobs[job_id]
        return jsonify({
            'status': job['status'],
            'progress': job['progress'],
            'message': job['message'],
        })

    # 内存中没有，检查磁盘上是否已完成
    video_dir = os.path.join(BACKEND_DIR, 'generated_videos', job_id)
    video_file = os.path.join(video_dir, '07-video.mp4')
    if os.path.exists(video_file):
        return jsonify({'status': 'done', 'progress': 1.0, 'message': '视频生成完成'})

    return jsonify({'status': 'not_found', 'progress': 0, 'message': '任务不存在'}), 404


@app.route('/api/ppt-video/list', methods=['GET'])
def ppt_video_list():
    """列出已生成的视频"""
    video_dir = os.path.join(BACKEND_DIR, 'generated_videos')
    if not os.path.exists(video_dir):
        return jsonify({'videos': []})

    videos = []
    for item in os.listdir(video_dir):
        item_path = os.path.join(video_dir, item)
        # 跳过临时目录与非目录
        if not os.path.isdir(item_path) or item.startswith('temp_'):
            continue
        video_file = os.path.join(item_path, '07-video.mp4')
        if os.path.exists(video_file):
            stat = os.stat(video_file)
            videos.append({
                'id': item,
                'name': item,
                'path': video_file,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            })

    videos.sort(key=lambda x: x['created'], reverse=True)
    return jsonify({'videos': videos})


@app.route('/api/ppt-video/delete', methods=['POST'])
def ppt_video_delete():
    """删除指定的视频（含整个子目录）"""
    data = request.json or {}
    video_id = data.get('id', '')

    if not video_id or '/' in video_id or '\\' in video_id or '..' in video_id:
        return jsonify({'success': False, 'error': '非法的视频 id'}), 400

    video_root = os.path.abspath(os.path.join(BACKEND_DIR, 'generated_videos'))
    target = os.path.abspath(os.path.join(video_root, video_id))
    if not target.startswith(video_root) or not os.path.isdir(target):
        return jsonify({'success': False, 'error': '视频不存在'}), 404

    try:
        shutil.rmtree(target)
        request_logger.info(f'[PPT-VIDEO] 已删除视频目录: {target}')
        return jsonify({'success': True, 'message': '视频已删除'})
    except Exception as e:
        request_logger.error(f'[PPT-VIDEO] 删除失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ppt-video/clear', methods=['POST'])
def ppt_video_clear():
    """清空所有视频"""
    data = request.json or {}
    if not data.get('confirm'):
        return jsonify({'success': False, 'error': '需要确认清空操作'}), 400

    video_root = os.path.join(BACKEND_DIR, 'generated_videos')
    if not os.path.exists(video_root):
        return jsonify({'success': True, 'deleted_count': 0})

    deleted = 0
    errors = []
    for sub in os.listdir(video_root):
        sub_path = os.path.join(video_root, sub)
        abs_sub = os.path.abspath(sub_path)
        if os.path.isdir(abs_sub) and abs_sub.startswith(os.path.abspath(video_root)):
            try:
                shutil.rmtree(abs_sub)
                deleted += 1
            except Exception as e:
                errors.append(f'{sub}: {e}')

    request_logger.info(f'[PPT-VIDEO] 已清空 {deleted} 个视频目录')
    return jsonify({'success': True, 'deleted_count': deleted, 'errors': errors})


if __name__ == '__main__':
    app_logger.info('=' * 60)
    app_logger.info('🤖 MiniMax Agent API 服务启动中...')
    app_logger.info('=' * 60)
    app_logger.info(f'📅 启动时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    app_logger.info('🌐 API 地址: http://127.0.0.1:5000')
    app_logger.info('📖 API 文档: http://127.0.0.1:5000/api/info')
    app_logger.info('❤️ 健康检查: http://127.0.0.1:5000/api/health')
    app_logger.info('📋 模式: 纯后端 API（前端由 Next.js 等框架提供）')
    app_logger.info('=' * 60)

    # 添加请求日志中间件
    @app.before_request
    def log_before_request():
        request_logger.debug(f'[BEFORE] {request.method} {request.path} - 来自 {request.remote_addr}')

    @app.after_request
    def log_after_request(response):
        request_logger.debug(f'[AFTER] {request.method} {request.path} - 状态码: {response.status_code}')
        return response

    app_logger.info('✅ 所有路由注册完成')
    app_logger.info('=' * 60)

    # use_reloader=False: 禁用 watchdog 自动重载;长时 SSE 流期间 Python stdlib 文件 mtime 抖动会触发重启,导致连接被强制中断
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
