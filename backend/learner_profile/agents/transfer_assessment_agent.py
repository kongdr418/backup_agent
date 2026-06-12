from __future__ import annotations

import hashlib
from typing import Any

from learner_profile.profile_agent import build_course_id


class TransferAssessmentAgent:
    def analyze(
        self,
        *,
        profile: dict[str, Any],
        classroom: dict[str, Any],
        report: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        source = classroom.get("source") if isinstance(classroom.get("source"), dict) else {}
        task_type = str(source.get("recommendation_task_type") or "")
        lesson_kind = str(classroom.get("lesson_kind") or "")
        if lesson_kind != "practice" and task_type not in {
            "practice_weak_points",
            "challenge_practice",
        }:
            return []

        score_values = [
            float((event.get("payload") or {}).get("score", 0) or 0)
            for event in events
            if isinstance(event, dict)
            and event.get("type") in {"quiz_submitted", "short_answer_scored"}
        ]
        if not score_values:
            return []
        score = round(sum(score_values) / len(score_values))
        target_dimension = (
            "far_transfer" if task_type == "challenge_practice" else "near_transfer"
        )
        if target_dimension == "far_transfer":
            level = "far_transfer" if score >= 65 else "near_transfer"
        else:
            level = "near_transfer" if score >= 50 else "recall"
        confidence = min(0.9, 0.58 + 0.08 * len(score_values))
        course_name = str(
            classroom.get("course") or classroom.get("topic") or "通用课程"
        ).strip()
        course_id = build_course_id(course_name)
        evidence_ids = [
            str(event.get("id"))
            for event in events
            if isinstance(event, dict) and event.get("id")
        ]
        raw = "|".join([course_id, target_dimension, *evidence_ids])
        return [
            {
                "id": "update_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
                "type": "transfer_ability_update",
                "scope": "course",
                "course_id": course_id,
                "course_name": course_name,
                "classroom_id": str(classroom.get("id") or ""),
                "trait_key": "transfer_ability",
                "before": (
                    profile.get("courses", {})
                    .get(course_id, {})
                    .get("transfer_ability")
                ),
                "after": {
                    "level": level,
                    "score": score,
                    "confidence": confidence,
                    "dimensions": {target_dimension: score},
                    "evidence_ids": evidence_ids,
                },
                "confidence": confidence,
                "reason": f"根据{target_dimension}任务表现归纳知识迁移能力。",
                "evidence_ids": evidence_ids,
            }
        ]
