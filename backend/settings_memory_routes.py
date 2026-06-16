from __future__ import annotations

import base64
import os
from typing import Any, Callable
from urllib.parse import unquote

from flask import Blueprint, jsonify, request

from interactive_classroom.critic_service import normalize_critic_mode


def create_settings_memory_blueprint(
    *,
    get_memory_manager: Callable[[], Any],
    get_user_id: Callable[[], str],
    get_agent: Callable[..., Any],
    sessions: dict,
    default_settings: dict,
    generators_dir: str,
    logger: Any,
) -> Blueprint:
    bp = Blueprint("settings_memory", __name__)

    @bp.route("/api/settings", methods=["GET"])
    def get_settings():
        memory = get_memory_manager()
        config = memory.get_config()
        saved_settings = config.get("content_settings", {})
        settings = {**default_settings, **saved_settings}
        settings["classroom_critic_mode"] = normalize_critic_mode(
            settings.get("classroom_critic_mode")
        )
        return jsonify({
            "settings": settings,
            "options": {
                "chat_model": [
                    {"value": "MiniMax-M2.5-highspeed", "label": "MiniMax M2.5 高速"},
                ],
                "mimo_voice": [
                    {"value": "mimo_default", "label": "MiMo-默认"},
                    {"value": "default_zh", "label": "MiMo-中文女声"},
                    {"value": "default_en", "label": "MiMo-英文女声"},
                ],
                "mimo_style": [
                    {"value": "", "label": "无（默认）"},
                    {"value": "开心", "label": "开心"},
                    {"value": "悲伤", "label": "悲伤"},
                    {"value": "生气", "label": "生气"},
                    {"value": "悄悄话", "label": "悄悄话"},
                    {"value": "东北话", "label": "东北话"},
                    {"value": "四川话", "label": "四川话"},
                    {"value": "粤语", "label": "粤语"},
                ],
                "aspect_ratio": [
                    {"value": "3:4", "label": "3:4 竖图（小红书推荐）"},
                    {"value": "1:1", "label": "1:1 方图"},
                ],
                "cover_style": [
                    {"value": "infographic", "label": "一图流文字版"},
                    {"value": "minimal", "label": "极简纯图版"},
                ],
            },
        })

    @bp.route("/api/settings", methods=["POST"])
    def update_settings():
        data = request.json or {}
        new_settings = data.get("settings", {})
        if "classroom_critic_mode" in new_settings:
            new_settings["classroom_critic_mode"] = normalize_critic_mode(
                new_settings.get("classroom_critic_mode")
            )
        valid_updates = {k: v for k, v in new_settings.items() if k in default_settings}
        default_settings.update(valid_updates)
        for agent in sessions.values():
            agent.update_content_settings(default_settings)

        memory = get_memory_manager()
        config = memory.get_config()
        config.setdefault("content_settings", {}).update(new_settings)
        memory.update_config(config)
        logger.info("[SETTINGS] 设置已更新: %s", default_settings)
        return jsonify({"success": True, "settings": default_settings})

    @bp.route("/api/memory", methods=["GET"])
    def get_memory_summary_api():
        memory = get_memory_manager()
        return jsonify({"summary": memory.get_memory_summary()})

    @bp.route("/api/memory/save", methods=["POST"])
    def save_memory_api():
        data = request.json or {}
        session_id = data.get("session_id", "default")
        agent = get_agent(session_id, user_id=get_user_id())
        return jsonify({"result": agent._save_conversation_essence()})

    @bp.route("/api/memory/clear", methods=["POST"])
    def clear_memory_api():
        memory = get_memory_manager()
        memory.clear_long_term_memory()
        return jsonify({"success": True})

    @bp.route("/api/memory/clear-daily", methods=["POST"])
    def clear_daily_api():
        data = request.json or {}
        session_id = data.get("session_id", "default")
        agent = get_agent(session_id, user_id=get_user_id())
        agent.clear_history()
        agent.memory.clear_session_file()
        return jsonify({"success": True})

    @bp.route("/api/memory/search", methods=["GET"])
    def search_memory_api():
        keyword = request.args.get("keyword", "")
        memory = get_memory_manager()
        return jsonify({"results": memory.search_memory(keyword)})

    @bp.route("/api/graphic/image/<filename>", methods=["GET"])
    def get_graphic_image(filename):
        filename = unquote(filename)
        path = os.path.join(generators_dir, "generated_content", "images", filename)
        if os.path.exists(path):
            with open(path, "rb") as img:
                return jsonify({"image": base64.b64encode(img.read()).decode("utf-8")})
        return jsonify({"image": None})

    @bp.route("/api/video/audio/<filename>", methods=["GET"])
    def get_video_audio(filename):
        filename = unquote(filename)
        path = os.path.join(generators_dir, "generated_content", "audio", filename)
        if os.path.exists(path):
            with open(path, "rb") as audio:
                return jsonify({"audio": base64.b64encode(audio.read()).decode("utf-8")})
        return jsonify({"audio": None})

    return bp
