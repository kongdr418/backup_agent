from __future__ import annotations

from typing import Any

from learner_profile.profile_agent import build_course_id

from .event_service import create_recommended_task_completed_event, record_event
from .report_service import build_classroom_report, resolve_knowledge_evidence


class ClassroomCompletionService:
    def __init__(
        self,
        *,
        classroom_storage: Any,
        learner_profile_storage: Any,
        profile_agent: Any,
        profile_orchestrator: Any,
        course_knowledge_retriever: Any,
        logger: Any,
    ) -> None:
        self.classroom_storage = classroom_storage
        self.learner_profile_storage = learner_profile_storage
        self.profile_agent = profile_agent
        self.profile_orchestrator = profile_orchestrator
        self.course_knowledge_retriever = course_knowledge_retriever
        self.logger = logger

    def analyze_profile_updates(
        self,
        user_id: str,
        classroom: dict,
        report: dict,
        events: list[dict],
        knowledge_context: dict | None = None,
    ) -> list[dict]:
        try:
            profile = self.learner_profile_storage.load_profile(user_id)
            course_name = classroom.get("course") or classroom.get("topic") or "通用课程"
            course_id = build_course_id(course_name)
            course_profile = profile.get("courses", {}).get(course_id, {})
            cached_points = self.classroom_storage.load_knowledge_point_cache(
                user_id,
                classroom.get("id", ""),
            )
            cached_by_raw = {
                str(row.get("raw_name")): row
                for row in cached_points
                if isinstance(row, dict) and row.get("raw_name")
            }
            raw_points = list((report.get("knowledge_summary") or {}).keys())
            missing_points = [point for point in raw_points if point not in cached_by_raw]
            if missing_points:
                normalized_missing = self.profile_agent.normalize_knowledge_points(
                    missing_points,
                    course_profile,
                    context=f"{course_name} {classroom.get('topic', '')}",
                    knowledge_context=knowledge_context,
                )
                for row in normalized_missing:
                    if isinstance(row, dict) and row.get("raw_name"):
                        cached_by_raw[str(row["raw_name"])] = row
                cached_points = list(cached_by_raw.values())
                self.classroom_storage.save_knowledge_point_cache(
                    user_id,
                    classroom.get("id", ""),
                    cached_points,
                )
            observations = self.profile_agent.collect_evidence_observations(
                profile,
                classroom,
                report,
                events,
                normalized_points=[
                    cached_by_raw[point]
                    for point in raw_points
                    if point in cached_by_raw
                ],
            )
            profile = self.learner_profile_storage.accumulate_evidence(
                user_id,
                observations,
            )
            mastery_proposals = self.profile_agent.analyze_learning_evidence(
                profile,
                classroom,
                report,
                events,
                observations=observations,
            )
            trait_proposals = self.profile_orchestrator.analyze(
                profile=profile,
                classroom=classroom,
                report=report,
                events=events,
            )
            proposals = [*mastery_proposals, *trait_proposals]
            if proposals:
                self.learner_profile_storage.add_pending_updates(user_id, proposals)
            return proposals
        except Exception:
            self.logger.warning(
                "[INTERACTIVE-CLASSROOM] 画像建议分析失败（不影响报告主流程）",
                exc_info=True,
            )
            return []

    def handle_completion(self, user_id: str, classroom: dict) -> None:
        try:
            classroom_id = classroom.get("id", "")
            source = classroom.get("source") if isinstance(classroom.get("source"), dict) else {}
            quiz_scene_ids = {
                scene.get("id")
                for scene in classroom.get("scenes", [])
                if scene.get("type") == "quiz" and scene.get("id")
            }
            answered_scene_ids = set(
                self.classroom_storage.load_answers(user_id, classroom_id).get("scenes", {}).keys()
            )
            is_actually_complete = bool(quiz_scene_ids) and quiz_scene_ids.issubset(
                answered_scene_ids
            )
            if source.get("type") == "recommended_practice":
                parent_classroom_id = (source.get("parent_classroom_id") or "").strip()
                task_id = (source.get("recommendation_task_id") or "").strip()
                task_type = (source.get("recommendation_task_type") or "").strip()
                parent = (
                    self.classroom_storage.load_classroom(user_id, parent_classroom_id)
                    if parent_classroom_id
                    else None
                )
                if parent is not None and task_id and is_actually_complete:
                    completion_event = create_recommended_task_completed_event(
                        user_id=user_id,
                        classroom_id=parent_classroom_id,
                        course_id=parent.get("course") or parent.get("topic") or "",
                        task_id=task_id,
                        task_type=task_type,
                        knowledge_points=classroom.get("knowledge_points", []),
                        result={
                            "status": "completed",
                            "practice_classroom_id": classroom_id,
                        },
                    )
                    record_event(self.classroom_storage, completion_event)

            answers = self.classroom_storage.load_answers(user_id, classroom_id)
            events = self.classroom_storage.load_events(user_id, classroom_id)
            profile = self.learner_profile_storage.load_profile(user_id)
            course_name = classroom.get("course") or classroom.get("topic") or "通用课程"
            course_id = build_course_id(course_name)
            course_profile = profile.get("courses", {}).get(course_id, {})
            report = build_classroom_report(
                classroom,
                answers,
                events,
                course_profile=course_profile,
                storage=self.classroom_storage,
                user_id=user_id,
            )
            topic = classroom.get("topic", "")
            try:
                knowledge_context = self.course_knowledge_retriever.retrieve_course_context(
                    user_id, course_name, topic,
                )
            except Exception as exc:
                self.logger.warning(
                    "[PRACTICE-REPORT] knowledge_retrieval_failed classroom_id=%s error=%s",
                    classroom_id, type(exc).__name__,
                )
                knowledge_context = None
            report["knowledge_evidence"] = resolve_knowledge_evidence(
                report.get("knowledge_summary", {}),
                knowledge_context,
                classroom,
            )
            proposals = self.analyze_profile_updates(
                user_id,
                classroom,
                report,
                events,
                knowledge_context=knowledge_context,
            )
            report["profile_update_count"] = len(proposals)
            report["profile_update_ids"] = [
                row.get("id") for row in proposals if row.get("id")
            ]
            self.classroom_storage.save_report(user_id, classroom_id, report)
            self.learner_profile_storage.record_recommendations(
                user_id,
                classroom_id,
                course_id,
                report.get("recommended_tasks", []),
            )
        except Exception:
            self.logger.warning(
                "[INTERACTIVE-CLASSROOM] 课堂完成后的画像闭环处理失败",
                exc_info=True,
            )
