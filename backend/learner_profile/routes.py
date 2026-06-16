from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, request


def create_learner_profile_blueprint(
    *,
    get_user_id: Callable[[], str],
    get_storage: Callable[[], Any],
    get_profile_agent: Callable[[], Any],
    get_onboarding_service: Callable[[], Any],
    resolve_content_llm_request_config: Callable[[dict], dict[str, str]],
) -> Blueprint:
    """Create learner-profile routes with late-bound app dependencies."""

    bp = Blueprint("learner_profile", __name__, url_prefix="/api/learner-profile")

    @bp.get("")
    def get_learner_profile():
        user_id = get_user_id()
        profile = get_storage().load_profile(user_id)
        return jsonify({"success": True, "profile": profile})

    @bp.put("")
    def update_learner_profile():
        user_id = get_user_id()
        data = request.get_json(silent=True) or {}
        profile = data.get("profile")
        if not isinstance(profile, dict):
            return jsonify({"success": False, "error": "profile must be an object"}), 400

        saved_profile = get_storage().save_manual_profile(user_id, profile)
        return jsonify({"success": True, "profile": saved_profile})

    @bp.post("/onboarding/message")
    def learner_profile_onboarding_message():
        user_id = get_user_id()
        data = request.get_json(silent=True) or {}
        messages = data.get("messages", [])
        if not isinstance(messages, list) or any(
            not isinstance(item, dict)
            or item.get("role") not in {"user", "assistant"}
            or not isinstance(item.get("content"), str)
            for item in messages
        ):
            return jsonify({"success": False, "error": "messages must be a conversation list"}), 400

        request_config = resolve_content_llm_request_config(data)
        llm_config = {
            "model": request_config.get("content_model", ""),
            "api_key": request_config.get("content_api_key", ""),
            "base_url": request_config.get("content_base_url", ""),
            "provider_type": request_config.get("content_provider_type", ""),
        }
        draft = data.get("draft")
        profile = draft if isinstance(draft, dict) else get_storage().load_profile(user_id)
        result = get_onboarding_service().advance(
            profile=profile,
            messages=messages[-20:],
            llm_config=llm_config,
        )
        return jsonify({"success": True, **result})

    @bp.get("/strategy")
    def get_learner_profile_strategy():
        user_id = get_user_id()
        course = (request.args.get("course") or "通用课程").strip() or "通用课程"
        profile = get_storage().load_profile(user_id)
        strategy = get_profile_agent().build_generation_strategy(profile, course)
        return jsonify({"success": True, "generation_strategy": strategy})

    @bp.patch("/updates/<update_id>")
    def resolve_learner_profile_update(update_id):
        user_id = get_user_id()
        data = request.get_json(silent=True) or {}
        action = (data.get("action") or "").strip()
        try:
            profile = get_storage().resolve_pending_update(
                user_id,
                update_id,
                action=action,
                modified_after=data.get("after"),
            )
        except KeyError:
            return jsonify({"success": False, "error": "画像更新建议不存在"}), 404
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        return jsonify({"success": True, "profile": profile})

    return bp
