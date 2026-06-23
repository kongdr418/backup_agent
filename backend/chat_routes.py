from __future__ import annotations

import json
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, request


_REDACTED = "[REDACTED]"
_SENSITIVE_LOG_FIELDS = {
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "password",
    "base_url",
    "baseUrl",
}


def _redact_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (_REDACTED if key in _SENSITIVE_LOG_FIELDS else _redact_for_log(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_for_log(item) for item in value]
    return value


def create_chat_blueprint(
    *,
    get_user_id: Callable[[], str],
    get_agent: Callable[..., Any],
    get_provider_for_model: Callable[[str], tuple[str, dict | None, dict | None]],
    apply_content_llm_config: Callable[[dict], None],
    default_settings: dict,
    server_api_keys: dict,
    sessions: dict,
    logger: Any,
) -> Blueprint:
    bp = Blueprint("chat", __name__)

    @bp.route("/api/chat", methods=["POST"])
    def chat():
        logger.info("=" * 50)
        logger.info("[CHAT] 收到非流式聊天请求")
        logger.debug("[CHAT] 请求数据: %s", _redact_for_log(request.json))

        data = request.json or {}
        message = data.get("message", "").strip()
        session_id = data.get("session_id", "default")
        model = data.get("model", default_settings.get("chat_model", "MiniMax-M2.5-highspeed"))
        api_key = data.get("api_key", "")
        base_url = data.get("base_url", "")
        provider_type = data.get("provider_type", "")

        provider_id, _, _ = get_provider_for_model(model)
        if not api_key and provider_id and provider_id in server_api_keys:
            api_key = server_api_keys[provider_id]

        apply_content_llm_config(data)

        logger.info("[CHAT] session_id: %s", session_id)
        logger.info("[CHAT] model: %s", model)
        logger.info("[CHAT] has_client_api_key: %s", bool(api_key))
        logger.info(
            "[CHAT] message: %s",
            f"{message[:100]}..." if len(message) > 100 else message,
        )

        if not message:
            logger.warning("[CHAT] 消息为空，返回 400")
            return jsonify({"error": "消息不能为空"}), 400

        user_id_chat = get_user_id()
        agent = get_agent(session_id, model=model, user_id=user_id_chat)
        response = agent.chat(
            message,
            stream=False,
            model=model,
            api_key=api_key,
            base_url=base_url,
            provider_type=provider_type,
        )
        return jsonify({"response": response, "history": agent.get_history()})

    @bp.route("/api/chat/stream", methods=["POST"])
    def chat_stream():
        logger.info("=" * 50)
        logger.info("[STREAM] 收到流式聊天请求")
        logger.debug("[STREAM] 请求数据: %s", _redact_for_log(request.json))

        data = request.json or {}
        message = data.get("message", "").strip()
        session_id = data.get("session_id", "default")
        model = data.get("model", default_settings.get("chat_model", "MiniMax-M2.5-highspeed"))
        api_key = data.get("api_key", "")
        base_url = data.get("base_url", "")
        provider_type = data.get("provider_type", "")

        if not api_key:
            pid, _, _ = get_provider_for_model(model)
            if pid and pid in server_api_keys:
                api_key = server_api_keys[pid]

        apply_content_llm_config(data)

        if not message:
            logger.warning("[STREAM] 消息为空，返回 400")
            return jsonify({"error": "消息不能为空"}), 400

        user_id_chat = get_user_id()
        agent = get_agent(session_id, model=model, user_id=user_id_chat)

        def generate():
            result = agent.chat(
                message,
                stream=True,
                model=model,
                api_key=api_key,
                base_url=base_url,
                provider_type=provider_type,
            )
            if hasattr(result, "__iter__") and not isinstance(result, (str, bytes, dict)):
                chunk_count = 0
                for item in result:
                    chunk_count += 1
                    if isinstance(item, str):
                        yield f"data: {json.dumps({'chunk': item}, ensure_ascii=False)}\n\n"
                    elif isinstance(item, dict) and item.get("type", "").endswith("_complete"):
                        yield f"data: {json.dumps({'type': item.get('type'), 'data': item.get('data', {})}, ensure_ascii=False)}\n\n"
                    elif isinstance(item, dict) and item.get("type") == "video_audio_data":
                        yield f"data: {json.dumps({'type': 'video_audio_data', 'audio_base64': item.get('audio_base64', ''), 'audio_filename': item.get('audio_filename', ''), 'voiceover_text': item.get('voiceover_text', '')}, ensure_ascii=False)}\n\n"
                    elif isinstance(item, dict) and item.get("type") == "graphic_image_data":
                        yield f"data: {json.dumps({'type': 'graphic_image_data', 'image_base64': item.get('image_base64', ''), 'image_filename': item.get('image_filename', ''), 'prompt': item.get('prompt', '')}, ensure_ascii=False)}\n\n"
                    elif isinstance(item, dict) and item.get("type") == "graphic_text_data":
                        yield f"data: {json.dumps({'type': 'graphic_text_data', 'xiaohongshu': item.get('xiaohongshu', '')}, ensure_ascii=False)}\n\n"
                    elif isinstance(item, dict) and item.get("type") in {"progress", "error"}:
                        yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                    else:
                        logger.warning("[STREAM] 生成器 item %s: 未知类型 %s", chunk_count, type(item))
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            elif isinstance(result, str):
                yield f"data: {json.dumps({'chunk': result}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            else:
                for chunk in result:
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        response = Response(generate(), mimetype="text/event-stream")
        response.headers["X-Accel-Buffering"] = "no"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @bp.route("/api/clear", methods=["POST"])
    def clear_history():
        data = request.json or {}
        session_id = data.get("session_id", "default")
        if session_id in sessions:
            sessions[session_id].clear_history()
            sessions[session_id].memory.clear_session_file()
        return jsonify({"success": True, "message": "历史已清空"})

    @bp.route("/api/history", methods=["GET"])
    def get_history():
        session_id = request.args.get("session_id", "default")
        user_id_sess = get_user_id()
        agent = get_agent(session_id, user_id=user_id_sess)
        return jsonify({"history": agent.get_history()})

    return bp
