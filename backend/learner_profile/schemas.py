from __future__ import annotations

import json
from typing import Any


PROFILE_VERSION = 2

COGNITIVE_PREFERENCE_KEYS = {
    "visual_structure",
    "example_based",
    "step_by_step",
    "comparison",
    "text_summary",
    "hands_on",
}

ERROR_PATTERN_KEYS = {
    "concept_confusion",
    "prerequisite_gap",
    "procedural_error",
    "application_failure",
    "careless_error",
    "expression_gap",
}

TRANSFER_LEVELS = {
    "unobserved",
    "recall",
    "near_transfer",
    "far_transfer",
    "integrated_problem_solving",
}


def clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def default_global_traits() -> dict[str, Any]:
    return {
        "cognitive_preferences": {},
        "interest_directions": [],
    }


def default_transfer_ability() -> dict[str, Any]:
    return {
        "level": "unobserved",
        "score": 0,
        "confidence": 0.0,
        "status": "unobserved",
        "dimensions": {
            "recall": 0,
            "near_transfer": 0,
            "far_transfer": 0,
            "integrated_problem_solving": 0,
        },
        "evidence_ids": [],
        "updated_at": "",
    }


def normalize_global_traits(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    cognitive = source.get("cognitive_preferences")
    interests = source.get("interest_directions")
    return {
        "cognitive_preferences": clone(cognitive) if isinstance(cognitive, dict) else {},
        "interest_directions": clone(interests) if isinstance(interests, list) else [],
    }


def normalize_course_profile(
    course_id: str,
    value: Any,
    now: str = "",
) -> dict[str, Any]:
    source = clone(value) if isinstance(value, dict) else {}
    source["course_id"] = str(source.get("course_id") or course_id)
    source.setdefault("course_name", "")
    source["mastery"] = source.get("mastery") if isinstance(source.get("mastery"), dict) else {}
    source["strong_points"] = (
        source.get("strong_points") if isinstance(source.get("strong_points"), list) else []
    )
    source["weak_points"] = (
        source.get("weak_points") if isinstance(source.get("weak_points"), list) else []
    )
    source.setdefault("recent_trend", "stable")
    source.setdefault("last_classroom_id", "")
    source["error_patterns"] = (
        source.get("error_patterns")
        if isinstance(source.get("error_patterns"), dict)
        else {}
    )
    transfer = source.get("transfer_ability")
    normalized_transfer = default_transfer_ability()
    if isinstance(transfer, dict):
        normalized_transfer.update(clone(transfer))
        if normalized_transfer.get("level") not in TRANSFER_LEVELS:
            normalized_transfer["level"] = "unobserved"
        dimensions = transfer.get("dimensions")
        if isinstance(dimensions, dict):
            normalized_transfer["dimensions"].update(clone(dimensions))
    source["transfer_ability"] = normalized_transfer
    source.setdefault("updated_at", now)
    return source


def normalize_courses(value: Any, now: str = "") -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {
        str(course_id): normalize_course_profile(str(course_id), course, now)
        for course_id, course in value.items()
        if isinstance(course, dict)
    }
