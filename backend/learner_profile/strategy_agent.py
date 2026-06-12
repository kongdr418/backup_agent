from __future__ import annotations

from typing import Any

from .profile_agent import build_course_id


_COGNITIVE_TO_PATTERN = {
    "visual_structure": "diagram",
    "example_based": "example",
    "step_by_step": "step_by_step",
    "comparison": "comparison",
    "text_summary": "concise_summary",
    "hands_on": "code_practice",
}


class StrategyAgent:
    def build(
        self,
        profile: dict[str, Any],
        course_name: str,
        resource_type: str = "classroom",
    ) -> dict[str, Any]:
        basic = profile.get("basic") if isinstance(profile.get("basic"), dict) else {}
        preferences = (
            profile.get("preferences")
            if isinstance(profile.get("preferences"), dict)
            else {}
        )
        course_id = build_course_id(course_name)
        course = (
            profile.get("courses", {}).get(course_id, {})
            if isinstance(profile.get("courses"), dict)
            else {}
        )
        basis = str(basic.get("learning_basis") or "零基础")
        difficulty = str(preferences.get("preferred_difficulty") or "基础")
        if "进阶" in basis or "挑战" in difficulty:
            depth = quiz_difficulty = "advanced"
        elif "有基础" in basis or "中等" in difficulty:
            depth = quiz_difficulty = "intermediate"
        else:
            depth, quiz_difficulty = "basic_to_intermediate", "basic"

        tutoring = str(preferences.get("tutoring_style") or "")
        feedback_style = (
            "direct"
            if "直接" in tutoring
            else "socratic"
            if "启发" in tutoring
            else "guided"
        )
        patterns: list[str] = []
        for value in preferences.get("content_style", []):
            text = str(value)
            for source, target in {
                "图": "diagram",
                "案例": "example",
                "步骤": "step_by_step",
                "代码": "code_practice",
                "对比": "comparison",
                "总结": "concise_summary",
            }.items():
                if source in text and target not in patterns:
                    patterns.append(target)

        global_traits = (
            profile.get("global_traits")
            if isinstance(profile.get("global_traits"), dict)
            else {}
        )
        cognitive = global_traits.get("cognitive_preferences", {})
        if isinstance(cognitive, dict):
            for key, row in cognitive.items():
                if (
                    isinstance(row, dict)
                    and row.get("status") == "confirmed"
                    and float(row.get("weight", 0) or 0) >= 0.5
                ):
                    pattern = _COGNITIVE_TO_PATTERN.get(key)
                    if pattern and pattern not in patterns:
                        patterns.append(pattern)
        interests = [
            str(row.get("label"))
            for row in global_traits.get("interest_directions", [])
            if isinstance(row, dict)
            and row.get("status") == "confirmed"
            and row.get("label")
        ][:4]

        mastery = course.get("mastery") if isinstance(course.get("mastery"), dict) else {}
        weak_rows = sorted(
            (
                row
                for row in mastery.values()
                if isinstance(row, dict) and float(row.get("score", 0) or 0) < 65
            ),
            key=lambda row: float(row.get("score", 0) or 0),
        )
        focus_points = [
            str(row.get("name"))
            for row in weak_rows[:3]
            if row.get("name")
        ] or [str(value) for value in course.get("weak_points", [])[:3]]

        errors = [
            key
            for key, row in (course.get("error_patterns") or {}).items()
            if isinstance(row, dict)
            and row.get("status") == "confirmed"
            and float(row.get("severity", 0) or 0) >= 0.4
        ]
        transfer = course.get("transfer_ability")
        transfer_level = (
            str(transfer.get("level"))
            if isinstance(transfer, dict) and transfer.get("status") == "confirmed"
            else "unobserved"
        )
        evidence_ids = list(
            dict.fromkeys(
                [
                    *[
                        event_id
                        for row in (course.get("error_patterns") or {}).values()
                        if isinstance(row, dict) and row.get("status") == "confirmed"
                        for event_id in row.get("evidence_ids", [])
                    ],
                    *(
                        transfer.get("evidence_ids", [])
                        if isinstance(transfer, dict)
                        and transfer.get("status") == "confirmed"
                        else []
                    ),
                ]
            )
        )
        goal = str(preferences.get("goal") or "概念理解")
        reason = (
            f"结合“{goal}”目标，按已确认画像调整内容，并优先处理"
            f"{'、'.join(focus_points or errors) or '当前课程目标'}。"
        )
        return {
            "strategy_version": 2,
            "course_id": course_id,
            "course_name": course_name or "通用课程",
            "resource_type": resource_type,
            "explanation_depth": depth,
            "content_style": patterns or ["diagram", "example"],
            "quiz_difficulty": quiz_difficulty,
            "feedback_style": feedback_style,
            "focus_knowledge_points": focus_points,
            "avoid": ["直接给出完整答案"] if feedback_style != "direct" else [],
            "content_strategy": {
                "explanation_depth": depth,
                "preferred_patterns": patterns or ["diagram", "example"],
                "interest_contexts": interests,
                "avoid_patterns": [],
            },
            "assessment_strategy": {
                "difficulty": quiz_difficulty,
                "error_targets": errors,
                "transfer_level": transfer_level,
            },
            "interaction_strategy": {
                "feedback_style": feedback_style,
                "require_step_hints": "procedural_error" in errors,
            },
            "evidence_ids": evidence_ids,
            "reason": reason,
            "profile_updated_at": str(profile.get("updated_at") or ""),
        }
