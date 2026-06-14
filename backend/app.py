"""
智创空间 - 基于多智能体交互的智慧课堂平台 Web 应用
Flask 后端服务

面向中国软件杯 A3 赛题"基于大模型的个性化资源生成与学习多智能体系统开发"，
以学生为中心，通过多智能体协同完成学习画像构建、个性化资源生成与智能辅导。
"""

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request
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
from file_library.routes import create_file_library_blueprint
import os
import logging
import re
import sys
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

app.register_blueprint(create_interactive_classroom_blueprint(
    get_user_id=get_request_user_id,
    get_storage=lambda: CLASSROOM_STORAGE,
    get_generation_service=_classroom_generation_service,
    get_runtime_service=_classroom_runtime_service,
    resolve_content_llm_request_config=_resolve_content_llm_request_config,
    backend_dir=BACKEND_DIR,
    logger=request_logger,
))

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
