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
from minimax_agent import MiniMaxAgent
from memory_manager import MemoryManager
from learner_profile.storage import LearnerProfileStorage, PPT_LEARNING_STRATEGY_TITLE
from learner_profile.profile_agent import ProfileAgent
from learner_profile.orchestrator import ProfileOrchestrator
from learner_profile.onboarding_service import ProfileOnboardingService
from learner_profile.routes import create_learner_profile_blueprint
from generators.shared_config import content_llm_call
from chat_routes import create_chat_blueprint
from settings_memory_routes import create_settings_memory_blueprint
from provider_routes import create_provider_blueprint
from provider_registry import (
    DEFAULT_SETTINGS,
    PROVIDERS,
    SERVER_API_KEYS,
    TTS_PROVIDERS,
    _get_provider_for_model,
)
from basic_routes import create_basic_blueprint
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
from interactive_classroom.generator import InteractiveClassroomGenerator
from interactive_classroom.completion_service import ClassroomCompletionService
from interactive_classroom.generation_service import ClassroomGenerationService
from interactive_classroom.generation_jobs import ClassroomGenerationJobService
from interactive_classroom.routes import create_interactive_classroom_blueprint
from interactive_classroom.critic_service import (
    content_llm_semantic_reviewer,
    normalize_critic_mode,
)
from interactive_classroom.practice_service import ClassroomPracticeService
from interactive_classroom.runtime_service import ClassroomRuntimeService
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
    return _classroom_generation_service().classroom_from_generation_preview(
        user_id=user_id,
        request_id=request_id,
    )


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


def _classroom_generation_service() -> ClassroomGenerationService:
    return ClassroomGenerationService(
        generator=CLASSROOM_GENERATOR,
        job_service=CLASSROOM_GENERATION_JOB_SERVICE,
        classroom_storage=CLASSROOM_STORAGE,
        learner_profile_storage=LEARNER_PROFILE_STORAGE,
        profile_agent=PROFILE_AGENT,
        course_knowledge_retriever=COURSE_KNOWLEDGE_RETRIEVER,
        build_tts_config=_build_classroom_tts_config,
        apply_content_llm_config=_apply_content_llm_config,
        resolve_content_llm_request_config=_resolve_content_llm_request_config,
        resolve_critic_mode=_resolve_classroom_critic_mode,
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

app.register_blueprint(create_basic_blueprint())


app.register_blueprint(create_provider_blueprint(
    providers=PROVIDERS,
    tts_providers=TTS_PROVIDERS,
    server_api_keys=SERVER_API_KEYS,
    get_provider_for_model=_get_provider_for_model,
))

app.register_blueprint(create_chat_blueprint(
    get_user_id=get_request_user_id,
    get_agent=get_agent,
    get_provider_for_model=_get_provider_for_model,
    apply_content_llm_config=_apply_content_llm_config,
    default_settings=DEFAULT_SETTINGS,
    server_api_keys=SERVER_API_KEYS,
    sessions=sessions,
    logger=request_logger,
))

app.register_blueprint(create_settings_memory_blueprint(
    get_memory_manager=get_memory_manager,
    get_user_id=get_request_user_id,
    get_agent=get_agent,
    sessions=sessions,
    default_settings=DEFAULT_SETTINGS,
    generators_dir=GENERATORS_DIR,
    logger=request_logger,
))


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


def interactive_classroom_generate():
    payload, status = _classroom_generation_service().start_generation(
        user_id=get_request_user_id(),
        data=request.json or {},
    )
    return jsonify(payload), status


def interactive_classroom_generate_cancel():
    data = request.json or {}
    payload, status = _classroom_generation_service().cancel_generation(
        data.get('request_id')
    )
    return jsonify(payload), status


def interactive_classroom_generate_status(request_id):
    payload, status = _classroom_generation_service().get_generation_status(request_id)
    return jsonify(payload), status


def interactive_classroom_generate_stream(request_id):
    request_id = (request_id or '').strip()
    if not _is_safe_classroom_request_id(request_id):
        return jsonify({'success': False, 'error': '非法 request_id'}), 400

    job = _get_classroom_generation_job(request_id)
    if job is None:
        return jsonify({'success': False, 'error': '生成任务不存在'}), 404

    response = Response(
        _classroom_generation_service().build_stream_generator(request_id),
        mimetype='text/event-stream',
    )
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
