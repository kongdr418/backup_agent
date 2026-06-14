"""
智创空间 - 基于多智能体交互的智慧课堂平台 Web 应用
Flask 后端服务

面向中国软件杯 A3 赛题"基于大模型的个性化资源生成与学习多智能体系统开发"，
以学生为中心，通过多智能体协同完成学习画像构建、个性化资源生成与智能辅导。
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
from minimax_agent import MiniMaxAgent
from memory_manager import MemoryManager
from learner_profile.storage import LearnerProfileStorage, PPT_LEARNING_STRATEGY_TITLE
from learner_profile.profile_agent import ProfileAgent
from learner_profile.orchestrator import ProfileOrchestrator
from learner_profile.onboarding_service import ProfileOnboardingService
from learner_profile.routes import create_learner_profile_blueprint
from generators.shared_config import content_llm_call
from ppt_engine.routes import create_ppt_routes_blueprint
from course_knowledge import (
    CourseKnowledgeIngestor,
    CourseKnowledgeRetriever,
    CourseKnowledgeStorage,
    CourseVectorIndex,
    LocalEmbeddingService,
)
from course_knowledge.routes import create_course_knowledge_blueprint
from interactive_classroom.storage import ClassroomStorage
from interactive_classroom.generator import ClassroomGenerationCancelled, InteractiveClassroomGenerator
from interactive_classroom.completion_service import ClassroomCompletionService
from interactive_classroom.generation_jobs import ClassroomGenerationJobService
from interactive_classroom.routes import create_interactive_classroom_blueprint
from interactive_classroom.critic_service import (
    build_content_llm_semantic_reviewer,
    content_llm_semantic_reviewer,
    normalize_critic_mode,
)
from interactive_classroom.practice_service import ClassroomPracticeService
from interactive_classroom.runtime_service import ClassroomRuntimeService
from interactive_classroom.lineage_service import (
    inherit_classroom_lineage,
    resolve_classroom_lineage,
    safe_classroom_ref,
)
from interactive_classroom.report_service import _compact_text_key
from interactive_classroom.discussion_service import (
    generate_discussion_reply,
    generate_discussion_reply_stream,
    generate_multi_agent_discussion_reply_stream,
    generate_multi_agent_discussion_turns,
    normalize_discussion_request,
)
from file_library.routes import create_file_library_blueprint
import json
import os
import shutil
import mimetypes
import logging
import queue
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
LEARNER_PROFILE_STORAGE = LearnerProfileStorage(BACKEND_DIR)
PROFILE_AGENT = ProfileAgent()
PROFILE_ORCHESTRATOR = ProfileOrchestrator()
PROFILE_ONBOARDING_SERVICE = ProfileOnboardingService(llm_call=content_llm_call)
CLASSROOM_STORAGE = ClassroomStorage(BACKEND_DIR)
COURSE_KNOWLEDGE_STORAGE = CourseKnowledgeStorage(BACKEND_DIR)
COURSE_KNOWLEDGE_EMBEDDINGS = LocalEmbeddingService()
COURSE_KNOWLEDGE_VECTOR_INDEX = CourseVectorIndex(
    storage=COURSE_KNOWLEDGE_STORAGE,
    embedding_service=COURSE_KNOWLEDGE_EMBEDDINGS,
)
COURSE_KNOWLEDGE_INGESTOR = CourseKnowledgeIngestor(
    BACKEND_DIR,
    storage=COURSE_KNOWLEDGE_STORAGE,
    vector_index=COURSE_KNOWLEDGE_VECTOR_INDEX,
)
COURSE_KNOWLEDGE_RETRIEVER = CourseKnowledgeRetriever(
    BACKEND_DIR,
    storage=COURSE_KNOWLEDGE_STORAGE,
    vector_index=COURSE_KNOWLEDGE_VECTOR_INDEX,
)
CLASSROOM_GENERATOR = InteractiveClassroomGenerator(
    BACKEND_DIR,
    CLASSROOM_STORAGE,
    semantic_reviewer=content_llm_semantic_reviewer,
)
CLASSROOM_PRACTICE_SERVICE = ClassroomPracticeService(
    CLASSROOM_STORAGE,
    CLASSROOM_GENERATOR,
)
CLASSROOM_GENERATION_JOBS_DIR = os.path.join(BACKEND_DIR, 'memory', 'classroom_generation_jobs')
CLASSROOM_GENERATION_ORPHAN_TIMEOUT_SECONDS = 90
CLASSROOM_GENERATION_JOB_SERVICE = ClassroomGenerationJobService(
    jobs_dir=CLASSROOM_GENERATION_JOBS_DIR,
    logger=request_logger,
    orphan_timeout_seconds=CLASSROOM_GENERATION_ORPHAN_TIMEOUT_SECONDS,
)
CLASSROOM_GENERATION_CANCELS = CLASSROOM_GENERATION_JOB_SERVICE.cancels
CLASSROOM_GENERATION_JOBS = CLASSROOM_GENERATION_JOB_SERVICE.jobs
CLASSROOM_GENERATION_CANCELS_LOCK = CLASSROOM_GENERATION_JOB_SERVICE.cancels_lock


def _is_safe_classroom_request_id(value: str) -> bool:
    return CLASSROOM_GENERATION_JOB_SERVICE.is_safe_request_id(value)


def _bool_from_payload(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'y', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'n', 'off'}:
            return False
    return default


def _register_classroom_generation(request_id: str) -> threading.Event | None:
    return CLASSROOM_GENERATION_JOB_SERVICE.register(request_id)


def _classroom_generation_now() -> str:
    return CLASSROOM_GENERATION_JOB_SERVICE.now()


def _classroom_generation_job_path(request_id: str) -> str:
    return CLASSROOM_GENERATION_JOB_SERVICE._job_path(request_id)


def _write_classroom_generation_job_file(request_id: str, job: dict) -> None:
    CLASSROOM_GENERATION_JOB_SERVICE._write_job_file(request_id, job)


def _read_classroom_generation_job_file(request_id: str) -> dict | None:
    return CLASSROOM_GENERATION_JOB_SERVICE._read_job_file(request_id)


def _classroom_generation_elapsed_seconds(job: dict, now: datetime | None = None) -> int:
    return CLASSROOM_GENERATION_JOB_SERVICE.elapsed_seconds(job, now)


def _mark_orphaned_classroom_generation_locked(request_id: str, job: dict) -> dict:
    return CLASSROOM_GENERATION_JOB_SERVICE._mark_orphaned_locked(request_id, job)


def _normalize_classroom_generation_job_locked(request_id: str, job: dict) -> dict:
    return CLASSROOM_GENERATION_JOB_SERVICE._normalize_locked(request_id, job)


def _prune_classroom_generation_jobs_locked(max_jobs: int = 80) -> None:
    CLASSROOM_GENERATION_JOB_SERVICE._prune_locked(max_jobs)


def _mark_classroom_generation_running(request_id: str, topic: str) -> dict | None:
    return CLASSROOM_GENERATION_JOB_SERVICE.mark_running(request_id, topic)


def _mark_classroom_generation_done(request_id: str, classroom_id: str, classroom: dict) -> dict | None:
    return CLASSROOM_GENERATION_JOB_SERVICE.mark_done(request_id, classroom_id, classroom)


def _mark_classroom_generation_cancelled(request_id: str) -> dict | None:
    return CLASSROOM_GENERATION_JOB_SERVICE.mark_cancelled(request_id)


def _mark_classroom_generation_error(request_id: str, error: str) -> dict | None:
    return CLASSROOM_GENERATION_JOB_SERVICE.mark_error(request_id, error)


def _get_classroom_generation_job(request_id: str) -> dict | None:
    return CLASSROOM_GENERATION_JOB_SERVICE.get_job(request_id)


def _get_classroom_generation_progress_events(request_id: str) -> list[dict]:
    return CLASSROOM_GENERATION_JOB_SERVICE.get_progress_events(request_id)


def _record_classroom_generation_progress(request_id: str, event: dict) -> None:
    CLASSROOM_GENERATION_JOB_SERVICE.record_progress(request_id, event)


def _finish_classroom_generation(request_id: str) -> None:
    CLASSROOM_GENERATION_JOB_SERVICE.finish(request_id)


def _cancel_classroom_generation(request_id: str) -> bool:
    return CLASSROOM_GENERATION_JOB_SERVICE.cancel(request_id)


# ---------- SSE 订阅者 ----------

def _classroom_subscribe(request_id: str) -> queue.Queue:
    """注册一个 SSE 订阅者，返回该客户端的事件队列。"""
    return CLASSROOM_GENERATION_JOB_SERVICE.subscribe(request_id)


def _classroom_unsubscribe(request_id: str, q: queue.Queue) -> None:
    CLASSROOM_GENERATION_JOB_SERVICE.unsubscribe(request_id, q)


def _classroom_emit(request_id: str, event: dict) -> None:
    """由生成线程调用：把事件 fan-out 到所有 SSE 订阅者。"""
    CLASSROOM_GENERATION_JOB_SERVICE.emit(request_id, event)


def _classroom_close_subscribers(request_id: str) -> None:
    """终端事件后调用：往所有订阅者塞一个 None 哨兵，让 SSE 循环退出。"""
    CLASSROOM_GENERATION_JOB_SERVICE.close_subscribers(request_id)


def _classroom_from_generation_preview(user_id: str, request_id: str) -> dict | None:
    if not _is_safe_classroom_request_id(request_id):
        return None
    job = _get_classroom_generation_job(request_id)
    if not job or job.get('status') not in {'running', 'done'}:
        return None

    scenes_by_id: dict[str, dict] = {}
    for event in job.get('progress_events') or []:
        if not isinstance(event, dict):
            continue
        scene = event.get('scene_payload')
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get('id') or '').strip()
        if scene_id:
            scenes_by_id[scene_id] = scene

    scenes = sorted(
        scenes_by_id.values(),
        key=lambda row: int(row.get('order') or 0) if str(row.get('order') or '').isdigit() else 999999,
    )
    if not scenes:
        return None

    topic = str(job.get('topic') or '生成中课堂').strip() or '生成中课堂'
    return {
        'id': request_id,
        'user_id': user_id,
        'title': f'{topic}（生成中）',
        'topic': topic,
        'course': '',
        'status': 'generating',
        'created_at': job.get('started_at') or _classroom_generation_now(),
        'updated_at': job.get('updated_at') or _classroom_generation_now(),
        'tts': {},
        'student_profile': {},
        'source': {'type': 'generation_preview', 'request_id': request_id},
        'agents': [],
        'knowledge_points': [topic],
        'scenes': scenes,
    }


def _resolve_discussion_classroom(user_id: str, classroom_id: str) -> tuple[dict | None, tuple[dict, int] | None]:
    classroom_id = (classroom_id or '').strip()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return None, ({'success': False, 'error': '非法 classroom_id'}, 400)

    if _is_safe_classroom_request_id(classroom_id):
        preview_classroom = _classroom_from_generation_preview(user_id, classroom_id)
        if preview_classroom is not None:
            return preview_classroom, None

    try:
        classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    except ValueError:
        return None, ({'success': False, 'error': '非法 classroom_id'}, 400)
    if classroom is None:
        return None, ({'success': False, 'error': '课堂不存在'}, 404)
    return classroom, None


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


def _classroom_completion_service() -> ClassroomCompletionService:
    return ClassroomCompletionService(
        classroom_storage=CLASSROOM_STORAGE,
        learner_profile_storage=LEARNER_PROFILE_STORAGE,
        profile_agent=PROFILE_AGENT,
        profile_orchestrator=PROFILE_ORCHESTRATOR,
        course_knowledge_retriever=COURSE_KNOWLEDGE_RETRIEVER,
        logger=request_logger,
    )


def _classroom_runtime_service() -> ClassroomRuntimeService:
    return ClassroomRuntimeService(
        classroom_storage=CLASSROOM_STORAGE,
        learner_profile_storage=LEARNER_PROFILE_STORAGE,
        profile_agent=PROFILE_AGENT,
        course_knowledge_retriever=COURSE_KNOWLEDGE_RETRIEVER,
        practice_service=CLASSROOM_PRACTICE_SERVICE,
        completion_service=_classroom_completion_service(),
        build_tts_config=_build_classroom_tts_config,
        logger=request_logger,
    )


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
app_logger.info('智创空间 - 多智能体交互智慧课堂平台启动中...')
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


def _resolve_classroom_critic_mode(data: dict) -> str:
    """请求显式值优先，否则使用持久化的智慧课堂全局审查模式。"""
    if 'critic_mode' in data:
        return normalize_critic_mode(data.get('critic_mode'))

    default_mode = globals().get('DEFAULT_SETTINGS', {}).get(
        'classroom_critic_mode',
        'standard',
    )
    try:
        saved_settings = (
            get_memory_manager()
            .get_config()
            .get('content_settings', {})
        )
        return normalize_critic_mode(
            saved_settings.get('classroom_critic_mode', default_mode)
        )
    except Exception:
        return normalize_critic_mode(default_mode)


def _resolve_content_llm_request_config(data: dict) -> dict[str, str]:
    """解析一次请求里的 LLM 配置，并在缺 key / base_url / provider_type 时做 provider 回退。"""
    content_model = (data.get('content_model') or '').strip()
    content_api_key = data.get('content_api_key') or ''
    content_base_url = (data.get('content_base_url') or '').strip()
    content_provider_type = (data.get('content_provider_type') or '').strip()

    if content_model:
        pid, provider, _ = _get_provider_for_model(content_model)
        if not content_api_key and pid and pid in SERVER_API_KEYS:
            content_api_key = SERVER_API_KEYS[pid]
        if not content_base_url and provider:
            content_base_url = provider.get('defaultBaseUrl', '') or ''
        if not content_provider_type and provider:
            content_provider_type = provider.get('type', '') or ''

    return {
        'content_model': content_model,
        'content_api_key': content_api_key,
        'content_base_url': content_base_url,
        'content_provider_type': content_provider_type,
        'critic_mode': _resolve_classroom_critic_mode(data),
    }


app.register_blueprint(create_learner_profile_blueprint(
    get_user_id=get_request_user_id,
    get_storage=lambda: LEARNER_PROFILE_STORAGE,
    get_profile_agent=lambda: PROFILE_AGENT,
    get_onboarding_service=lambda: PROFILE_ONBOARDING_SERVICE,
    resolve_content_llm_request_config=_resolve_content_llm_request_config,
))
app.register_blueprint(create_course_knowledge_blueprint(
    get_user_id=get_request_user_id,
    get_ingestor=lambda: COURSE_KNOWLEDGE_INGESTOR,
    logger=request_logger,
))
app.register_blueprint(create_file_library_blueprint(
    get_user_id=get_request_user_id,
    backend_dir=BACKEND_DIR,
    generators_dir=GENERATORS_DIR,
    scan_dir=_scan_dir,
    logger=request_logger,
))

# ==================== 健康检查 & API 信息 ====================

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'service': 'ZhichuangSpace API',
        'version': '1.0.0',
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route('/api/info', methods=['GET'])
def api_info():
    """API 信息接口"""
    return jsonify({
        'name': 'ZhichuangSpace API',
        'version': '1.0.0',
        'description': '智创空间 - 基于多智能体交互的智慧课堂平台后端服务',
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
    provider_id, _, _ = _get_provider_for_model(model)
    if not api_key:
        if provider_id and provider_id in SERVER_API_KEYS:
            api_key = SERVER_API_KEYS[provider_id]

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

        # 检查是否是生成器/迭代器（PPT制作返回生成器：先输出大纲，再输出预览）
        if hasattr(result, '__iter__') and not isinstance(result, (str, bytes, dict)):
            request_logger.info('[STREAM] 检测到生成器/迭代器类型')
            chunk_count = 0

            for item in result:
                chunk_count += 1

                # 情况1：字符串（大纲文本或其他消息）
                if isinstance(item, str):
                    request_logger.debug(f'[STREAM] 生成器 item {chunk_count}: 字符串，长度 {len(item)}')
                    yield f"data: {json.dumps({'chunk': item}, ensure_ascii=False)}\n\n"

                # 情况2：字典（所有 *_complete 事件统一转发）
                elif isinstance(item, dict) and item.get('type', '').endswith('_complete'):
                    request_logger.info(f'[STREAM] 生成器 item {chunk_count}: 完成事件 type={item.get("type")}')
                    content_data = item.get('data', {})
                    yield f"data: {json.dumps({'type': item.get('type'), 'data': content_data}, ensure_ascii=False)}\n\n"

                # 情况3：音频数据（单独发送）- 大文件数据在流式传输中可能分割，需要特殊处理
                elif isinstance(item, dict) and item.get('type') == 'video_audio_data':
                    request_logger.info(f'[STREAM] 生成器 item {chunk_count}: 视频音频数据 (base64长度: {len(item.get("audio_base64", ""))})')
                    print(f"[DEBUG APP] 收到音频数据，准备发送，base64长度: {len(item.get('audio_base64', ''))}")
                    # 使用流式方式发送大数据，避免一次发送过多数据导致缓冲问题
                    audio_data = item.get('audio_base64', '')
                    voiceover_text = item.get('voiceover_text', '')
                    audio_filename = item.get('audio_filename', '')
                    # 分段发送音频数据
                    yield f"data: {json.dumps({'type': 'video_audio_data', 'audio_base64': audio_data, 'audio_filename': audio_filename, 'voiceover_text': voiceover_text}, ensure_ascii=False)}\n\n"

                # 情况4：图片数据（单独发送）
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
            return _verify_openai_compatible(api_key, base_url, model_id, provider_id)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def _verify_openai_compatible(api_key: str, base_url: str, model_id: str, provider_id: str = ''):
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
            if provider_id.startswith('xfyun') or 'xf-yun.com' in base_url:
                msg = '讯飞鉴权失败：请填写控制台生成的 APIpassword，或 AK:SK；同时确认当前账号已开通所选 X2/v2 接口权限。'
            else:
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
    'classroom_critic_mode': 'standard',
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
    settings['classroom_critic_mode'] = normalize_critic_mode(
        settings.get('classroom_critic_mode')
    )

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
    if 'classroom_critic_mode' in new_settings:
        new_settings['classroom_critic_mode'] = normalize_critic_mode(
            new_settings.get('classroom_critic_mode')
        )

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

def _resolve_ppt_generation_notes(data: dict, user_id: str) -> str | None:
    notes = (data.get('notes') or '').strip()
    course = (data.get('course') or '').strip()
    topic = (data.get('topic') or '').strip()

    # 注入课程知识库上下文
    try:
        knowledge_notes = COURSE_KNOWLEDGE_RETRIEVER.build_ppt_knowledge_notes(
            user_id=user_id,
            course=course,
            topic=topic,
        )
    except Exception as exc:
        request_logger.warning(
            '[PPT-NOTES] knowledge_retrieval_failed error=%s',
            type(exc).__name__,
        )
        knowledge_notes = ""
    if knowledge_notes:
        notes = '\n\n'.join(part for part in [notes, knowledge_notes] if part)

    # 默认注入学习者画像策略，确保 PPT 资源生成和课堂入口保持个性化。
    if PPT_LEARNING_STRATEGY_TITLE not in notes:
        learning_strategy = LEARNER_PROFILE_STORAGE.build_ppt_learning_strategy(user_id)
        notes = '\n\n'.join(part for part in [notes, learning_strategy] if part)
    return notes or None


app.register_blueprint(create_ppt_routes_blueprint(
    get_user_id=get_request_user_id,
    get_provider_for_model=_get_provider_for_model,
    providers=PROVIDERS,
    server_api_keys=SERVER_API_KEYS,
    bool_from_payload=_bool_from_payload,
    resolve_ppt_generation_notes=_resolve_ppt_generation_notes,
    resolve_svg_job_dir=_resolve_svg_job_dir,
    scan_dir=_scan_dir,
    backend_dir=BACKEND_DIR,
    logger=request_logger,
))


# ==================== Interactive Classroom API ====================

def _safe_classroom_ref(value: str) -> bool:
    return safe_classroom_ref(value)


def _resolve_classroom_lineage(data: dict) -> dict | None:
    return resolve_classroom_lineage(data)


def _inherit_classroom_lineage(user_id: str, lineage: dict, course: str) -> tuple[dict, str]:
    return inherit_classroom_lineage(CLASSROOM_STORAGE, user_id, lineage, course)


def interactive_classroom_generate():
    data = request.json or {}
    user_id = get_request_user_id()
    topic = (data.get('topic') or '').strip()
    course = (data.get('course') or '通用课程').strip()
    ppt_job_id = (data.get('ppt_job_id') or '').strip()
    request_id = (data.get('request_id') or '').strip()
    critic_mode = _resolve_classroom_critic_mode(data)
    lineage = _resolve_classroom_lineage(data)
    learner_profile = LEARNER_PROFILE_STORAGE.load_profile(user_id)
    student_profile = LEARNER_PROFILE_STORAGE.load_classroom_profile(user_id)
    generation_strategy = PROFILE_AGENT.build_generation_strategy(
        learner_profile,
        course,
    )

    if not topic:
        return jsonify({'success': False, 'error': 'topic 不能为空'}), 400
    if ppt_job_id and not re.match(r'^[a-zA-Z0-9_.-]{1,128}$', ppt_job_id):
        return jsonify({'success': False, 'error': '非法 ppt_job_id'}), 400
    if request_id and not _is_safe_classroom_request_id(request_id):
        return jsonify({'success': False, 'error': '非法 request_id'}), 400
    if lineage is None:
        return jsonify({'success': False, 'error': '非法课程关系参数'}), 400
    lineage, course = _inherit_classroom_lineage(user_id, lineage, course)

    if request_id:
        existing = _get_classroom_generation_job(request_id)
        if existing:
            return jsonify({'success': True, 'request_id': request_id, 'job': existing, 'status': existing.get('status')}), 202

    # 同步内容生成模型配置到 shared_config（LLM 测验生成需要）
    _apply_content_llm_config(data)
    critic_llm_config = _resolve_content_llm_request_config(data)
    semantic_reviewer = build_content_llm_semantic_reviewer(critic_llm_config)

    # 检索课程知识上下文
    try:
        knowledge_context = COURSE_KNOWLEDGE_RETRIEVER.retrieve_course_context(
            user_id=user_id,
            course=course,
            topic=topic,
        )
    except Exception as exc:
        request_logger.warning(
            '[CLASSROOM-GEN] knowledge_retrieval_failed error=%s',
            type(exc).__name__,
        )
        knowledge_context = None

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
                    generation_strategy=generation_strategy,
                    knowledge_context=knowledge_context,
                    lineage=lineage,
                    cancel_check=cancel_event.is_set if cancel_event is not None else None,
                    progress_callback=on_progress,
                    critic_mode=critic_mode,
                    semantic_reviewer=semantic_reviewer,
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
            generation_strategy=generation_strategy,
            knowledge_context=knowledge_context,
            lineage=lineage,
            cancel_check=cancel_event.is_set if cancel_event is not None else None,
            critic_mode=critic_mode,
            semantic_reviewer=semantic_reviewer,
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


def interactive_classroom_generate_status(request_id):
    request_id = (request_id or '').strip()
    if not _is_safe_classroom_request_id(request_id):
        return jsonify({'success': False, 'error': '非法 request_id'}), 400

    job = _get_classroom_generation_job(request_id)
    if job is None:
        return jsonify({'success': False, 'error': '生成任务不存在'}), 404
    return jsonify({'success': True, 'job': job})


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

        for progress_event in _get_classroom_generation_progress_events(request_id):
            yield _serialize(progress_event)

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


def interactive_classroom_list():
    user_id = get_request_user_id()
    rows = CLASSROOM_STORAGE.list_classrooms(user_id)
    return jsonify({'classrooms': rows})


def interactive_classroom_get(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    if classroom is None:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404
    classroom['answers_record'] = CLASSROOM_STORAGE.load_answers(user_id, classroom_id)
    return jsonify({'success': True, 'classroom': classroom})


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


def interactive_classroom_delete(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    ok = CLASSROOM_STORAGE.delete_classroom(user_id, classroom_id)
    if not ok:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404
    return jsonify({'success': True})


def interactive_classroom_clear():
    user_id = get_request_user_id()
    data = request.json or {}
    if not data.get('confirm'):
        return jsonify({'success': False, 'error': '需要 confirm: true'}), 400
    count = CLASSROOM_STORAGE.delete_all_classrooms(user_id)
    return jsonify({'success': True, 'deleted': count})


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

    has_short_answer = any(
        str(q.get('type', '')) == 'short_answer'
        for q in scene.get('content', {}).get('questions', [])
    )
    llm_config = _resolve_content_llm_request_config(data) if has_short_answer else None

    result = _classroom_runtime_service().submit_answer(
        user_id=user_id,
        classroom_id=classroom_id,
        classroom=classroom,
        scene=scene,
        scene_id=scene_id,
        answers=answers,
        request_data=data,
        llm_config=llm_config,
    )

    return jsonify({
        'success': True,
        **result,
    })


def interactive_classroom_report(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    if classroom is None:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404

    report = _classroom_runtime_service().build_report_for_classroom(
        user_id=user_id,
        classroom_id=classroom_id,
        classroom=classroom,
    )
    return jsonify({'success': True, 'report': report})


def interactive_classroom_create_practice(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
    data = request.get_json(silent=True) or {}
    task_id = (data.get('task_id') or '').strip()
    task_type = (data.get('task_type') or '').strip()
    if not task_id or not task_type:
        return jsonify({'success': False, 'error': 'task_id 和 task_type 不能为空'}), 400

    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    if classroom is None:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404
    try:
        practice = _classroom_runtime_service().create_practice_from_recommendation(
            user_id=user_id,
            classroom_id=classroom_id,
            classroom=classroom,
            task_id=task_id,
            task_type=task_type,
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    return jsonify({
        'success': True,
        'classroom_id': practice.get('id'),
        'classroom': practice,
    }), 201


def interactive_classroom_next_lesson_plan(classroom_id):
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    if classroom is None:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404

    data = request.json or {}
    plan = _classroom_runtime_service().build_next_lesson_plan_for_classroom(
        user_id=user_id,
        classroom_id=classroom_id,
        classroom=classroom,
        overrides=data,
    )
    return jsonify({'success': True, 'plan': plan})


# ---- P7: 学习事件 API ----

def interactive_classroom_record_event(classroom_id):
    """记录单个学习事件（scene_reviewed / recommended_task_opened / classroom_completed 等）。"""
    user_id = get_request_user_id()
    if (
        not classroom_id
        or '..' in classroom_id
        or '/' in classroom_id
        or '\\' in classroom_id
        or not re.match(r'^[a-zA-Z0-9_-]{1,128}$', classroom_id)
    ):
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    data = request.json or {}
    event_type = (data.get('event_type') or '').strip()
    scene_id = (data.get('scene_id') or '').strip()
    if not event_type:
        return jsonify({'success': False, 'error': 'event_type 不能为空'}), 400

    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    if classroom is None:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404

    extra = data.get('payload') or {}

    try:
        saved = _classroom_runtime_service().record_learning_event(
            user_id=user_id,
            classroom_id=classroom_id,
            classroom=classroom,
            event_type=event_type,
            scene_id=scene_id,
            payload=extra,
        )
        return jsonify({'success': True, 'event': saved.to_dict()})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        request_logger.exception(f'[INTERACTIVE-CLASSROOM] /event 记录失败: {exc}')
        return jsonify({'success': False, 'error': '事件记录失败'}), 500


def interactive_classroom_list_events(classroom_id):
    """列出课堂的所有学习事件，支持按 type 筛选。"""
    user_id = get_request_user_id()
    if '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id:
        return jsonify({'success': False, 'error': '非法 classroom_id'}), 400

    classroom = CLASSROOM_STORAGE.load_classroom(user_id, classroom_id)
    if classroom is None:
        return jsonify({'success': False, 'error': '课堂不存在'}), 404

    events = CLASSROOM_STORAGE.load_events(user_id, classroom_id)
    filter_type = (request.args.get('type') or '').strip()
    if filter_type:
        events = [e for e in events if e.get('type') == filter_type]

    return jsonify({'success': True, 'events': events})


def interactive_classroom_discuss(classroom_id):
    user_id = get_request_user_id()
    data = request.json or {}
    discussion, error = normalize_discussion_request(data)
    if error:
        return jsonify({'success': False, 'error': error}), 400

    classroom, error_response = _resolve_discussion_classroom(user_id, classroom_id)
    if error_response is not None:
        payload, status = error_response
        return jsonify(payload), status

    llm_config = _resolve_content_llm_request_config(data)

    if discussion['multi_agent']:
        turns = generate_multi_agent_discussion_turns(
            classroom=classroom,
            played_scene_ids=discussion['played_scene_ids'],
            conversation=discussion['messages'],
            trigger=discussion['trigger'],
            quick_action=discussion['quick_action'],
            current_scene_id=discussion['current_scene_id'],
            llm_config=llm_config,
        )
        return jsonify({
            'success': True,
            'assistant_message': turns[-1] if turns else {
                'role': 'assistant',
                'content': '',
                'trigger': discussion['trigger'],
            },
            'assistant_messages': turns,
            'auto_advance_paused': True,
        })

    reply = generate_discussion_reply(
        classroom=classroom,
        played_scene_ids=discussion['played_scene_ids'],
        conversation=discussion['messages'],
        trigger=discussion['trigger'],
        quick_action=discussion['quick_action'],
        current_scene_id=discussion['current_scene_id'],
        llm_config=llm_config,
    )
    return jsonify({
        'success': True,
        'assistant_message': {
            'role': 'assistant',
            'content': reply,
            'trigger': discussion['trigger'],
        },
        'auto_advance_paused': True,
    })


def interactive_classroom_discuss_stream(classroom_id):
    """流式讨论接口（SSE），事件格式参考 /api/chat/stream：
    data: {"chunk": "..."}\\n\\n ... data: {"done": true}\\n\\n
    """
    user_id = get_request_user_id()
    data = request.json or {}
    discussion, error = normalize_discussion_request(data)
    if error:
        return jsonify({'success': False, 'error': error}), 400

    classroom, error_response = _resolve_discussion_classroom(user_id, classroom_id)
    if error_response is not None:
        payload, status = error_response
        return jsonify(payload), status

    llm_config = _resolve_content_llm_request_config(data)

    def generate():
        try:
            if discussion['multi_agent']:
                for event in generate_multi_agent_discussion_reply_stream(
                    classroom=classroom,
                    played_scene_ids=discussion['played_scene_ids'],
                    conversation=discussion['messages'],
                    trigger=discussion['trigger'],
                    quick_action=discussion['quick_action'],
                    current_scene_id=discussion['current_scene_id'],
                    llm_config=llm_config,
                ):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            else:
                for chunk in generate_discussion_reply_stream(
                    classroom=classroom,
                    played_scene_ids=discussion['played_scene_ids'],
                    conversation=discussion['messages'],
                    trigger=discussion['trigger'],
                    quick_action=discussion['quick_action'],
                    current_scene_id=discussion['current_scene_id'],
                    llm_config=llm_config,
                ):
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'auto_advance_paused': True}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype='text/event-stream')


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


app.register_blueprint(create_interactive_classroom_blueprint({
    'generate': interactive_classroom_generate,
    'generate_cancel': interactive_classroom_generate_cancel,
    'generate_status': interactive_classroom_generate_status,
    'generate_stream': interactive_classroom_generate_stream,
    'list': interactive_classroom_list,
    'get': interactive_classroom_get,
    'update': interactive_classroom_update,
    'delete': interactive_classroom_delete,
    'clear': interactive_classroom_clear,
    'answer': interactive_classroom_answer,
    'report': interactive_classroom_report,
    'practice': interactive_classroom_create_practice,
    'next_lesson_plan': interactive_classroom_next_lesson_plan,
    'record_event': interactive_classroom_record_event,
    'list_events': interactive_classroom_list_events,
    'discuss': interactive_classroom_discuss,
    'discuss_stream': interactive_classroom_discuss_stream,
    'audio': interactive_classroom_audio,
}))


if __name__ == '__main__':
    app_logger.info('=' * 60)
    app_logger.info('🎓 智创空间 - 多智能体智慧课堂平台 API 服务启动中...')
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

    debug_enabled = os.environ.get('APP_DEBUG', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}

    # use_reloader=False: 禁用 watchdog 自动重载;长时 SSE 流期间
    # Python stdlib 文件 mtime 抖动会触发重启,导致连接被强制中断
    app.run(host='0.0.0.0', port=5000, debug=debug_enabled, use_reloader=False)
