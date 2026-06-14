from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from interactive_classroom.event_service import (
    create_recommended_task_completed_event,
    record_event,
)
from interactive_classroom.generator import InteractiveClassroomGenerator
from interactive_classroom.schema import InteractiveClassroom
from interactive_classroom.storage import ClassroomStorage


def _clean_practice_text(value: Any, max_length: int = 160) -> str:
    text = " ".join(str(value or "").split())
    return text[:max_length].strip()


def _collect_practice_evidence(
    source_classroom: dict[str, Any],
    knowledge_points: list[str],
    target_scene_ids: list[str],
) -> list[dict[str, Any]]:
    scenes = [
        scene
        for scene in source_classroom.get("scenes", [])
        if isinstance(scene, dict) and scene.get("type") == "slide"
    ]
    if target_scene_ids:
        wanted = set(target_scene_ids)
        prioritized = [scene for scene in scenes if scene.get("id") in wanted]
        scenes = prioritized or scenes

    evidence: list[dict[str, Any]] = []
    for point in knowledge_points:
        point_text = _clean_practice_text(point, 80)
        snippets: list[str] = []
        for scene in scenes:
            content = scene.get("content") if isinstance(scene.get("content"), dict) else {}
            values: list[Any] = [
                scene.get("title", ""),
                *scene.get("knowledge_points", []),
                *content.get("extracted_text", []),
            ]
            for action in scene.get("actions", []):
                if isinstance(action, dict):
                    values.append(action.get("text", ""))

            joined = " ".join(_clean_practice_text(value, 240) for value in values if _clean_practice_text(value))
            if point_text and point_text not in joined:
                continue
            for value in values:
                text = _clean_practice_text(value, 160)
                if text and text not in snippets:
                    snippets.append(text)
                if len(snippets) >= 6:
                    break
            if snippets:
                break
        evidence.append({"point": point_text, "snippets": snippets[:6]})
    return evidence


class ClassroomPracticeService:
    def __init__(
        self,
        storage: ClassroomStorage,
        generator: InteractiveClassroomGenerator,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.storage = storage
        self.generator = generator
        self.now_provider = now_provider or datetime.now

    def create_practice(
        self,
        *,
        user_id: str,
        source_classroom: dict[str, Any],
        report: dict[str, Any],
        task_id: str,
        task_type: str,
        generation_strategy: dict[str, Any],
    ) -> dict[str, Any]:
        if task_type not in {"practice_weak_points", "challenge_practice"}:
            raise ValueError("unsupported practice task")
        task = next(
            (
                row
                for row in report.get("recommended_tasks", [])
                if isinstance(row, dict)
                and row.get("id") == task_id
                and row.get("type") == task_type
            ),
            None,
        )
        if task is None:
            raise ValueError("recommendation task not found")

        knowledge_points = [
            str(value).strip()
            for value in task.get("knowledge_points", [])
            if str(value).strip()
        ][:5]
        if not knowledge_points:
            fallback_key = (
                "weak_points"
                if task_type == "practice_weak_points"
                else "strong_points"
            )
            knowledge_points = [
                str(value).strip()
                for value in report.get(fallback_key, [])
                if str(value).strip()
            ][:5]
        if not knowledge_points:
            knowledge_points = [
                str(source_classroom.get("topic") or "综合理解").strip()
            ]

        diagnostic_notes = []
        recommendation = str(report.get("next_recommendation") or "").strip()
        if recommendation:
            diagnostic_notes.append(f"学习报告建议：{recommendation}")
        weak_points = [
            str(value).strip()
            for value in report.get("weak_points", [])
            if str(value).strip()
        ][:5]
        if weak_points:
            diagnostic_notes.append(f"报告薄弱点：{'、'.join(weak_points)}")
        task_reason = str(task.get("reason") or "").strip()
        if task_reason:
            diagnostic_notes.append(f"推荐原因：{task_reason}")
        knowledge_summary = report.get("knowledge_summary", {})
        if isinstance(knowledge_summary, dict):
            low_mastery = []
            for point in knowledge_points:
                row = knowledge_summary.get(point, {})
                if isinstance(row, dict) and row.get("mastery") is not None:
                    low_mastery.append(f"{point}掌握度{row.get('mastery')}%")
            if low_mastery:
                diagnostic_notes.append(f"掌握证据：{'；'.join(low_mastery[:4])}")
        target_scene_ids = [
            str(value).strip()
            for value in task.get("target_scene_ids", [])
            if str(value).strip()
        ][:8]
        practice_evidence = _collect_practice_evidence(
            source_classroom,
            knowledge_points,
            target_scene_ids,
        )

        practice_strategy = dict(generation_strategy or {})
        assessment_strategy = (
            dict(practice_strategy.get("assessment_strategy") or {})
            if isinstance(practice_strategy.get("assessment_strategy"), dict)
            else {}
        )
        if diagnostic_notes:
            assessment_strategy["practice_diagnostic_notes"] = diagnostic_notes
        if practice_evidence:
            assessment_strategy["practice_evidence"] = practice_evidence
        assessment_strategy["practice_focus_points"] = knowledge_points
        assessment_strategy["practice_task_type"] = task_type
        practice_strategy["assessment_strategy"] = assessment_strategy

        now = self.now_provider()
        classroom_id = (
            f"cls_practice_{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        )
        title_prefix = "补强练习" if task_type == "practice_weak_points" else "挑战练习"
        quiz_scene = self.generator.build_practice_quiz_scene(
            topic=f"{source_classroom.get('topic', '')}{title_prefix}",
            knowledge_points=knowledge_points,
            task_type=task_type,
            generation_strategy=practice_strategy,
        )
        source_id = source_classroom.get("id", "")
        parent_depth = int(source_classroom.get("lesson_depth", 0) or 0)
        parent_index = int(source_classroom.get("lesson_index", 1) or 1)
        course_root_id = (
            source_classroom.get("course_root_id") or source_id
        )
        classroom = InteractiveClassroom(
            id=classroom_id,
            user_id=user_id,
            title=f"{source_classroom.get('topic', '课堂')}{title_prefix}",
            topic=str(source_classroom.get("topic") or title_prefix),
            course=str(
                source_classroom.get("course")
                or source_classroom.get("topic")
                or "通用课程"
            ),
            status="ready",
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            tts={},
            student_profile={},
            generation_strategy=practice_strategy,
            course_root_id=course_root_id,
            parent_classroom_id=source_id,
            lesson_depth=parent_depth + 1,
            lesson_index=parent_index + 1,
            lesson_kind="practice",
            source={
                "type": "recommended_practice",
                "parent_classroom_id": source_id,
                "recommendation_task_id": task_id,
                "recommendation_task_type": task_type,
            },
            agents=[
                {
                    "id": "teacher",
                    "name": "AI 教师",
                    "role": "teacher",
                    "avatar": "",
                    "color": "#0f766e",
                    "persona": "根据课堂证据提供补强练习与即时反馈。",
                }
            ],
            knowledge_points=knowledge_points,
            scenes=[quiz_scene],
        )
        payload = classroom.to_dict()
        self.storage.save_classroom(user_id, classroom_id, payload)
        return payload

    def backfill_practice_created_events(
        self,
        *,
        user_id: str,
        classroom: dict[str, Any],
    ) -> int:
        classroom_id = classroom.get("id", "")
        if not classroom_id:
            return 0

        existing_task_ids = {
            str((event.get("payload") or {}).get("task_id") or "")
            for event in self.storage.load_events(user_id, classroom_id)
            if event.get("type") == "recommended_task_completed"
            and isinstance(event.get("payload"), dict)
            and (event.get("payload") or {}).get("result", {}).get("status")
            == "practice_created"
        }
        created_count = 0
        for row in self.storage.list_classrooms(user_id):
            if row.get("parent_classroom_id") != classroom_id:
                continue
            if row.get("lesson_kind") not in {"practice", "challenge_practice"}:
                continue
            child = self.storage.load_classroom(user_id, row.get("id", ""))
            if not isinstance(child, dict):
                continue
            source = child.get("source")
            if not isinstance(source, dict) or source.get("type") != "recommended_practice":
                continue
            task_id = (source.get("recommendation_task_id") or "").strip()
            if not task_id or task_id in existing_task_ids:
                continue
            event = create_recommended_task_completed_event(
                user_id=user_id,
                classroom_id=classroom_id,
                course_id=classroom.get("course") or classroom.get("topic") or "",
                task_id=task_id,
                task_type=(source.get("recommendation_task_type") or "").strip(),
                knowledge_points=child.get("knowledge_points", []),
                result={
                    "status": "practice_created",
                    "practice_classroom_id": child.get("id", ""),
                },
            )
            record_event(self.storage, event)
            existing_task_ids.add(task_id)
            created_count += 1
        return created_count
