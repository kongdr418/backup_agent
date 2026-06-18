from __future__ import annotations

import asyncio
from typing import Any, Callable

from learner_profile.profile_agent import build_course_id

from .event_service import (
    create_classroom_completed_event,
    create_flashcard_reviewed_event,
    create_mistake_mastered_event,
    create_quiz_submitted_event,
    create_recommended_task_completed_event,
    create_recommended_task_opened_event,
    create_scene_reviewed_event,
    create_short_answer_scored_event,
    record_event,
)
from .next_lesson_service import build_next_lesson_plan
from .practice_service import ClassroomPracticeService
from .quiz_service import evaluate_quiz_scene, evaluate_quiz_scene_async
from .report_service import (
    build_classroom_report,
    refresh_report_learning_path,
    resolve_knowledge_evidence,
)
from .tts_service import ClassroomTTSService


def _format_answer_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " / ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


class ClassroomRuntimeService:
    def __init__(
        self,
        *,
        classroom_storage: Any,
        learner_profile_storage: Any,
        profile_agent: Any,
        course_knowledge_retriever: Any,
        practice_service: ClassroomPracticeService,
        completion_service: Any,
        build_tts_config: Callable[..., dict],
        logger: Any,
        study_tools_storage: Any | None = None,
    ) -> None:
        self.classroom_storage = classroom_storage
        self.learner_profile_storage = learner_profile_storage
        self.profile_agent = profile_agent
        self.course_knowledge_retriever = course_knowledge_retriever
        self.practice_service = practice_service
        self.study_tools_storage = study_tools_storage
        self.completion_service = completion_service
        self.build_tts_config = build_tts_config
        self.logger = logger

    def submit_answer(
        self,
        *,
        user_id: str,
        classroom_id: str,
        classroom: dict,
        scene: dict,
        scene_id: str,
        answers: dict,
        request_data: dict,
        llm_config: dict | None = None,
    ) -> dict:
        has_short_answer = any(
            str(q.get("type", "")) == "short_answer"
            for q in scene.get("content", {}).get("questions", [])
        )

        if has_short_answer:
            try:
                eval_result = asyncio.run(
                    evaluate_quiz_scene_async(scene, answers, llm_config=llm_config)
                )
            except Exception as exc:
                self.logger.exception(
                    "[INTERACTIVE-CLASSROOM] /answer LLM 评分失败: %s",
                    exc,
                )
                eval_result = evaluate_quiz_scene(scene, answers)
        else:
            eval_result = evaluate_quiz_scene(scene, answers)

        self.classroom_storage.save_answers(
            user_id=user_id,
            classroom_id=classroom_id,
            scene_id=scene_id,
            answers_payload={"answers": answers, "evaluation": eval_result},
        )
        self._record_answer_events(
            user_id=user_id,
            classroom_id=classroom_id,
            classroom=classroom,
            scene_id=scene_id,
            eval_result=eval_result,
            answers=answers,
        )
        mistake_sync = self._sync_wrong_answers_to_mistakes(
            user_id=user_id,
            classroom_id=classroom_id,
            classroom=classroom,
            scene=scene,
            scene_id=scene_id,
            eval_result=eval_result,
        )
        feedback_action = self._build_feedback_action(
            user_id=user_id,
            classroom_id=classroom_id,
            classroom=classroom,
            scene_id=scene_id,
            eval_result=eval_result,
            request_data=request_data,
        )
        return {
            "score": eval_result.get("score", 0),
            "correct": eval_result.get("correct", 0),
            "total": eval_result.get("total", 0),
            "earned_points": eval_result.get("earned_points", 0),
            "total_points": eval_result.get("total_points", 0),
            "results": eval_result.get("results", []),
            "mistake_sync": mistake_sync,
            "feedback_action": feedback_action,
        }

    def build_report_for_classroom(
        self,
        *,
        user_id: str,
        classroom_id: str,
        classroom: dict,
    ) -> dict:
        self.practice_service.backfill_practice_created_events(
            user_id=user_id,
            classroom=classroom,
        )
        answers = self.classroom_storage.load_answers(user_id, classroom_id)
        events = self.classroom_storage.load_events(user_id, classroom_id)
        report = self._build_or_refresh_report(
            user_id=user_id,
            classroom_id=classroom_id,
            classroom=classroom,
            answers=answers,
            events=events,
        )

        course_name = classroom.get("course") or classroom.get("topic") or "通用课程"
        topic = classroom.get("topic", "")
        knowledge_context = self._retrieve_knowledge_context(
            user_id=user_id,
            course_name=course_name,
            topic=topic,
            log_prefix="[REPORT]",
            classroom_id=classroom_id,
        )
        report["knowledge_evidence"] = resolve_knowledge_evidence(
            report.get("knowledge_summary", {}),
            knowledge_context,
            classroom,
        )

        proposals = self.completion_service.analyze_profile_updates(
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
            build_course_id(course_name),
            report.get("recommended_tasks", []),
        )
        return report

    def create_practice_from_recommendation(
        self,
        *,
        user_id: str,
        classroom_id: str,
        classroom: dict,
        task_id: str,
        task_type: str,
    ) -> dict:
        report = self.classroom_storage.load_report(user_id, classroom_id)
        if report is None:
            answers = self.classroom_storage.load_answers(user_id, classroom_id)
            events = self.classroom_storage.load_events(user_id, classroom_id)
            report = self._build_fresh_report(
                user_id=user_id,
                classroom=classroom,
                answers=answers,
                events=events,
            )
            self.classroom_storage.save_report(user_id, classroom_id, report)

        profile = self.learner_profile_storage.load_profile(user_id)
        course_name = classroom.get("course") or classroom.get("topic") or "通用课程"
        strategy = self.profile_agent.build_generation_strategy(profile, course_name)
        practice = self.practice_service.create_practice(
            user_id=user_id,
            source_classroom=classroom,
            report=report,
            task_id=task_id,
            task_type=task_type,
            generation_strategy=strategy,
        )
        completion_event = create_recommended_task_completed_event(
            user_id=user_id,
            classroom_id=classroom_id,
            course_id=classroom.get("course") or classroom.get("topic") or "",
            task_id=task_id,
            task_type=task_type,
            knowledge_points=practice.get("knowledge_points", []),
            result={
                "status": "practice_created",
                "practice_classroom_id": practice.get("id", ""),
            },
        )
        record_event(self.classroom_storage, completion_event)

        answers = self.classroom_storage.load_answers(user_id, classroom_id)
        events = self.classroom_storage.load_events(user_id, classroom_id)
        if answers.get("scenes"):
            report = self._build_fresh_report(
                user_id=user_id,
                classroom=classroom,
                answers=answers,
                events=events,
            )
        else:
            report = refresh_report_learning_path(
                report,
                events,
                self.classroom_storage,
                user_id,
            )
        self.classroom_storage.save_report(user_id, classroom_id, report)
        self.learner_profile_storage.record_recommendations(
            user_id,
            classroom_id,
            build_course_id(course_name),
            report.get("recommended_tasks", []),
        )
        return practice

    def build_next_lesson_plan_for_classroom(
        self,
        *,
        user_id: str,
        classroom_id: str,
        classroom: dict,
        overrides: dict,
    ) -> dict:
        report = self.classroom_storage.load_report(user_id, classroom_id)
        if report is None:
            answers = self.classroom_storage.load_answers(user_id, classroom_id)
            events = self.classroom_storage.load_events(user_id, classroom_id)
            report = self._build_fresh_report(
                user_id=user_id,
                classroom=classroom,
                answers=answers,
                events=events,
            )
            self.classroom_storage.save_report(user_id, classroom_id, report)

        course_name = classroom.get("course") or classroom.get("topic") or ""
        topic = classroom.get("topic", "")
        knowledge_context = self._retrieve_knowledge_context(
            user_id=user_id,
            course_name=course_name,
            topic=topic,
            log_prefix="[NEXT-LESSON]",
            classroom_id=classroom_id,
        )
        profile = self.learner_profile_storage.load_profile(user_id)
        generation_strategy = self.profile_agent.build_generation_strategy(
            profile,
            course_name or topic or "通用课程",
        )
        return build_next_lesson_plan(
            classroom,
            report,
            overrides,
            knowledge_context,
            generation_strategy,
        )

    def record_learning_event(
        self,
        *,
        user_id: str,
        classroom_id: str,
        classroom: dict,
        event_type: str,
        scene_id: str,
        payload: dict,
    ):
        course_id = classroom.get("course", "") or classroom.get("topic", "")
        if event_type == "scene_reviewed":
            scene = next(
                (s for s in classroom.get("scenes", []) if s.get("id") == scene_id),
                None,
            )
            event = create_scene_reviewed_event(
                user_id=user_id,
                classroom_id=classroom_id,
                scene_id=scene_id,
                course_id=course_id,
                knowledge_points=scene.get("knowledge_points", []) if scene else [],
                review_count=int(payload.get("review_count", 1)),
            )
        elif event_type == "recommended_task_opened":
            event = create_recommended_task_opened_event(
                user_id=user_id,
                classroom_id=classroom_id,
                course_id=course_id,
                task_id=payload.get("task_id", ""),
                task_type=payload.get("task_type", ""),
                knowledge_points=payload.get("knowledge_points", []),
            )
        elif event_type == "recommended_task_completed":
            event = create_recommended_task_completed_event(
                user_id=user_id,
                classroom_id=classroom_id,
                course_id=course_id,
                task_id=payload.get("task_id", ""),
                task_type=payload.get("task_type", ""),
                knowledge_points=payload.get("knowledge_points", []),
                result=payload.get("result", {}),
            )
        elif event_type == "classroom_completed":
            event = create_classroom_completed_event(
                user_id=user_id,
                classroom_id=classroom_id,
                course_id=course_id,
                quiz_total=int(payload.get("quiz_total", 0)),
                answered_total=int(payload.get("answered_total", 0)),
            )
        elif event_type == "mistake_mastered":
            event = create_mistake_mastered_event(
                user_id=user_id,
                classroom_id=classroom_id,
                scene_id=scene_id,
                course_id=course_id,
                mistake=payload.get("mistake", {}),
            )
        elif event_type == "flashcard_reviewed":
            event = create_flashcard_reviewed_event(
                user_id=user_id,
                classroom_id=classroom_id,
                scene_id=scene_id,
                course_id=course_id,
                flashcard=payload.get("flashcard", {}),
                grade=int(payload.get("grade", 0)),
            )
        else:
            raise ValueError(f"不支持的 event_type: {event_type}")

        saved = record_event(self.classroom_storage, event)
        if event_type == "classroom_completed":
            self.completion_service.handle_completion(user_id, classroom)
        return saved

    def _sync_wrong_answers_to_mistakes(
        self,
        *,
        user_id: str,
        classroom_id: str,
        classroom: dict,
        scene: dict,
        scene_id: str,
        eval_result: dict,
    ) -> dict[str, int]:
        if self.study_tools_storage is None:
            return {"added": 0, "deduped": 0}

        questions = {
            str(question.get("id") or ""): question
            for question in scene.get("content", {}).get("questions", [])
            if isinstance(question, dict)
        }
        course_name = classroom.get("course") or classroom.get("topic") or ""
        course_id = build_course_id(course_name) if course_name else ""
        items: list[dict[str, Any]] = []

        for result in eval_result.get("results", []):
            if result.get("correct") is not False:
                continue
            question_id = str(result.get("question_id") or "")
            if not question_id:
                continue
            question = questions.get(question_id, {})
            items.append(
                {
                    "source": "classroom",
                    "source_evidence_id": f"{classroom_id}:{scene_id}:{question_id}:wrong",
                    "source_ref": {
                        "classroom_id": classroom_id,
                        "scene_id": scene_id,
                        "question_id": question_id,
                    },
                    "course_id": course_id,
                    "course_name": course_name,
                    "knowledge_point_name": (
                        result.get("knowledge_point")
                        or question.get("knowledge_point")
                        or ""
                    ),
                    "stem": question.get("question") or "",
                    "question_type": question.get("type") or "",
                    "options": question.get("options") or [],
                    "correct_answer": _format_answer_text(result.get("correct_answer")),
                    "user_answer": _format_answer_text(result.get("your_answer")),
                    "analysis": result.get("analysis") or question.get("analysis") or "",
                    "tags": ["classroom"],
                }
            )

        if not items:
            return {"added": 0, "deduped": 0}
        try:
            outcome = self.study_tools_storage.bulk_add_mistakes(user_id, items)
            return {
                "added": int(outcome.get("added_count", 0) or 0),
                "deduped": int(outcome.get("deduped_count", 0) or 0),
            }
        except Exception:
            self.logger.warning(
                "[INTERACTIVE-CLASSROOM] study_tools_mistake_sync_failed",
                exc_info=True,
            )
            return {"added": 0, "deduped": 0}

    def _record_answer_events(
        self,
        *,
        user_id: str,
        classroom_id: str,
        classroom: dict,
        scene_id: str,
        eval_result: dict,
        answers: dict,
    ) -> None:
        course_id = classroom.get("course", "") or classroom.get("topic", "")
        try:
            quiz_event = create_quiz_submitted_event(
                user_id=user_id,
                classroom_id=classroom_id,
                scene_id=scene_id,
                course_id=course_id,
                eval_result=eval_result,
                answers=answers,
            )
            record_event(self.classroom_storage, quiz_event)

            for result in eval_result.get("results", []):
                if result.get("score") is not None and result.get("feedback") is not None:
                    sa_event = create_short_answer_scored_event(
                        user_id=user_id,
                        classroom_id=classroom_id,
                        scene_id=scene_id,
                        course_id=course_id,
                        question_id=result.get("question_id", ""),
                        knowledge_point=result.get("knowledge_point", ""),
                        grade={
                            "score": result.get("score", 0),
                            "feedback": result.get("feedback", ""),
                            "covered_points": result.get("covered_points", []),
                        },
                    )
                    record_event(self.classroom_storage, sa_event)
        except Exception:
            self.logger.warning(
                "[INTERACTIVE-CLASSROOM] 学习事件记录失败（不影响答题流程）",
                exc_info=True,
            )

    def _build_feedback_action(
        self,
        *,
        user_id: str,
        classroom_id: str,
        classroom: dict,
        scene_id: str,
        eval_result: dict,
        request_data: dict,
    ) -> dict:
        feedback_action = {
            "id": f"feedback_{scene_id}",
            "type": "quiz_feedback",
            "agent_id": "teacher",
            "text": eval_result.get("feedback_text", ""),
            "audio_url": "",
        }

        feedback_text = feedback_action["text"]
        if feedback_text:
            try:
                audio_dir = self.classroom_storage.audio_dir(user_id, classroom_id)
                tts = ClassroomTTSService(
                    output_dir=audio_dir,
                    tts_config=self.build_tts_config(
                        data=request_data,
                        classroom=classroom,
                    ),
                )
                filename = tts.synthesize_action(
                    feedback_action["id"],
                    feedback_text,
                    audio_dir,
                )
                if filename:
                    feedback_action["audio_url"] = (
                        f"/api/interactive-classroom/{classroom_id}/audio/{filename}"
                    )
            except Exception:
                feedback_action["audio_url"] = ""
        return feedback_action

    def _build_or_refresh_report(
        self,
        *,
        user_id: str,
        classroom_id: str,
        classroom: dict,
        answers: dict,
        events: list[dict],
    ) -> dict:
        if answers.get("scenes"):
            return self._build_fresh_report(
                user_id=user_id,
                classroom=classroom,
                answers=answers,
                events=events,
            )
        cached_report = self.classroom_storage.load_report(user_id, classroom_id)
        if cached_report is not None:
            return refresh_report_learning_path(
                cached_report,
                events,
                self.classroom_storage,
                user_id,
            )
        return self._build_fresh_report(
            user_id=user_id,
            classroom=classroom,
            answers=answers,
            events=events,
        )

    def _build_fresh_report(
        self,
        *,
        user_id: str,
        classroom: dict,
        answers: dict,
        events: list[dict],
    ) -> dict:
        profile = self.learner_profile_storage.load_profile(user_id)
        course_name = classroom.get("course") or classroom.get("topic") or "通用课程"
        course_profile = profile.get("courses", {}).get(build_course_id(course_name), {})
        return build_classroom_report(
            classroom,
            answers,
            events,
            course_profile=course_profile,
            storage=self.classroom_storage,
            user_id=user_id,
        )

    def _retrieve_knowledge_context(
        self,
        *,
        user_id: str,
        course_name: str,
        topic: str,
        log_prefix: str,
        classroom_id: str,
    ) -> dict | None:
        try:
            return self.course_knowledge_retriever.retrieve_course_context(
                user_id,
                course_name,
                topic,
            )
        except Exception as exc:
            self.logger.warning(
                "%s knowledge_retrieval_failed classroom_id=%s error=%s",
                log_prefix,
                classroom_id,
                type(exc).__name__,
            )
            return None
