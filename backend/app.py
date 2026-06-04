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
from interactive_classroom.storage import ClassroomStorage
from interactive_classroom.generator import ClassroomGenerationCancelled, InteractiveClassroomGenerator
from interactive_classroom.quiz_service import evaluate_quiz_scene
from interactive_classroom.report_service import build_classroom_report
from interactive_classroom.tts_service import ClassroomTTSService
import json
import os
import shutil
import mimetypes
import logging
import re
import sys
from deep_translator import GoogleTranslator
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
CLASSROOM_STORAGE = ClassroomStorage(BACKEND_DIR)
CLASSROOM_GENERATOR = InteractiveClassroomGenerator(BACKEND_DIR, CLASSROOM_STORAGE)
CLASSROOM_GENERATION_CANCELS: dict[str, threading.Event] = {}
CLASSROOM_GENERATION_JOBS: dict[str, dict] = {}
CLASSROOM_GENERATION_CANCELS_LOCK = threading.Lock()

# SSE 订阅者：每个连上的前端对应一个 queue.Queue；生成线程把事件 fan-out 给所有订阅者
import queue  # noqa: E402
CLASSROOM_GENERATION_SUBSCRIBERS: dict[str, list[queue.Queue]] = {}
CLASSROOM_GENERATION_SUBSCRIBERS_LOCK = threading.Lock()


def _is_safe_classroom_request_id(value: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9_.:-]{1,128}$', value or ''))


def _register_classroom_generation(request_id: str) -> threading.Event | None:
    if not request_id:
        return None
    with CLASSROOM_GENERATION_CANCELS_LOCK:
        event = CLASSROOM_GENERATION_CANCELS.get(request_id)
        if event is None:
            event = threading.Event()
            CLASSROOM_GENERATION_CANCELS[request_id] = event
        return event


def _classroom_generation_now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _prune_classroom_generation_jobs_locked(max_jobs: int = 80) -> None:
    if len(CLASSROOM_GENERATION_JOBS) <= max_jobs:
        return
    removable = [
        (job.get('updated_at') or job.get('started_at') or '', request_id)
        for request_id, job in CLASSROOM_GENERATION_JOBS.items()
        if job.get('status') not in {'running', 'cancelling'}
    ]
    removable.sort()
    for _, request_id in removable[:max(0, len(CLASSROOM_GENERATION_JOBS) - max_jobs)]:
        CLASSROOM_GENERATION_JOBS.pop(request_id, None)


def _mark_classroom_generation_running(request_id: str, topic: str) -> dict | None:
    if not request_id:
        return None
    now = _classroom_generation_now()
    with CLASSROOM_GENERATION_CANCELS_LOCK:
        current = CLASSROOM_GENERATION_JOBS.get(request_id, {})
        job = {
            **current,
            'request_id': request_id,
            'topic': topic,
            'status': 'running',
            'started_at': current.get('started_at') or now,
            'updated_at': now,
        }
        CLASSROOM_GENERATION_JOBS[request_id] = job
        _prune_classroom_generation_jobs_locked()
        return dict(job)


def _mark_classroom_generation_done(request_id: str, classroom_id: str, classroom: dict) -> dict | None:
    if not request_id:
        return None
    now = _classroom_generation_now()
    with CLASSROOM_GENERATION_CANCELS_LOCK:
        current = CLASSROOM_GENERATION_JOBS.get(request_id, {})
        job = {
            **current,
            'request_id': request_id,
            'status': 'done',
            'classroom_id': classroom_id,
            'classroom': classroom,
            'updated_at': now,
        }
        CLASSROOM_GENERATION_JOBS[request_id] = job
        _prune_classroom_generation_jobs_locked()
        return dict(job)


def _mark_classroom_generation_cancelled(request_id: str) -> dict | None:
    if not request_id:
        return None
    now = _classroom_generation_now()
    with CLASSROOM_GENERATION_CANCELS_LOCK:
        current = CLASSROOM_GENERATION_JOBS.get(request_id, {})
        job = {
            **current,
            'request_id': request_id,
            'status': 'cancelled',
            'updated_at': now,
            'error': '课堂生成已停止',
        }
        CLASSROOM_GENERATION_JOBS[request_id] = job
        _prune_classroom_generation_jobs_locked()
        return dict(job)


def _mark_classroom_generation_error(request_id: str, error: str) -> dict | None:
    if not request_id:
        return None
    now = _classroom_generation_now()
    with CLASSROOM_GENERATION_CANCELS_LOCK:
        current = CLASSROOM_GENERATION_JOBS.get(request_id, {})
        job = {
            **current,
            'request_id': request_id,
            'status': 'error',
            'updated_at': now,
            'error': error,
        }
        CLASSROOM_GENERATION_JOBS[request_id] = job
        _prune_classroom_generation_jobs_locked()
        return dict(job)


def _get_classroom_generation_job(request_id: str) -> dict | None:
    if not request_id:
        return None
    with CLASSROOM_GENERATION_CANCELS_LOCK:
        job = CLASSROOM_GENERATION_JOBS.get(request_id)
        return dict(job) if job else None


def _finish_classroom_generation(request_id: str) -> None:
    if not request_id:
        return
    with CLASSROOM_GENERATION_CANCELS_LOCK:
        CLASSROOM_GENERATION_CANCELS.pop(request_id, None)


def _cancel_classroom_generation(request_id: str) -> bool:
    with CLASSROOM_GENERATION_CANCELS_LOCK:
        event = CLASSROOM_GENERATION_CANCELS.get(request_id)
        if event is None:
            return False
        event.set()
        job = CLASSROOM_GENERATION_JOBS.get(request_id)
        if job and job.get('status') == 'running':
            CLASSROOM_GENERATION_JOBS[request_id] = {
                **job,
                'status': 'cancelling',
                'updated_at': _classroom_generation_now(),
            }
        return True


# ---------- SSE 订阅者 ----------

def _classroom_subscribe(request_id: str) -> queue.Queue:
    """注册一个 SSE 订阅者，返回该客户端的事件队列。"""
    q: queue.Queue = queue.Queue(maxsize=512)
    with CLASSROOM_GENERATION_SUBSCRIBERS_LOCK:
        CLASSROOM_GENERATION_SUBSCRIBERS.setdefault(request_id, []).append(q)
    return q


def _classroom_unsubscribe(request_id: str, q: queue.Queue) -> None:
    with CLASSROOM_GENERATION_SUBSCRIBERS_LOCK:
        subs = CLASSROOM_GENERATION_SUBSCRIBERS.get(request_id)
        if not subs:
            return
        if q in subs:
            subs.remove(q)
        if not subs:
            CLASSROOM_GENERATION_SUBSCRIBERS.pop(request_id, None)


def _classroom_emit(request_id: str, event: dict) -> None:
    """由生成线程调用：把事件 fan-out 到所有 SSE 订阅者。"""
    with CLASSROOM_GENERATION_SUBSCRIBERS_LOCK:
        subs = CLASSROOM_GENERATION_SUBSCRIBERS.get(request_id, [])
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                # 慢消费者：丢弃这一帧；不阻塞生成线程
                pass


def _classroom_close_subscribers(request_id: str) -> None:
    """终端事件后调用：往所有订阅者塞一个 None 哨兵，让 SSE 循环退出。"""
    with CLASSROOM_GENERATION_SUBSCRIBERS_LOCK:
        subs = CLASSROOM_GENERATION_SUBSCRIBERS.get(request_id, [])
        for q in subs:
            try:
                q.put_nowait(None)
            except queue.Full:
                pass


def _build_classroom_tts_config(data=None, classroom=None):
    data = data or {}
    classroom_tts = (classroom or {}).get('tts', {})
    memory = get_memory_manager()
    cfg = memory.get_config().get('content_settings', {})

    provider = (
        data.get('tts_provider')
        or classroom_tts.get('provider')
        or cfg.get('tts_provider')
        or 'edge-tts'
    )
    model = (
        data.get('tts_model')
        or classroom_tts.get('model')
        or cfg.get('tts_model')
        or (TTS_PROVIDERS.get(provider, {}).get('models', [{}])[0].get('id', ''))
    )
    voice = (
        data.get('tts_voice')
        or classroom_tts.get('voice')
        or cfg.get('tts_voice')
        or 'zh-CN-XiaoxiaoNeural'
    )
    api_key = data.get('tts_api_key') or cfg.get('tts_api_key') or ''
    base_url = (
        data.get('tts_base_url')
        or cfg.get('tts_base_url')
        or TTS_PROVIDERS.get(provider, {}).get('defaultBaseUrl', '')
    )

    if not api_key and provider in SERVER_API_KEYS:
        api_key = SERVER_API_KEYS[provider]

    return {
        'provider': provider,
        'api_key': api_key,
        'base_url': base_url,
        'model': model,
        'voice': voice,
    }

# 视频生成任务追踪（内存字典，job_id → 状态）
video_jobs = {}


def get_request_user_id() -> str:
    """从请求中提取 user_id，校验格式，缺省返回 'anonymous'"""
    uid = ''
    if request.is_json:
        uid = (request.json or {}).get('user_id', '')
    if not uid:
        uid = request.args.get('user_id', '')
    if not uid:
        uid = (request.form or {}).get('user_id', '')
    if uid and re.match(r'^[a-zA-Z0-9_-]{1,128}$', uid):
        return uid
    return 'anonymous'


def _scan_dir(base_dir: str, user_id: str) -> str:
    """返回用户隔离的扫描目录。anonymous 降级为旧全局目录。"""
    if user_id != 'anonymous':
        path = os.path.join(base_dir, 'users', user_id)
        os.makedirs(path, exist_ok=True)
        return path
    return base_dir


def _is_safe_job_id(value: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9_.-]{1,128}$', value or ''))


def _resolve_svg_job_dir(job_id: str, user_id: str) -> tuple[str, str]:
    """Find a generated SVG PPT job even when dev host changes user_id.

    Browser storage is isolated by host. When localhost is switched to
    127.0.0.1 to bypass a broken dev cache, the frontend may send a fresh
    user_id. For preview/editing existing jobs, fall back to global and other
    user job directories by job_id.
    """
    if not _is_safe_job_id(job_id):
        return '', user_id

    base_dir = os.path.join(BACKEND_DIR, 'generated_svg_ppt')
    candidates: list[tuple[str, str]] = []
    if user_id != 'anonymous':
        candidates.append((os.path.join(base_dir, 'users', user_id, job_id), user_id))
    candidates.append((os.path.join(base_dir, job_id), 'anonymous'))

    users_dir = os.path.join(base_dir, 'users')
    if os.path.isdir(users_dir):
        try:
            for owner_id in os.listdir(users_dir):
                if owner_id == user_id or not re.match(r'^[a-zA-Z0-9_-]{1,128}$', owner_id):
                    continue
                candidates.append((os.path.join(users_dir, owner_id, job_id), owner_id))
        except OSError:
            pass

    for path, owner_id in candidates:
        if os.path.isdir(path):
            return path, owner_id
    return '', user_id


def _user_output_dir(base_dir: str, user_id: str) -> str:
    """返回用户隔离的输出目录并自动创建。"""
    path = os.path.join(base_dir, 'users', user_id) if user_id != 'anonymous' else base_dir
    os.makedirs(path, exist_ok=True)
    return path


app = Flask(__name__)
CORS(app)

app_logger.info('=' * 60)
app_logger.info('MiniMax Agent Web 应用启动中...')
app_logger.info('=' * 60)

# API 密钥 - 从环境变量读取
API_KEY = os.environ.get('MINIMAX_API_KEY', '')

# 存储用户会话（简单实现，生产环境应使用 Redis 等）
sessions = {}


def get_agent(session_id: str, model: str = None, user_id: str = 'anonymous') -> MiniMaxAgent:
    """获取或创建 Agent 实例"""
    if session_id not in sessions:
        agent = MiniMaxAgent(API_KEY, session_id, model=model, user_id=user_id)
        sessions[session_id] = agent
    elif model and sessions[session_id].model != model:
        sessions[session_id].model = model
    return sessions[session_id]


def _apply_content_llm_config(data: dict):
    """将请求中的内容生成模型配置同步到 shared_config，使讲稿/大纲/习题等生成器使用正确模型"""
    content_model = data.get('content_model', '')
    content_api_key = data.get('content_api_key', '')
    content_base_url = data.get('content_base_url', '')
    content_provider_type = data.get('content_provider_type', '')
    # 服务端 API Key 回退
    if not content_api_key and content_model:
        pid, _, _ = _get_provider_for_model(content_model)
        if pid and pid in SERVER_API_KEYS:
            content_api_key = SERVER_API_KEYS[pid]
    if content_model or content_api_key or content_base_url or content_provider_type:
        try:
            from generators.shared_config import set_content_llm_config
            set_content_llm_config(model=content_model, api_key=content_api_key,
                                   base_url=content_base_url, provider_type=content_provider_type)
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

    # 服务端 API Key 回退
    if not api_key:
        pid, _, _ = _get_provider_for_model(model)
        if pid and pid in SERVER_API_KEYS:
            api_key = SERVER_API_KEYS[pid]

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
    user_id_chat = get_request_user_id()
    agent = get_agent(session_id, model=model, user_id=user_id_chat)

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

    # 服务端 API Key 回退
    if not api_key:
        pid, _, _ = _get_provider_for_model(model)
        if pid and pid in SERVER_API_KEYS:
            api_key = SERVER_API_KEYS[pid]

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
    user_id_chat = get_request_user_id()
    agent = get_agent(session_id, model=model, user_id=user_id_chat)

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

                # 情况8：结构化错误事件（生成器内部失败时由 _err_event 产出）
                # 修复：原先被兜底分支丢弃，导致前端收不到错误、UI 永远卡在最后一个进度
                elif isinstance(item, dict) and item.get('type') == 'error':
                    request_logger.warning(f'[STREAM] 生成器 item {chunk_count}: 错误事件 kind={item.get("kind")} message={item.get("message")}')
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

    user_id_sess = get_request_user_id()
    agent = get_agent(session_id, user_id=user_id_sess)
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


@app.route('/api/tts-test', methods=['POST'])
def tts_test():
    """实际 TTS 测试：合成语音并返回 base64 音频"""
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400
    provider_id = data.get('providerId', '')
    api_key = data.get('apiKey', '')
    base_url = data.get('baseUrl', '')
    model = data.get('model', '')
    voice = data.get('voice', '')
    text = data.get('text', '')
    if not text.strip():
        return jsonify({'success': False, 'message': '请输入测试文本'}), 400
    provider = TTS_PROVIDERS.get(provider_id)
    if not base_url and provider:
        base_url = provider.get('defaultBaseUrl', '')
    if not base_url and provider_id != 'edge-tts':
        return jsonify({'success': False, 'message': '无法确定 API 地址'}), 400
    if not api_key and provider_id in SERVER_API_KEYS:
        api_key = SERVER_API_KEYS[provider_id]
    if not api_key and provider_id not in ('edge-tts',):
        return jsonify({'success': False, 'message': '请填写 API Key'}), 400

    if provider_id in ('openai-tts', 'glm-tts'):
        try:
            url = f"{base_url.rstrip('/')}/audio/speech"
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
            payload = {
                'model': model or 'tts-1',
                'input': text,
                'voice': voice or 'alloy',
                'response_format': 'mp3',
            }
            if provider_id == 'glm-tts':
                payload['voice'] = voice or 'tongtong'
                payload['speed'] = 1.0
                payload['volume'] = 1.0
                payload['response_format'] = 'wav'
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            if resp.status_code == 200:
                import base64 as b64
                audio_b64 = b64.b64encode(resp.content).decode('utf-8')
                return jsonify({'success': True, 'audio': audio_b64, 'format': 'wav'})
            error_data = _safe_json(resp)
            msg = error_data.get('error', {}).get('message', '') or resp.text[:500]
            return jsonify({'success': False, 'message': msg})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})

    if provider_id == 'mimo-tts':
        try:
            from openai import OpenAI as OpenAIClient
            client = OpenAIClient(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model or 'mimo-v2.5-tts',
                messages=[
                    {'role': 'user', 'content': '请朗读以下内容'},
                    {'role': 'assistant', 'content': text},
                ],
                audio={'format': 'mp3', 'voice': voice or 'mimo_default'},
            )
            audio_data = response.choices[0].message.audio.data
            return jsonify({'success': True, 'audio': audio_data, 'format': 'mp3'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})

    if provider_id == 'edge-tts':
        try:
            import asyncio
            import edge_tts

            # 根据音色语言自动翻译
            voice_info = None
            if provider and voice:
                for v in provider.get('voices', []):
                    if v['id'] == voice:
                        voice_info = v
                        break

            target_lang = voice_info.get('lang', 'zh-CN') if voice_info else 'zh-CN'
            text_to_speak = text
            if target_lang != 'zh-CN':
                try:
                    text_to_speak = GoogleTranslator(source='zh-CN', target=target_lang).translate(text)
                except Exception:
                    pass  # 翻译失败则用原文

            async def _generate():
                communicate = edge_tts.Communicate(text_to_speak, voice or 'zh-CN-XiaoxiaoNeural')
                audio_buffer = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_buffer += chunk["data"]
                return audio_buffer
            audio_data = asyncio.run(_generate())
            import base64 as b64
            audio_b64 = b64.b64encode(audio_data).decode('utf-8')
            return jsonify({'success': True, 'audio': audio_b64, 'format': 'mp3'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})

    return jsonify({'success': False, 'message': f'不支持的 TTS 类型: {provider_id}'})


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
        elif provider_type == 'mimo-tts':
            return _verify_minimax_tts(api_key, base_url, model_id)
        elif provider_type == 'openai-tts':
            return _verify_openai_tts(api_key, base_url, model_id, provider_id)
        elif provider_type == 'anthropic':
            return _verify_anthropic(api_key, base_url, model_id)
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


def _verify_anthropic(api_key: str, base_url: str, model_id: str):
    """验证 Anthropic 兼容 API"""
    import requests as req
    try:
        resp = req.post(
            f"{base_url}/v1/messages",
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': model_id,
                'max_tokens': 64,
                'messages': [{'role': 'user', 'content': 'Say "OK" if you can hear me.'}],
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            text = ''
            for block in data.get('content', []):
                if block.get('type') == 'text':
                    text += block.get('text', '')
            return jsonify({
                'success': True,
                'message': '连接成功',
                'response': text.strip(),
            })
        else:
            error_str = resp.text
            if resp.status_code == 401:
                msg = 'API Key 无效或已过期'
            elif resp.status_code == 404:
                msg = '模型未找到，请检查模型 ID 或 Base URL'
            elif resp.status_code == 429:
                msg = 'API 请求频率超限，请稍后再试'
            else:
                try:
                    err = resp.json()
                    msg = err.get('error', {}).get('message', error_str)
                except Exception:
                    msg = error_str
            return jsonify({'success': False, 'message': msg})
    except req.exceptions.Timeout:
        return jsonify({'success': False, 'message': '连接超时，请检查网络或 Base URL'})
    except req.exceptions.ConnectionError:
        return jsonify({'success': False, 'message': '无法连接到 API 服务器，请检查 Base URL'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


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


def _safe_json(resp):
    """安全解析 JSON 响应，失败返回空字典"""
    try:
        return resp.json()
    except Exception:
        return {}


def _verify_openai_tts(api_key: str, base_url: str, model_id: str, provider_id: str = ''):
    """验证 OpenAI TTS / GLM TTS — /audio/speech 端点"""
    url = f"{base_url.rstrip('/')}/audio/speech"
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    voice = 'alloy'
    payload = {
        'model': model_id,
        'input': 'OK',
        'voice': voice,
        'response_format': 'mp3',
    }
    if provider_id == 'glm-tts':
        payload['voice'] = 'tongtong'
        payload['speed'] = 1.0
        payload['volume'] = 1.0
        payload['response_format'] = 'wav'
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
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
    """验证 MiniMax API (新平台 api.minimaxi.com，OpenAI 兼容)"""
    from openai import OpenAI
    # base_url 由前端传入，可能已是完整端点 /chat/completions；保证只保留 base
    if base_url.rstrip('/').endswith('/chat/completions'):
        base = base_url.rsplit('/chat/completions', 1)[0]
    else:
        base = base_url
    client = OpenAI(api_key=api_key, base_url=base, timeout=15)
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[{'role': 'user', 'content': 'Say "OK" if you can hear me.'}],
            max_tokens=64,
        )
        text = response.choices[0].message.content or ''
        if not text.strip():
            return jsonify({'success': False, 'message': '返回内容为空，请检查 API Key 或模型 ID'})
        return jsonify({'success': True, 'message': '连接成功', 'response': text.strip()})
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
    'tts_provider': 'mimo-tts',
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
    user_id = get_request_user_id()

    files = []

    # 扫描 PPT 文件
    ppt_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_ppt"), user_id)
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
                    'icon': '📊',
                    'slide_count': None,
                })

    # 扫描 SVG PPT 导出的 PPTX 文件
    svg_ppt_dir = _scan_dir(os.path.join(BACKEND_DIR, 'generated_svg_ppt'), user_id)
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
            # 读取 slide_count
            slide_count = None
            svg_final_dir = os.path.join(job_path, 'svg_final')
            if os.path.exists(svg_final_dir):
                slide_count = len([x for x in os.listdir(svg_final_dir) if x.endswith('.svg')])
            elif os.path.exists(exports_dir):
                import glob
                slide_count = len(glob.glob(os.path.join(exports_dir, '*.pptx'))) or None
            files.append({
                'id': f'svg_ppt_{job_dir}',
                'name': display_name,
                'type': 'ppt',
                'type_label': 'PPT',
                'job_id': job_dir,
                'path': filepath,
                'size': stat.st_size,
                'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                'icon': '📊',
                'slide_count': slide_count,
            })

    # 扫描讲义文件
    lecture_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_lectures"), user_id)
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
    outline_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_outlines"), user_id)
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
    speech_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_speeches"), user_id)
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
    exercise_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_exercises"), user_id)
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
    quiz_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_quizzes"), user_id)
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
    card_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_cards"), user_id)
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
    mindmap_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_mindmaps"), user_id)
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
    content_text_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_content/text"), user_id)
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
    content_audio_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_content/audio"), user_id)
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
    content_image_dir = _scan_dir(os.path.join(GENERATORS_DIR, "generated_content/images"), user_id)
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
    video_dir = _scan_dir(os.path.join(BACKEND_DIR, "generated_videos"), user_id)
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
    user_id = get_request_user_id()

    request_logger.info(f'[FILES] 重命名文件: {old_path} -> {new_name} (user: {user_id})')

    if not old_path or not os.path.exists(old_path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404

    if not new_name or '/' in new_name or '\\' in new_name:
        return jsonify({'success': False, 'error': '无效的文件名'}), 400

    # 安全检查
    allowed_dirs = [_scan_dir(os.path.join(GENERATORS_DIR, d), user_id) for d in [
        'generated_ppt', 'generated_lectures', 'generated_content',
        'generated_outlines', 'generated_speeches', 'generated_exercises',
        'generated_quizzes', 'generated_cards', 'generated_mindmaps'
    ]]
    svg_ppt_root = _scan_dir(os.path.join(BACKEND_DIR, 'generated_svg_ppt'), user_id)
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
    """清空当前用户所有生成的文件"""
    data = request.json
    confirm = data.get('confirm', False)
    user_id = get_request_user_id()

    if not confirm:
        return jsonify({'success': False, 'error': '需要确认清空操作'}), 400

    request_logger.info(f'[FILES] 收到清空文件请求 (user: {user_id})')

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
            dir_path = _scan_dir(os.path.join(BACKEND_DIR, 'generated_svg_ppt'), user_id)
        elif dir_name == 'generated_videos':
            dir_path = _scan_dir(os.path.join(BACKEND_DIR, 'generated_videos'), user_id)
        else:
            dir_path = _scan_dir(os.path.join(GENERATORS_DIR, dir_name), user_id)
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
    user_id_sess = get_request_user_id()
    agent = get_agent(session_id, user_id=user_id_sess)
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
    user_id_sess = get_request_user_id()
    agent = get_agent(session_id, user_id=user_id_sess)
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
    base_url = data.get('base_url')

    # 服务端 API Key 回退
    if not api_key:
        pid, _, _ = _get_provider_for_model(model)
        if pid and pid in SERVER_API_KEYS:
            api_key = SERVER_API_KEYS[pid]

    deep_research = data.get('deep_research', False)
    visual_critic = data.get('visual_critic', False)
    template_id = data.get('template_id')
    notes = (data.get('notes') or '').strip() or None
    user_id = get_request_user_id()

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
            base_url=base_url,
            user_id=user_id,
            language=language,
            num_slides=num_slides,
            style=style,
            detail_level=detail_level,
            deep_research=deep_research,
            visual_critic=visual_critic,
            template_id=template_id,
            notes=notes,
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
    user_id = get_request_user_id()
    base_dir, _owner_user_id = _resolve_svg_job_dir(job_id, user_id)
    if not base_dir:
        return jsonify({'error': '任务不存在'}), 404
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
    user_id = get_request_user_id()
    base_dir, _owner_user_id = _resolve_svg_job_dir(job_id, user_id)
    if not base_dir:
        return jsonify({'error': '任务不存在'}), 404
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
    user_id = get_request_user_id()
    base_dir, _owner_user_id = _resolve_svg_job_dir(job_id, user_id)
    if not base_dir:
        return jsonify({'error': '任务不存在'}), 404

    # 优先使用 PPTist 编辑后的版本
    pptist_pptx = os.path.join(base_dir, 'pptist', 'current.pptx')
    if os.path.isfile(pptist_pptx):
        from flask import send_file
        resp = send_file(
            pptist_pptx,
            as_attachment=True,
            download_name=os.path.basename(pptist_pptx),
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        )
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp

    exports_dir = os.path.join(base_dir, 'exports')
    if not os.path.exists(exports_dir):
        return jsonify({'error': '未找到导出文件'}), 404

    pptx_files = sorted(glob.glob(os.path.join(exports_dir, '*.pptx')), key=os.path.getmtime, reverse=True)
    if not pptx_files:
        return jsonify({'error': 'PPTX 文件不存在'}), 404

    # 优先返回 PPTist 导出的版本
    pptx_path = next((f for f in pptx_files if 'pptist' in os.path.basename(f).lower()), pptx_files[0])
    from flask import send_file
    resp = send_file(
        pptx_path,
        as_attachment=True,
        download_name=os.path.basename(pptx_path),
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
    )
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


@app.route('/api/ppt-svg/list', methods=['GET'])
def ppt_svg_list():
    """列出所有已生成的 SVG PPT"""
    user_id = get_request_user_id()
    base_dir = _scan_dir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_svg_ppt'), user_id)
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


@app.route('/api/pptist/preview/<job_id>/deck', methods=['GET'])
def pptist_preview_deck(job_id):
    """PPTist 编辑器加载 deck 数据"""
    import glob
    user_id = get_request_user_id()

    if '..' in job_id or '/' in job_id or '\\' in job_id:
        return jsonify({'error': '非法 job_id'}), 400

    job_dir, owner_user_id = _resolve_svg_job_dir(job_id, user_id)
    if not job_dir:
        return jsonify({'error': '任务不存在'}), 404

    # 检查是否已有保存的 deck
    deck_path = os.path.join(job_dir, 'pptist', 'deck.json')
    if os.path.exists(deck_path):
        try:
            with open(deck_path, 'r', encoding='utf-8') as f:
                deck = json.load(f)
            deck.setdefault('source', {})
            deck['source']['kind'] = 'preview'
            deck['source']['id'] = job_id
            deck['source']['saved_deck'] = True
            uid_qs = f'?user_id={owner_user_id}' if owner_user_id != 'anonymous' else ''
            deck['source']['source_pptx_url'] = f'/api/ppt-svg/download/{job_id}{uid_qs}'
            return jsonify(deck)
        except (json.JSONDecodeError, OSError):
            pass

    # 返回 blank deck，让 PPTist 通过 source_pptx_url 导入 PPTX
    uid_qs = f'?user_id={owner_user_id}' if owner_user_id != 'anonymous' else ''
    return jsonify({
        'title': os.path.basename(job_dir),
        'width': 1280,
        'height': 720,
        'theme': None,
        'slides': [],
        'source': {
            'kind': 'preview',
            'id': job_id,
            'saved_deck': False,
            'source_pptx_url': f'/api/ppt-svg/download/{job_id}{uid_qs}',
            'fallback_slides': [],
        },
    })


@app.route('/api/pptist/preview/<job_id>/deck', methods=['PUT'])
def pptist_save_deck(job_id):
    """保存 PPTist deck JSON"""
    user_id = get_request_user_id()

    if '..' in job_id or '/' in job_id or '\\' in job_id:
        return jsonify({'error': '非法 job_id'}), 400

    job_dir, _owner_user_id = _resolve_svg_job_dir(job_id, user_id)
    if not job_dir:
        return jsonify({'error': '任务不存在'}), 404

    payload = request.get_json(silent=True) or {}
    deck = {
        'title': payload.get('title', ''),
        'width': payload.get('width', 1280),
        'height': payload.get('height', 720),
        'theme': payload.get('theme'),
        'slides': payload.get('slides', []),
        'updated_at': datetime.now().isoformat(),
    }

    pptist_dir = os.path.join(job_dir, 'pptist')
    os.makedirs(pptist_dir, exist_ok=True)
    deck_path = os.path.join(pptist_dir, 'deck.json')

    try:
        with open(deck_path, 'w', encoding='utf-8') as f:
            json.dump(deck, f, ensure_ascii=False, indent=2)
        return jsonify({
            'status': 'saved',
            'slide_count': len(deck.get('slides', [])),
            'updated_at': deck['updated_at'],
        })
    except Exception as e:
        return jsonify({'error': f'保存失败: {e}'}), 500


@app.route('/api/pptist/preview/<job_id>/export', methods=['POST'])
def pptist_export_deck(job_id):
    """接收 PPTist 导出的 PPTX 文件"""
    import glob
    user_id = get_request_user_id()

    if '..' in job_id or '/' in job_id or '\\' in job_id:
        return jsonify({'error': '非法 job_id'}), 400

    job_dir, _owner_user_id = _resolve_svg_job_dir(job_id, user_id)
    if not job_dir:
        return jsonify({'error': '任务不存在'}), 404

    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400

    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.pptx'):
        return jsonify({'error': '需要 PPTX 文件'}), 400

    pptist_dir = os.path.join(job_dir, 'pptist')
    os.makedirs(pptist_dir, exist_ok=True)
    current_path = os.path.join(pptist_dir, 'current.pptx')
    file.save(current_path)

    # 同时保存到 exports 目录
    exports_dir = os.path.join(job_dir, 'exports')
    os.makedirs(exports_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    export_path = os.path.join(exports_dir, f'presentation_pptist_{timestamp}.pptx')
    shutil.copy2(current_path, export_path)

    # 更新 metadata.json 的输出路径
    meta_path = os.path.join(job_dir, 'metadata.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            meta['output_path'] = export_path
            meta['pptx_filename'] = os.path.basename(export_path)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return jsonify({
        'status': 'complete',
        'output_path': export_path,
        'slide_count': 0,
    })


@app.route('/api/ppt-svg/<job_id>', methods=['DELETE'])
def ppt_svg_delete(job_id):
    """删除指定 SVG PPT 的全部输出"""
    user_id = get_request_user_id()
    base_dir = _scan_dir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_svg_ppt'), user_id)
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
    user_id = get_request_user_id()

    base_dir = _scan_dir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_svg_ppt'), user_id)
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
    user_id = get_request_user_id()

    # 同步内容生成模型配置到 shared_config（LLM 讲稿生成需要）
    _apply_content_llm_config(data)

    # 获取 PPTX 路径
    pptx_path = data.get('pptx_path')
    topic = data.get('topic')
    tts_provider = data.get('tts_provider', '')
    voice = data.get('voice', '')
    # 根据 provider 强制使用正确音色
    default_voices = {'mimo-tts': 'mimo_default', 'openai-tts': 'alloy', 'glm-tts': 'tongtong'}
    valid_voices = {v['id'] for v in TTS_PROVIDERS.get(tts_provider, {}).get('voices', [])}
    if not voice or voice not in valid_voices:
        voice = default_voices.get(tts_provider, 'mimo_default')
    tts_api_key = data.get('tts_api_key', '')
    tts_base_url = data.get('tts_base_url', '')
    tts_model = data.get('tts_model', '')

    # 如果没有指定路径，尝试获取最新生成的 PPT
    if not pptx_path:
        # 从 generated_ppt 目录获取最新的 pptx 文件
        ppt_dir = _scan_dir(os.path.join(GENERATORS_DIR, 'generated_ppt'), user_id)
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
    tracking_key = f"{user_id}:{job_id}"
    video_jobs[tracking_key] = {
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
            # 兼容旧版本：minimax-tts → mimo-tts
            saved_tts_provider = saved_settings.get('tts_provider', '')
            if saved_tts_provider == 'minimax-tts':
                saved_tts_provider = 'mimo-tts'

            tts_config = {
                'provider': tts_provider or saved_tts_provider or 'mimo-tts',
                'api_key': tts_api_key,
                'base_url': tts_base_url or saved_settings.get('tts_base_url') or TTS_PROVIDERS.get(tts_provider, {}).get('defaultBaseUrl', ''),
                'model': tts_model or saved_settings.get('tts_model') or (TTS_PROVIDERS.get(tts_provider, {}).get('models', [{}])[0].get('id', '')),
                'voice': voice,
            }
            video_workspace = _user_output_dir(os.path.join(BACKEND_DIR, 'generated_videos'), user_id)
            generator = VideoGenerator(workspace_dir=video_workspace, tts_config=tts_config)

            def progress_callback(progress, message):
                if tracking_key in video_jobs:
                    video_jobs[tracking_key]['progress'] = progress
                    video_jobs[tracking_key]['message'] = message
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

            if tracking_key in video_jobs:
                video_jobs[tracking_key]['status'] = 'done'
                video_jobs[tracking_key]['progress'] = 1.0
                video_jobs[tracking_key]['message'] = '视频生成完成'

            request_logger.info(f'[PPT-VIDEO] 任务完成: {job_id}')

        except Exception as e:
            request_logger.error(f'[PPT-VIDEO] 生成失败: {e}')
            if tracking_key in video_jobs:
                video_jobs[tracking_key]['status'] = 'error'
                video_jobs[tracking_key]['message'] = str(e)

    # 启动后台线程，不依赖 HTTP 连接
    t = threading.Thread(target=_run_generation, daemon=True)
    t.start()

    # 立即返回 job_id，前端通过轮询获取进度
    return jsonify({'success': True, 'job_id': job_id})


@app.route('/api/ppt-video/status/<job_id>', methods=['GET'])
def ppt_video_status(job_id):
    """查询视频生成任务状态"""
    user_id = get_request_user_id()
    tracking_key = f"{user_id}:{job_id}"
    # 先查内存中的活跃任务
    if tracking_key in video_jobs:
        job = video_jobs[tracking_key]
        return jsonify({
            'status': job['status'],
            'progress': job['progress'],
            'message': job['message'],
        })

    # 内存中没有，检查磁盘上是否已完成
    video_dir = os.path.join(_scan_dir(os.path.join(BACKEND_DIR, 'generated_videos'), user_id), job_id)
    video_file = os.path.join(video_dir, '07-video.mp4')
    if os.path.exists(video_file):
        return jsonify({'status': 'done', 'progress': 1.0, 'message': '视频生成完成'})

    return jsonify({'status': 'not_found', 'progress': 0, 'message': '任务不存在'}), 404


@app.route('/api/ppt-video/list', methods=['GET'])
def ppt_video_list():
    """列出已生成的视频"""
    user_id = get_request_user_id()
    video_dir = _scan_dir(os.path.join(BACKEND_DIR, 'generated_videos'), user_id)
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
    user_id = get_request_user_id()

    if not video_id or '/' in video_id or '\\' in video_id or '..' in video_id:
        return jsonify({'success': False, 'error': '非法的视频 id'}), 400

    video_root = os.path.abspath(_scan_dir(os.path.join(BACKEND_DIR, 'generated_videos'), user_id))
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
    user_id = get_request_user_id()

    video_root = _scan_dir(os.path.join(BACKEND_DIR, 'generated_videos'), user_id)
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


# ==================== Interactive Classroom API ====================

@app.route('/api/interactive-classroom/generate', methods=['POST'])
def interactive_classroom_generate():
    data = request.json or {}
    user_id = get_request_user_id()
    topic = (data.get('topic') or '').strip()
    course = (data.get('course') or '通用课程').strip()
    ppt_job_id = (data.get('ppt_job_id') or '').strip()
    request_id = (data.get('request_id') or '').strip()
    student_profile = data.get('student_profile') if isinstance(data.get('student_profile'), dict) else {}

    if not topic:
        return jsonify({'success': False, 'error': 'topic 不能为空'}), 400
    if ppt_job_id and not re.match(r'^[a-zA-Z0-9_.-]{1,128}$', ppt_job_id):
        return jsonify({'success': False, 'error': '非法 ppt_job_id'}), 400
    if request_id and not _is_safe_classroom_request_id(request_id):
        return jsonify({'success': False, 'error': '非法 request_id'}), 400

    if request_id:
        existing = _get_classroom_generation_job(request_id)
        if existing:
            return jsonify({'success': True, 'request_id': request_id, 'job': existing, 'status': existing.get('status')}), 202

    # 同步内容生成模型配置到 shared_config（LLM 测验生成需要）
    _apply_content_llm_config(data)

    tts_config = _build_classroom_tts_config(data=data)

    cancel_event = _register_classroom_generation(request_id)
    if request_id:
        _mark_classroom_generation_running(request_id, topic)

        def run_generation_job():
            def emit(event: dict) -> None:
                _classroom_emit(request_id, event)

            def on_progress(event: dict) -> None:
                emit(event)

            try:
                payload = CLASSROOM_GENERATOR.generate(
                    user_id=user_id,
                    topic=topic,
                    course=course,
                    tts_config=tts_config,
                    ppt_job_id=ppt_job_id,
                    student_profile=student_profile,
                    cancel_check=cancel_event.is_set if cancel_event is not None else None,
                    progress_callback=on_progress,
                )
                _mark_classroom_generation_done(request_id, payload.get('id'), payload)
                emit({
                    'type': 'classroom_done',
                    'request_id': request_id,
                    'classroom_id': payload.get('id'),
                    'scene_count': len(payload.get('scenes', [])),
                })
                request_logger.info(f'[INTERACTIVE-CLASSROOM] 后台生成完成 request_id={request_id}')
            except ClassroomGenerationCancelled:
                _mark_classroom_generation_cancelled(request_id)
                emit({
                    'type': 'classroom_cancelled',
                    'request_id': request_id,
                })
                request_logger.info(f'[INTERACTIVE-CLASSROOM] 后台生成已取消 request_id={request_id}')
            except Exception as exc:
                _mark_classroom_generation_error(request_id, str(exc))
                emit({
                    'type': 'classroom_error',
                    'request_id': request_id,
                    'error': str(exc),
                })
                request_logger.exception(f'[INTERACTIVE-CLASSROOM] 后台生成失败 request_id={request_id}')
            finally:
                _classroom_close_subscribers(request_id)
                _finish_classroom_generation(request_id)

        thread = threading.Thread(target=run_generation_job, name=f'classroom-generation-{request_id}', daemon=True)
        thread.start()
        return jsonify({
            'success': True,
            'request_id': request_id,
            'status': 'running',
            'job': _get_classroom_generation_job(request_id),
        }), 202

    try:
        payload = CLASSROOM_GENERATOR.generate(
            user_id=user_id,
            topic=topic,
            course=course,
            tts_config=tts_config,
            ppt_job_id=ppt_job_id,
            student_profile=student_profile,
            cancel_check=cancel_event.is_set if cancel_event is not None else None,
        )
    except ClassroomGenerationCancelled:
        request_logger.info(f'[INTERACTIVE-CLASSROOM] 生成已取消 request_id={request_id}')
        return jsonify({'success': False, 'cancelled': True, 'error': '课堂生成已停止'}), 499
    finally:
        _finish_classroom_generation(request_id)

    return jsonify({
        'success': True,
        'classroom_id': payload.get('id'),
        'status': payload.get('status', 'ready'),
        'classroom': payload,
    })


@app.route('/api/interactive-classroom/generate/cancel', methods=['POST'])
def interactive_classroom_generate_cancel():
    data = request.json or {}
    request_id = (data.get('request_id') or '').strip()
    if not request_id:
        return jsonify({'success': False, 'error': 'request_id 不能为空'}), 400
    if not _is_safe_classroom_request_id(request_id):
        return jsonify({'success': False, 'error': '非法 request_id'}), 400

    _cancel_classroom_generation(request_id)
    request_logger.info(f'[INTERACTIVE-CLASSROOM] 收到取消请求 request_id={request_id}')
    return jsonify({'success': True, 'cancelled': True})


@app.route('/api/interactive-classroom/generate/status/<request_id>', methods=['GET'])
def interactive_classroom_generate_status(request_id):
    request_id = (request_id or '').strip()
    if not _is_safe_classroom_request_id(request_id):
        return jsonify({'success': False, 'error': '非法 request_id'}), 400

    job = _get_classroom_generation_job(request_id)
    if job is None:
        return jsonify({'success': False, 'error': '生成任务不存在'}), 404
    return jsonify({'success': True, 'job': job})


@app.route('/api/interactive-classroom/generate/stream/<request_id>', methods=['GET'])
def interactive_classroom_generate_stream(request_id):
    """SSE 课堂生成进度流。

    - 任务不存在 → 404
    - 任务已结束（done / cancelled / error）→ 立即发一条对应事件后关闭
    - 任务进行中 → 订阅事件队列，按生成线程推送顺序流式输出
    - 15s 无事件 → 发 SSE heartbeat 注释保活
    """
    request_id = (request_id or '').strip()
    if not _is_safe_classroom_request_id(request_id):
        return jsonify({'success': False, 'error': '非法 request_id'}), 400

    job = _get_classroom_generation_job(request_id)
    if job is None:
        return jsonify({'success': False, 'error': '生成任务不存在'}), 404

    from interactive_classroom.generator import GENERATION_STAGES

    def _serialize(event: dict) -> str:
        # ensure_ascii=False 让中文 step 标题/错误信息直接走 UTF-8
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    def _terminal_event_from_job(job_dict: dict) -> dict | None:
        status = job_dict.get('status')
        if status == 'done':
            return {
                'type': 'classroom_done',
                'request_id': request_id,
                'classroom_id': job_dict.get('classroom_id'),
                'scene_count': len((job_dict.get('classroom') or {}).get('scenes', [])),
            }
        if status == 'cancelled':
            return {'type': 'classroom_cancelled', 'request_id': request_id}
        if status == 'error':
            return {
                'type': 'classroom_error',
                'request_id': request_id,
                'error': job_dict.get('error') or '生成失败',
            }
        return None

    def _start_event(job_dict: dict) -> dict:
        # scene_total 在阶段 1 里才会知道；这里给个保守的占位 0 让前端知道有几个阶段
        return {
            'type': 'classroom_start',
            'request_id': request_id,
            'topic': job_dict.get('topic', ''),
            'stages': [s['key'] for s in GENERATION_STAGES],
            'stage_total': len(GENERATION_STAGES),
            'stage_labels': {s['key']: s['label'] for s in GENERATION_STAGES},
            'scene_total': 0,
        }

    terminal = _terminal_event_from_job(job)
    queue_sub: queue.Queue | None = None

    def gen():
        # 无论何种情况，先发一个 classroom_start 让前端进入"流式"状态
        yield _serialize(_start_event(job))

        if terminal is not None:
            yield _serialize(terminal)
            return

        # 任务仍在跑：订阅事件流
        nonlocal queue_sub
        queue_sub = _classroom_subscribe(request_id)
        try:
            while True:
                try:
                    event = queue_sub.get(timeout=15.0)
                except queue.Empty:
                    yield ":heartbeat\n\n"
                    continue
                if event is None:
                    return
                yield _serialize(event)
        finally:
            if queue_sub is not None:
                _classroom_unsubscribe(request_id, queue_sub)

    response = Response(gen(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # 反向代理禁用缓冲
    response.headers['Connection'] = 'keep-alive'
    return response


@app.route('/api/interactive-classroom/list', methods=['GET'])
def interactive_classroom_list():
    user_id = get_request_user_id()
    rows = CLASSROOM_STORAGE.list_classrooms(user_id)
    return jsonify({'classrooms': rows})


@app.route('/api/interactive-classroom/<classroom_id>', methods=['GET'])
def interactive_classroom_get(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    if classroom is None:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404
    return jsonify({'success': True, 'classroom': classroom})


@app.route('/api/interactive-classroom/<classroom_id>', methods=['PATCH'])
def interactive_classroom_update(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    data = request.json or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'success': False, 'error': 'title 不能为空'}), 400

    ok = CLASSROOM_STORAGE.rename_classroom(user_id, classroom_id, title)
    if not ok:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404
    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    return jsonify({'success': True, 'classroom': classroom})


@app.route('/api/interactive-classroom/<classroom_id>', methods=['DELETE'])
def interactive_classroom_delete(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    ok = CLASSROOM_STORAGE.delete_classroom(user_id, classroom_id)
    if not ok:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404
    return jsonify({'success': True})


@app.route('/api/interactive-classroom/<classroom_id>/answer', methods=['POST'])
def interactive_classroom_answer(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    data = request.json or {}
    scene_id = (data.get('scene_id') or '').strip()
    answers = data.get('answers') or {}
    if not scene_id or not isinstance(answers, dict):
        return jsonify({'success': False, 'error': 'scene_id 或 answers 非法'}), 400

    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    if classroom is None:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404

    scene = next((s for s in classroom.get('scenes', []) if s.get('id') == scene_id), None)
    if scene is None or scene.get('type') != 'quiz':
        return jsonify({'success': False, 'error': 'quiz scene 不存在'}), 404

    eval_result = evaluate_quiz_scene(scene, answers)
    CLASSROOM_STORAGE.save_answers(
        user_id=user_id,
        classroom_id=classroom_id,
        scene_id=scene_id,
        answers_payload={'answers': answers, 'evaluation': eval_result},
    )

    feedback_action = {
        'id': f'feedback_{scene_id}',
        'type': 'quiz_feedback',
        'agent_id': 'teacher',
        'text': eval_result.get('feedback_text', ''),
        'audio_url': '',
    }

    feedback_text = feedback_action['text']
    if feedback_text:
        try:
            audio_dir = CLASSROOM_STORAGE.audio_dir(user_id, classroom_id)
            tts = ClassroomTTSService(
                output_dir=audio_dir,
                tts_config=_build_classroom_tts_config(data=data, classroom=classroom),
            )
            filename = tts.synthesize_action(feedback_action['id'], feedback_text, audio_dir)
            if filename:
                feedback_action['audio_url'] = (
                    f'/api/interactive-classroom/{classroom_id}/audio/{filename}'
                )
        except Exception:
            feedback_action['audio_url'] = ''

    return jsonify({
        'success': True,
        'score': eval_result.get('score', 0),
        'correct': eval_result.get('correct', 0),
        'total': eval_result.get('total', 0),
        'earned_points': eval_result.get('earned_points', 0),
        'total_points': eval_result.get('total_points', 0),
        'results': eval_result.get('results', []),
        'feedback_action': feedback_action,
    })


@app.route('/api/interactive-classroom/<classroom_id>/report', methods=['GET'])
def interactive_classroom_report(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    if classroom is None:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404

    answers = CLASSROOM_STORAGE.load_answers(user_id, classroom_id)
    report = build_classroom_report(classroom, answers)
    CLASSROOM_STORAGE.save_report(user_id, classroom_id, report)
    return jsonify({'success': True, 'report': report})


@app.route('/api/interactive-classroom/<classroom_id>/audio/<filename>', methods=['GET'])
def interactive_classroom_audio(classroom_id, filename):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'success': False, 'error': '非法 filename'}), 400

    audio_path = os.path.join(
        BACKEND_DIR,
        'memory',
        'users',
        user_id,
        'interactive_classrooms',
        classroom_id,
        'audio',
        filename,
    )
    if not os.path.exists(audio_path):
        return jsonify({'success': False, 'error': '音频不存在'}), 404

    from flask import send_file
    guessed_type, _ = mimetypes.guess_type(audio_path)
    return send_file(audio_path, mimetype=guessed_type or 'application/octet-stream')


# ==================== Templates API ====================

@app.route('/api/templates/list', methods=['GET'])
def templates_list():
    """List all installed built-in templates."""
    try:
        from ppt_engine.template_manager import list_templates
        templates = list_templates()
        return jsonify({
            'templates': [
                {
                    'template_id': t.template_id,
                    'label': t.label,
                    'summary': t.summary,
                    'tone': t.tone,
                    'theme_mode': t.theme_mode,
                    'category': t.category,
                    'keywords': t.keywords,
                    'slide_count': t.slide_count,
                }
                for t in templates
            ]
        })
    except Exception as e:
        app_logger.error(f'[TEMPLATES] 列表加载失败: {e}')
        return jsonify({'templates': []})


@app.route('/api/templates/preview/<template_id>', methods=['GET'])
def template_preview(template_id):
    """Return all page SVGs of a built-in template."""
    try:
        from ppt_engine.template_manager import load_template
        tmpl = load_template(template_id)
        if tmpl is None:
            return jsonify({'pages': {}, 'label': ''})
        pages = {}
        if tmpl.cover_svg:
            pages['cover'] = tmpl.cover_svg
        if tmpl.chapter_svg:
            pages['chapter'] = tmpl.chapter_svg
        if tmpl.content_svg:
            pages['content'] = tmpl.content_svg
        if tmpl.ending_svg:
            pages['ending'] = tmpl.ending_svg
        if tmpl.toc_svg:
            pages['toc'] = tmpl.toc_svg
        return jsonify({'pages': pages, 'label': tmpl.info.label})
    except Exception as e:
        app_logger.error(f'[TEMPLATES] 预览加载失败: {e}')
        return jsonify({'pages': {}, 'label': ''})


if __name__ == '__main__':
    app_logger.info('=' * 60)
    app_logger.info('🤖 MiniMax Agent API 服务启动中...')
    app_logger.info('=' * 60)
    app_logger.info(f'📅 启动时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    app_logger.info('🌐 API 地址: http://127.0.0.1:5000')

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

    # use_reloader=False: 禁用 watchdog 自动重载;长时 SSE 流期间
    # Python stdlib 文件 mtime 抖动会触发重启,导致连接被强制中断
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
