from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from interactive_classroom.schema import LearningEvent
from interactive_classroom.storage import ClassroomStorage


def _now_iso() -> str:
    return datetime.now().isoformat()


def _new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:16]}"


def _build_dedupe_key(
    event_type: str,
    classroom_id: str,
    scene_id: str,
    extra: str = "",
) -> str:
    """构建幂等键，用于防重复提交。"""
    raw = f"{event_type}:{classroom_id}:{scene_id}:{extra}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def create_quiz_submitted_event(
    user_id: str,
    classroom_id: str,
    scene_id: str,
    course_id: str,
    eval_result: dict[str, Any],
    answers: dict[str, Any],
    retry_of: str = "",
) -> LearningEvent:
    """创建 quiz_submitted 事件。"""
    dedupe_key = _build_dedupe_key("quiz_submitted", classroom_id, scene_id)
    results = eval_result.get("results", [])
    knowledge_points = list({
        str(r.get("knowledge_point", "")).strip()
        for r in results
        if r.get("knowledge_point")
    })

    return LearningEvent(
        id=_new_event_id(),
        type="quiz_submitted",
        user_id=user_id,
        classroom_id=classroom_id,
        scene_id=scene_id,
        course_id=course_id,
        created_at=_now_iso(),
        knowledge_points=knowledge_points,
        payload={
            "score": eval_result.get("score", 0),
            "correct": eval_result.get("correct", 0),
            "total": eval_result.get("total", 0),
            "earned_points": eval_result.get("earned_points", 0),
            "total_points": eval_result.get("total_points", 0),
            "question_count": len(results),
            "answers_summary": {
                r.get("question_id", ""): {
                    "correct": r.get("correct", False),
                    "knowledge_point": r.get("knowledge_point", ""),
                }
                for r in results
            },
        },
        retry_of=retry_of,
        dedupe_key=dedupe_key,
    )


def create_short_answer_scored_event(
    user_id: str,
    classroom_id: str,
    scene_id: str,
    course_id: str,
    question_id: str,
    knowledge_point: str,
    grade: dict[str, Any],
) -> LearningEvent:
    """创建 short_answer_scored 事件。"""
    dedupe_key = _build_dedupe_key(
        "short_answer_scored", classroom_id, scene_id, extra=question_id
    )
    kp = knowledge_point.strip()
    return LearningEvent(
        id=_new_event_id(),
        type="short_answer_scored",
        user_id=user_id,
        classroom_id=classroom_id,
        scene_id=scene_id,
        course_id=course_id,
        created_at=_now_iso(),
        knowledge_points=[kp] if kp else [],
        payload={
            "question_id": question_id,
            "score": grade.get("score", 0),
            "feedback": grade.get("feedback", ""),
            "covered_points": grade.get("covered_points", []),
        },
        dedupe_key=dedupe_key,
    )


def create_scene_reviewed_event(
    user_id: str,
    classroom_id: str,
    scene_id: str,
    course_id: str,
    knowledge_points: list[str] | None = None,
    review_count: int = 1,
) -> LearningEvent:
    """创建 scene_reviewed 事件（复听讲解页）。"""
    dedupe_key = _build_dedupe_key("scene_reviewed", classroom_id, scene_id)
    return LearningEvent(
        id=_new_event_id(),
        type="scene_reviewed",
        user_id=user_id,
        classroom_id=classroom_id,
        scene_id=scene_id,
        course_id=course_id,
        created_at=_now_iso(),
        knowledge_points=knowledge_points or [],
        payload={"review_count": review_count},
        dedupe_key=dedupe_key,
    )


def create_recommended_task_opened_event(
    user_id: str,
    classroom_id: str,
    course_id: str,
    task_id: str,
    task_type: str,
    knowledge_points: list[str] | None = None,
) -> LearningEvent:
    """创建 recommended_task_opened 事件。"""
    return LearningEvent(
        id=_new_event_id(),
        type="recommended_task_opened",
        user_id=user_id,
        classroom_id=classroom_id,
        course_id=course_id,
        created_at=_now_iso(),
        knowledge_points=knowledge_points or [],
        payload={"task_id": task_id, "task_type": task_type},
        dedupe_key=_build_dedupe_key("recommended_task_opened", classroom_id, task_id),
    )


def create_recommended_task_completed_event(
    user_id: str,
    classroom_id: str,
    course_id: str,
    task_id: str,
    task_type: str,
    knowledge_points: list[str] | None = None,
    result: dict[str, Any] | None = None,
) -> LearningEvent:
    """创建 recommended_task_completed 事件。"""
    return LearningEvent(
        id=_new_event_id(),
        type="recommended_task_completed",
        user_id=user_id,
        classroom_id=classroom_id,
        course_id=course_id,
        created_at=_now_iso(),
        knowledge_points=knowledge_points or [],
        payload={
            "task_id": task_id,
            "task_type": task_type,
            "result": result or {},
        },
        dedupe_key=_build_dedupe_key("recommended_task_completed", classroom_id, task_id),
    )


def create_classroom_completed_event(
    user_id: str,
    classroom_id: str,
    course_id: str,
    quiz_total: int,
    answered_total: int,
) -> LearningEvent:
    """创建 classroom_completed 事件。"""
    return LearningEvent(
        id=_new_event_id(),
        type="classroom_completed",
        user_id=user_id,
        classroom_id=classroom_id,
        course_id=course_id,
        created_at=_now_iso(),
        payload={
            "quiz_total": quiz_total,
            "answered_total": answered_total,
        },
        dedupe_key=_build_dedupe_key("classroom_completed", classroom_id, ""),
    )


def record_event(
    storage: ClassroomStorage,
    event: LearningEvent,
) -> LearningEvent:
    """记录事件到存储，返回已保存的事件。

    如果 dedupe_key 已存在则跳过写入，返回已有事件。
    """
    existing = storage.find_event_by_dedupe_key(
        event.user_id, event.classroom_id, event.dedupe_key
    )
    if existing:
        return existing
    storage.save_event(event.user_id, event.classroom_id, event)
    return event
