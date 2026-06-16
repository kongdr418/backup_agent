from __future__ import annotations

import hashlib
from typing import Any

from learner_profile.profile_agent import build_course_id


def _proposal_id(*parts: str) -> str:
    raw = "|".join(parts)
    return "update_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class ErrorDiagnosisAgent:
    def analyze(
        self,
        *,
        profile: dict[str, Any],
        classroom: dict[str, Any],
        report: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        course_name = str(
            classroom.get("course") or classroom.get("topic") or "通用课程"
        ).strip()
        course_id = build_course_id(course_name)
        evidence_by_pattern: dict[str, list[str]] = {}
        knowledge_by_pattern: dict[str, set[str]] = {}

        for event in events:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or "")
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            score = float(payload.get("score", 100) or 0)
            feedback = str(payload.get("feedback") or "")
            patterns: list[str] = []
            if event.get("type") == "short_answer_scored" and score < 65:
                if any(word in feedback for word in ("表达", "不完整", "要点")):
                    patterns.append("expression_gap")
                elif any(word in feedback for word in ("步骤", "过程")):
                    patterns.append("procedural_error")
            explicit = payload.get("error_pattern")
            if isinstance(explicit, str) and explicit:
                patterns.append(explicit)
            for pattern in patterns:
                evidence_by_pattern.setdefault(pattern, []).append(event_id)
                knowledge_by_pattern.setdefault(pattern, set()).update(
                    str(value)
                    for value in event.get("knowledge_points", [])
                    if str(value)
                )

        proposals: list[dict[str, Any]] = []
        for pattern, evidence_ids in evidence_by_pattern.items():
            unique_ids = list(dict.fromkeys(value for value in evidence_ids if value))
            confidence = min(0.9, 0.62 + 0.1 * len(unique_ids))
            proposals.append(
                {
                    "id": _proposal_id(course_id, pattern, *unique_ids),
                    "type": "error_pattern_update",
                    "scope": "course",
                    "course_id": course_id,
                    "course_name": course_name,
                    "classroom_id": str(classroom.get("id") or ""),
                    "trait_key": pattern,
                    "before": (
                        profile.get("courses", {})
                        .get(course_id, {})
                        .get("error_patterns", {})
                        .get(pattern)
                    ),
                    "after": {
                        "severity": min(1.0, 0.5 + 0.12 * len(unique_ids)),
                        "confidence": confidence,
                        "knowledge_point_ids": sorted(knowledge_by_pattern.get(pattern, set())),
                        "evidence_ids": unique_ids,
                    },
                    "confidence": confidence,
                    "reason": "课堂评分反馈显示该错误模式需要持续关注。",
                    "evidence_ids": unique_ids,
                }
            )
        return proposals
