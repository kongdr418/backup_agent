from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any


PROFILE_VERSION = 1
_SAFE_USER_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean_text(value: Any, max_length: int = 200) -> str:
    return " ".join(str(value or "").split())[:max_length]


def _clean_text_list(value: Any, max_items: int = 8) -> list[str]:
    if isinstance(value, str):
        rows = re.split(r"[+,，、/|]", value)
    elif isinstance(value, list):
        rows = value
    else:
        rows = []

    result: list[str] = []
    for row in rows:
        text = _clean_text(row, 40)
        if text and text not in result:
            result.append(text)
        if len(result) >= max_items:
            break
    return result


def _safe_collection(value: Any, fallback: Any) -> Any:
    if not isinstance(value, type(fallback)):
        return fallback
    return json.loads(json.dumps(value, ensure_ascii=False))


class LearnerProfileStorage:
    def __init__(
        self,
        backend_dir: str,
        now_provider: Callable[[], str] | None = None,
    ) -> None:
        self.memory_root = os.path.join(backend_dir, "memory", "users")
        self.now_provider = now_provider or _now_iso

    def _user_dir(self, user_id: str) -> str:
        if not _SAFE_USER_ID.fullmatch(user_id or ""):
            raise ValueError("invalid user_id")
        return os.path.join(self.memory_root, user_id)

    def _profile_path(self, user_id: str) -> str:
        return os.path.join(self._user_dir(user_id), "learner_profile.json")

    def _default_profile(self, user_id: str) -> dict[str, Any]:
        now = self.now_provider()
        return {
            "profile_version": PROFILE_VERSION,
            "user_id": user_id,
            "basic": {
                "display_name": "",
                "learning_stage": "",
                "learning_basis": "",
                "background": "",
            },
            "preferences": {
                "goal": "",
                "content_style": [],
                "preferred_difficulty": "",
                "tutoring_style": "",
            },
            "courses": {},
            "pending_updates": [],
            "recent_recommendations": [],
            "created_at": now,
            "updated_at": now,
        }

    def _normalize_profile(
        self,
        user_id: str,
        payload: dict[str, Any],
        existing: dict[str, Any] | None = None,
        touch_updated_at: bool = False,
    ) -> dict[str, Any]:
        basic = payload.get("basic") if isinstance(payload.get("basic"), dict) else {}
        preferences = (
            payload.get("preferences")
            if isinstance(payload.get("preferences"), dict)
            else {}
        )

        legacy_basis = payload.get("basis", "")
        legacy_goal = payload.get("goal", "")
        legacy_style = payload.get("style", "")
        legacy_difficulty = payload.get("difficulty", "")
        created_at = _clean_text(
            (existing or {}).get("created_at") or payload.get("created_at"),
            40,
        )
        updated_at = _clean_text(payload.get("updated_at"), 40)
        if touch_updated_at or not created_at or not updated_at:
            now = self.now_provider()
            created_at = created_at or now
            updated_at = now if touch_updated_at else (updated_at or created_at)

        return {
            "profile_version": PROFILE_VERSION,
            "user_id": user_id,
            "basic": {
                "display_name": _clean_text(basic.get("display_name"), 80),
                "learning_stage": _clean_text(basic.get("learning_stage"), 80),
                "learning_basis": _clean_text(
                    basic.get("learning_basis") or legacy_basis,
                    80,
                ),
                "background": _clean_text(basic.get("background"), 300),
            },
            "preferences": {
                "goal": _clean_text(preferences.get("goal") or legacy_goal, 120),
                "content_style": _clean_text_list(
                    preferences.get("content_style") or legacy_style
                ),
                "preferred_difficulty": _clean_text(
                    preferences.get("preferred_difficulty") or legacy_difficulty,
                    40,
                ),
                "tutoring_style": _clean_text(
                    preferences.get("tutoring_style"),
                    80,
                ),
            },
            "courses": _safe_collection(payload.get("courses"), {}),
            "pending_updates": _safe_collection(payload.get("pending_updates"), []),
            "recent_recommendations": _safe_collection(
                payload.get("recent_recommendations"),
                [],
            ),
            "created_at": created_at,
            "updated_at": updated_at,
        }

    def load_profile(self, user_id: str) -> dict[str, Any]:
        path = self._profile_path(user_id)
        if not os.path.exists(path):
            return self._default_profile(user_id)
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            return self._default_profile(user_id)
        return self._normalize_profile(user_id, payload, payload)

    def save_profile(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("profile must be an object")

        path = self._profile_path(user_id)
        existing = self.load_profile(user_id) if os.path.exists(path) else None
        profile = self._normalize_profile(
            user_id,
            payload,
            existing,
            touch_updated_at=True,
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)

        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(profile, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
        return profile

    def load_classroom_profile(self, user_id: str) -> dict[str, str]:
        profile = self.load_profile(user_id)
        basic = profile.get("basic", {})
        preferences = profile.get("preferences", {})
        content_style = preferences.get("content_style", [])
        style = "+".join(
            str(item).strip()
            for item in content_style
            if str(item).strip()
        )
        return {
            "basis": basic.get("learning_basis") or "零基础",
            "goal": preferences.get("goal") or "考试通过",
            "style": style or "图解+案例",
            "difficulty": preferences.get("preferred_difficulty") or "基础",
        }
