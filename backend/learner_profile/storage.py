from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .schemas import (
    PROFILE_VERSION,
    default_global_traits,
    normalize_courses,
    normalize_global_traits,
)

_SAFE_USER_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
PPT_LEARNING_STRATEGY_TITLE = "【学习者画像教学策略】"


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
        self._lock = threading.RLock()

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
            "global_traits": default_global_traits(),
            "courses": {},
            "pending_updates": [],
            "recent_recommendations": [],
            "update_history": [],
            "evidence_buffer": {},
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
            "global_traits": normalize_global_traits(payload.get("global_traits")),
            "courses": normalize_courses(payload.get("courses"), updated_at),
            "pending_updates": _safe_collection(payload.get("pending_updates"), []),
            "recent_recommendations": _safe_collection(
                payload.get("recent_recommendations"),
                [],
            ),
            "update_history": _safe_collection(payload.get("update_history"), []),
            "evidence_buffer": _safe_collection(payload.get("evidence_buffer"), {}),
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

        with self._lock:
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

    def save_manual_profile(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("profile must be an object")
        with self._lock:
            existing = self.load_profile(user_id)
            merged = {
                **existing,
                "basic": (
                    payload.get("basic")
                    if isinstance(payload.get("basic"), dict)
                    else existing.get("basic", {})
                ),
                "preferences": (
                    payload.get("preferences")
                    if isinstance(payload.get("preferences"), dict)
                    else existing.get("preferences", {})
                ),
                "global_traits": (
                    payload.get("global_traits")
                    if isinstance(payload.get("global_traits"), dict)
                    else existing.get("global_traits", default_global_traits())
                ),
            }
            for key in (
                "courses",
                "pending_updates",
                "recent_recommendations",
                "update_history",
                "evidence_buffer",
            ):
                if key in payload:
                    merged[key] = payload[key]
            for key in ("basis", "goal", "style", "difficulty"):
                if key in payload:
                    merged[key] = payload[key]
            return self.save_profile(user_id, merged)

    def add_pending_updates(
        self,
        user_id: str,
        proposals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            profile = self.load_profile(user_id)
            pending = profile.setdefault("pending_updates", [])
            existing_ids = {
                str(item.get("id"))
                for item in pending
                if isinstance(item, dict) and item.get("id")
            }
            for proposal in proposals:
                if not isinstance(proposal, dict):
                    continue
                proposal_id = _clean_text(proposal.get("id"), 80)
                if not proposal_id or proposal_id in existing_ids:
                    continue
                course_id = _clean_text(proposal.get("course_id"), 80)
                point_id = _clean_text(proposal.get("knowledge_point_id"), 80)
                if course_id and point_id:
                    for existing in pending:
                        if (
                            isinstance(existing, dict)
                            and existing.get("status") == "pending"
                            and existing.get("course_id") == course_id
                            and existing.get("knowledge_point_id") == point_id
                        ):
                            existing["status"] = "superseded"
                            existing["superseded_by"] = proposal_id
                            existing["resolved_at"] = self.now_provider()
                row = json.loads(json.dumps(proposal, ensure_ascii=False))
                row["id"] = proposal_id
                row["status"] = "pending"
                pending.append(row)
                existing_ids.add(proposal_id)
            return self.save_profile(user_id, profile)

    def resolve_pending_update(
        self,
        user_id: str,
        update_id: str,
        action: str,
        modified_after: Any | None = None,
    ) -> dict[str, Any]:
        if action not in {"accept", "modify", "ignore"}:
            raise ValueError("invalid action")
        with self._lock:
            profile = self.load_profile(user_id)
            pending = profile.setdefault("pending_updates", [])
            proposal = next(
                (
                    item
                    for item in pending
                    if isinstance(item, dict) and item.get("id") == update_id
                ),
                None,
            )
            if proposal is None:
                raise KeyError("update not found")
            if proposal.get("status") != "pending":
                return profile

            now = self.now_provider()
            if action == "ignore":
                proposal["status"] = "ignored"
                proposal["resolved_at"] = now
                return self.save_profile(user_id, profile)

            proposal_type = _clean_text(proposal.get("type"), 80)
            if proposal_type != "mastery_adjustment":
                applied_value = (
                    modified_after
                    if action == "modify"
                    else proposal.get("after")
                )
                if applied_value is None:
                    raise ValueError("proposal is missing after value")
                self._apply_trait_update(profile, proposal, applied_value, now)
                proposal["status"] = "modified" if action == "modify" else "accepted"
                proposal["applied_after"] = json.loads(
                    json.dumps(applied_value, ensure_ascii=False)
                )
                proposal["resolved_at"] = now
                self._append_update_history(
                    profile,
                    proposal,
                    action,
                    applied_value,
                    now,
                )
                return self.save_profile(user_id, profile)

            if action == "modify":
                if modified_after is None:
                    raise ValueError("modified_after is required")
                score = float(modified_after)
                if score < 0 or score > 100:
                    raise ValueError("modified_after must be between 0 and 100")

            applied_score = int(
                round(
                    float(
                        modified_after
                        if action == "modify"
                        else proposal.get("after", proposal.get("before", 50))
                    )
                )
            )
            course_id = _clean_text(proposal.get("course_id"), 80)
            point_id = _clean_text(proposal.get("knowledge_point_id"), 80)
            if not course_id or not point_id:
                raise ValueError("proposal is missing course or knowledge point")

            courses = profile.setdefault("courses", {})
            course = courses.setdefault(
                course_id,
                {
                    "course_id": course_id,
                    "course_name": _clean_text(proposal.get("course_name"), 120),
                    "mastery": {},
                    "strong_points": [],
                    "weak_points": [],
                    "recent_trend": "stable",
                    "last_classroom_id": "",
                    "updated_at": now,
                },
            )
            mastery = course.setdefault("mastery", {})
            existing = mastery.get(point_id) if isinstance(mastery.get(point_id), dict) else {}
            evidence_ids = list(
                dict.fromkeys(
                    [
                        *existing.get("evidence_ids", []),
                        *proposal.get("evidence_ids", []),
                    ]
                )
            )
            recent_scores = [
                int(round(float(value)))
                for value in existing.get("recent_scores", [])
                if isinstance(value, (int, float))
            ]
            recent_scores.append(applied_score)
            recent_scores = recent_scores[-8:]
            mastery[point_id] = {
                "name": _clean_text(proposal.get("knowledge_point_name"), 80),
                "parent_name": _clean_text(proposal.get("parent_name"), 80),
                "score": applied_score,
                "confidence": max(
                    0.0,
                    min(1.0, float(proposal.get("confidence", 0.5) or 0.5)),
                ),
                "evidence_count": len(evidence_ids),
                "evidence_ids": evidence_ids,
                "recent_scores": recent_scores,
                "updated_at": now,
            }
            all_rows = [
                row
                for row in mastery.values()
                if isinstance(row, dict) and _clean_text(row.get("name"), 80)
            ]
            course["weak_points"] = [
                row["name"]
                for row in sorted(all_rows, key=lambda item: float(item.get("score", 0)))
                if float(row.get("score", 0) or 0) < 65
            ][:5]
            course["strong_points"] = [
                row["name"]
                for row in sorted(
                    all_rows,
                    key=lambda item: float(item.get("score", 0)),
                    reverse=True,
                )
                if float(row.get("score", 0) or 0) >= 80
            ][:5]
            if len(recent_scores) >= 2:
                delta = recent_scores[-1] - recent_scores[-2]
                course["recent_trend"] = (
                    "improving" if delta > 5 else "declining" if delta < -5 else "stable"
                )
            else:
                course["recent_trend"] = course.get("recent_trend") or "stable"
            course["last_classroom_id"] = _clean_text(
                proposal.get("classroom_id"),
                128,
            )
            course["updated_at"] = now

            proposal["status"] = "modified" if action == "modify" else "accepted"
            proposal["applied_after"] = applied_score
            proposal["resolved_at"] = now
            history = profile.setdefault("update_history", [])
            history.append(
                {
                    "update_id": update_id,
                    "course_id": course_id,
                    "knowledge_point_id": point_id,
                    "before": proposal.get("before"),
                    "after": applied_score,
                    "action": action,
                    "evidence_ids": proposal.get("evidence_ids", []),
                    "reason": proposal.get("reason", ""),
                    "resolved_at": now,
                }
            )
            profile["update_history"] = history[-100:]
            evidence_buffer = profile.setdefault("evidence_buffer", {})
            course_buffer = evidence_buffer.get(course_id)
            if isinstance(course_buffer, dict):
                course_buffer.pop(point_id, None)
                if not course_buffer:
                    evidence_buffer.pop(course_id, None)
            return self.save_profile(user_id, profile)

    def _apply_trait_update(
        self,
        profile: dict[str, Any],
        proposal: dict[str, Any],
        applied_value: Any,
        now: str,
    ) -> None:
        proposal_type = _clean_text(proposal.get("type"), 80)
        trait_key = _clean_text(proposal.get("trait_key"), 120)
        value = json.loads(json.dumps(applied_value, ensure_ascii=False))
        if isinstance(value, dict):
            value["status"] = "confirmed"
            value["updated_at"] = now
            value.setdefault("confidence", proposal.get("confidence", 0.5))
            value.setdefault("evidence_ids", proposal.get("evidence_ids", []))

        if proposal_type == "cognitive_preference_update":
            if not trait_key:
                raise ValueError("proposal is missing trait_key")
            traits = profile.setdefault("global_traits", default_global_traits())
            traits.setdefault("cognitive_preferences", {})[trait_key] = value
            return

        if proposal_type == "interest_direction_update":
            traits = profile.setdefault("global_traits", default_global_traits())
            interests = traits.setdefault("interest_directions", [])
            label = _clean_text(
                value.get("label") if isinstance(value, dict) else trait_key,
                120,
            )
            interests[:] = [
                row
                for row in interests
                if not isinstance(row, dict) or _clean_text(row.get("label"), 120) != label
            ]
            if isinstance(value, dict):
                interests.append(value)
            return

        course_id = _clean_text(proposal.get("course_id"), 80)
        if not course_id:
            raise ValueError("proposal is missing course")
        courses = profile.setdefault("courses", {})
        course = courses.setdefault(
            course_id,
            normalize_courses(
                {
                    course_id: {
                        "course_id": course_id,
                        "course_name": _clean_text(proposal.get("course_name"), 120),
                    }
                },
                now,
            )[course_id],
        )
        if proposal_type == "error_pattern_update":
            if not trait_key:
                raise ValueError("proposal is missing trait_key")
            course.setdefault("error_patterns", {})[trait_key] = value
        elif proposal_type == "transfer_ability_update":
            course["transfer_ability"] = value
        else:
            raise ValueError("unsupported profile update type")
        course["updated_at"] = now

    def _append_update_history(
        self,
        profile: dict[str, Any],
        proposal: dict[str, Any],
        action: str,
        applied_value: Any,
        now: str,
    ) -> None:
        history = profile.setdefault("update_history", [])
        history.append(
            {
                "update_id": proposal.get("id"),
                "type": proposal.get("type"),
                "scope": proposal.get("scope"),
                "course_id": proposal.get("course_id", ""),
                "trait_key": proposal.get("trait_key", ""),
                "before": proposal.get("before"),
                "after": json.loads(json.dumps(applied_value, ensure_ascii=False)),
                "action": action,
                "evidence_ids": proposal.get("evidence_ids", []),
                "reason": proposal.get("reason", ""),
                "resolved_at": now,
            }
        )
        profile["update_history"] = history[-100:]

    def accumulate_evidence(
        self,
        user_id: str,
        observations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            profile = self.load_profile(user_id)
            buffer = profile.setdefault("evidence_buffer", {})
            for observation in observations:
                if not isinstance(observation, dict):
                    continue
                course_id = _clean_text(observation.get("course_id"), 80)
                point_id = _clean_text(observation.get("knowledge_point_id"), 80)
                source_id = _clean_text(observation.get("source_id"), 180)
                if not course_id or not point_id or not source_id:
                    continue
                course_buffer = buffer.setdefault(course_id, {})
                point_buffer = course_buffer.setdefault(
                    point_id,
                    {
                        "course_name": _clean_text(
                            observation.get("course_name"),
                            120,
                        ),
                        "knowledge_point_name": _clean_text(
                            observation.get("knowledge_point_name"),
                            80,
                        ),
                        "parent_name": _clean_text(
                            observation.get("parent_name"),
                            80,
                        ),
                        "observations": [],
                    },
                )
                rows = point_buffer.setdefault("observations", [])
                if any(
                    isinstance(row, dict) and row.get("source_id") == source_id
                    for row in rows
                ):
                    continue
                rows.append(json.loads(json.dumps(observation, ensure_ascii=False)))
                point_buffer["observations"] = rows[-20:]
            return self.save_profile(user_id, profile)

    def record_recommendations(
        self,
        user_id: str,
        classroom_id: str,
        course_id: str,
        recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            profile = self.load_profile(user_id)
            existing = [
                row
                for row in profile.get("recent_recommendations", [])
                if isinstance(row, dict)
                and row.get("classroom_id") != classroom_id
            ]
            now = self.now_provider()
            for recommendation in recommendations:
                if not isinstance(recommendation, dict):
                    continue
                existing.append(
                    {
                        **json.loads(json.dumps(recommendation, ensure_ascii=False)),
                        "classroom_id": classroom_id,
                        "course_id": course_id,
                        "created_at": now,
                    }
                )
            profile["recent_recommendations"] = existing[-20:]
            return self.save_profile(user_id, profile)

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

    def build_ppt_learning_strategy(self, user_id: str) -> str:
        profile = self.load_profile(user_id)
        basic = profile.get("basic", {})
        preferences = profile.get("preferences", {})
        content_style = preferences.get("content_style", [])

        stage = basic.get("learning_stage") or "未填写"
        basis = basic.get("learning_basis") or "零基础"
        background = basic.get("background") or "未填写"
        goal = preferences.get("goal") or "考试通过"
        styles = "、".join(content_style) or "图解、案例"
        difficulty = preferences.get("preferred_difficulty") or "基础"
        tutoring_style = preferences.get("tutoring_style") or "循序渐进"

        return "\n".join([
            PPT_LEARNING_STRATEGY_TITLE,
            f"学习阶段：{stage}",
            f"已有基础：{basis}",
            f"学习背景：{background}",
            f"学习目标：{goal}",
            f"内容偏好：{styles}",
            f"难度策略：{difficulty}",
            f"辅导方式：{tutoring_style}",
            "请据此调整知识起点、内容结构、案例类型、解释深度和课堂互动题难度。",
            "不要把画像字段直接展示在幻灯片正文中，也不要将画像信息写入学生可见讲稿。",
        ])
