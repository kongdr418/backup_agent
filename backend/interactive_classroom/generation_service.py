from __future__ import annotations

import json
import queue
import re
import threading
from typing import Any, Callable

from .critic_service import build_content_llm_semantic_reviewer
from .generation_jobs import ClassroomGenerationJobService
from .generator import (
    GENERATION_STAGES,
    ClassroomGenerationCancelled,
    InteractiveClassroomGenerator,
)
from .lineage_service import inherit_classroom_lineage, resolve_classroom_lineage


class ClassroomGenerationService:
    def __init__(
        self,
        *,
        generator: InteractiveClassroomGenerator,
        job_service: ClassroomGenerationJobService,
        classroom_storage: Any,
        learner_profile_storage: Any,
        profile_agent: Any,
        course_knowledge_retriever: Any,
        build_tts_config: Callable[..., dict],
        apply_content_llm_config: Callable[[dict], None],
        resolve_content_llm_request_config: Callable[[dict], dict],
        resolve_critic_mode: Callable[[dict], str],
        logger: Any,
    ) -> None:
        self.generator = generator
        self.job_service = job_service
        self.classroom_storage = classroom_storage
        self.learner_profile_storage = learner_profile_storage
        self.profile_agent = profile_agent
        self.course_knowledge_retriever = course_knowledge_retriever
        self.build_tts_config = build_tts_config
        self.apply_content_llm_config = apply_content_llm_config
        self.resolve_content_llm_request_config = resolve_content_llm_request_config
        self.resolve_critic_mode = resolve_critic_mode
        self.logger = logger

    def start_generation(self, *, user_id: str, data: dict) -> tuple[dict, int]:
        topic = (data.get("topic") or "").strip()
        course = (data.get("course") or "通用课程").strip()
        ppt_job_id = (data.get("ppt_job_id") or "").strip()
        request_id = (data.get("request_id") or "").strip()
        lineage = resolve_classroom_lineage(data)

        if not topic:
            return {"success": False, "error": "topic 不能为空"}, 400
        if ppt_job_id and not re.match(r"^[a-zA-Z0-9_.-]{1,128}$", ppt_job_id):
            return {"success": False, "error": "非法 ppt_job_id"}, 400
        if request_id and not self.job_service.is_safe_request_id(request_id):
            return {"success": False, "error": "非法 request_id"}, 400
        if lineage is None:
            return {"success": False, "error": "非法课程关系参数"}, 400

        lineage, course = inherit_classroom_lineage(
            self.classroom_storage,
            user_id,
            lineage,
            course,
        )
        if request_id:
            existing = self.job_service.get_job(request_id)
            if existing:
                return {
                    "success": True,
                    "request_id": request_id,
                    "job": existing,
                    "status": existing.get("status"),
                }, 202

        learner_profile = self.learner_profile_storage.load_profile(user_id)
        student_profile = self.learner_profile_storage.load_classroom_profile(user_id)
        generation_strategy = self.profile_agent.build_generation_strategy(
            learner_profile,
            course,
        )
        self.apply_content_llm_config(data)
        critic_llm_config = self.resolve_content_llm_request_config(data)
        generation_kwargs = {
            "user_id": user_id,
            "topic": topic,
            "course": course,
            "tts_config": self.build_tts_config(data=data),
            "ppt_job_id": ppt_job_id,
            "student_profile": student_profile,
            "generation_strategy": generation_strategy,
            "knowledge_context": self._retrieve_knowledge_context(
                user_id=user_id,
                course=course,
                topic=topic,
            ),
            "lineage": lineage,
            "critic_mode": self.resolve_critic_mode(data),
            "semantic_reviewer": build_content_llm_semantic_reviewer(critic_llm_config),
        }
        cancel_event = self.job_service.register(request_id)
        generation_kwargs["cancel_check"] = (
            cancel_event.is_set if cancel_event is not None else None
        )

        if request_id:
            self.job_service.mark_running(request_id, topic)
            self._start_background_generation(request_id, generation_kwargs)
            return {
                "success": True,
                "request_id": request_id,
                "status": "running",
                "job": self.job_service.get_job(request_id),
            }, 202

        try:
            payload = self.generator.generate(**generation_kwargs)
        except ClassroomGenerationCancelled:
            self.logger.info(
                "[INTERACTIVE-CLASSROOM] 生成已取消 request_id=%s",
                request_id,
            )
            return {"success": False, "cancelled": True, "error": "课堂生成已停止"}, 499
        finally:
            self.job_service.finish(request_id)

        return {
            "success": True,
            "classroom_id": payload.get("id"),
            "status": payload.get("status", "ready"),
            "classroom": payload,
        }, 200

    def cancel_generation(self, request_id: str) -> tuple[dict, int]:
        request_id = (request_id or "").strip()
        if not request_id:
            return {"success": False, "error": "request_id 不能为空"}, 400
        if not self.job_service.is_safe_request_id(request_id):
            return {"success": False, "error": "非法 request_id"}, 400
        self.job_service.cancel(request_id)
        self.logger.info(
            "[INTERACTIVE-CLASSROOM] 收到取消请求 request_id=%s",
            request_id,
        )
        return {"success": True, "cancelled": True}, 200

    def get_generation_status(self, request_id: str) -> tuple[dict, int]:
        request_id = (request_id or "").strip()
        if not self.job_service.is_safe_request_id(request_id):
            return {"success": False, "error": "非法 request_id"}, 400
        job = self.job_service.get_job(request_id)
        if job is None:
            return {"success": False, "error": "生成任务不存在"}, 404
        return {"success": True, "job": job}, 200

    def build_stream_generator(self, request_id: str):
        request_id = (request_id or "").strip()
        job = self.job_service.get_job(request_id)
        terminal = self._terminal_event_from_job(request_id, job)
        queue_sub: queue.Queue | None = None

        def gen():
            nonlocal queue_sub
            yield self._serialize(self._start_event(request_id, job))
            if terminal is not None:
                yield self._serialize(terminal)
                return
            for progress_event in self.job_service.get_progress_events(request_id):
                yield self._serialize(progress_event)
            queue_sub = self.job_service.subscribe(request_id)
            try:
                while True:
                    try:
                        event = queue_sub.get(timeout=15.0)
                    except queue.Empty:
                        yield ":heartbeat\n\n"
                        continue
                    if event is None:
                        return
                    yield self._serialize(event)
            finally:
                if queue_sub is not None:
                    self.job_service.unsubscribe(request_id, queue_sub)

        return gen()

    def classroom_from_generation_preview(
        self,
        *,
        user_id: str,
        request_id: str,
    ) -> dict | None:
        if not self.job_service.is_safe_request_id(request_id):
            return None
        job = self.job_service.get_job(request_id)
        if not job or job.get("status") not in {"running", "done"}:
            return None

        scenes_by_id: dict[str, dict] = {}
        for event in job.get("progress_events") or []:
            if not isinstance(event, dict):
                continue
            scene = event.get("scene_payload")
            if not isinstance(scene, dict):
                continue
            scene_id = str(scene.get("id") or "").strip()
            if scene_id:
                scenes_by_id[scene_id] = scene
        scenes = sorted(
            scenes_by_id.values(),
            key=lambda row: int(row.get("order") or 0)
            if str(row.get("order") or "").isdigit()
            else 999999,
        )
        if not scenes:
            return None

        topic = str(job.get("topic") or "生成中课堂").strip() or "生成中课堂"
        now = self.job_service.now()
        return {
            "id": request_id,
            "user_id": user_id,
            "title": f"{topic}（生成中）",
            "topic": topic,
            "course": "",
            "status": "generating",
            "created_at": job.get("started_at") or now,
            "updated_at": job.get("updated_at") or now,
            "tts": {},
            "student_profile": {},
            "source": {"type": "generation_preview", "request_id": request_id},
            "agents": [],
            "knowledge_points": [topic],
            "scenes": scenes,
        }

    def _start_background_generation(
        self,
        request_id: str,
        generation_kwargs: dict,
    ) -> None:
        def run_generation_job() -> None:
            try:
                payload = self.generator.generate(
                    **generation_kwargs,
                    progress_callback=lambda event: self.job_service.emit(request_id, event),
                )
                self.job_service.mark_done(request_id, payload.get("id"), payload)
                self.job_service.emit(
                    request_id,
                    {
                        "type": "classroom_done",
                        "request_id": request_id,
                        "classroom_id": payload.get("id"),
                        "scene_count": len(payload.get("scenes", [])),
                    },
                )
                self.logger.info(
                    "[INTERACTIVE-CLASSROOM] 后台生成完成 request_id=%s",
                    request_id,
                )
            except ClassroomGenerationCancelled:
                self.job_service.mark_cancelled(request_id)
                self.job_service.emit(
                    request_id,
                    {"type": "classroom_cancelled", "request_id": request_id},
                )
                self.logger.info(
                    "[INTERACTIVE-CLASSROOM] 后台生成已取消 request_id=%s",
                    request_id,
                )
            except Exception as exc:
                self.job_service.mark_error(request_id, str(exc))
                self.job_service.emit(
                    request_id,
                    {
                        "type": "classroom_error",
                        "request_id": request_id,
                        "error": str(exc),
                    },
                )
                self.logger.exception(
                    "[INTERACTIVE-CLASSROOM] 后台生成失败 request_id=%s",
                    request_id,
                )
            finally:
                self.job_service.close_subscribers(request_id)
                self.job_service.finish(request_id)

        thread = threading.Thread(
            target=run_generation_job,
            name=f"classroom-generation-{request_id}",
            daemon=True,
        )
        thread.start()

    def _retrieve_knowledge_context(
        self,
        *,
        user_id: str,
        course: str,
        topic: str,
    ) -> dict | None:
        try:
            return self.course_knowledge_retriever.retrieve_course_context(
                user_id=user_id,
                course=course,
                topic=topic,
            )
        except Exception as exc:
            self.logger.warning(
                "[CLASSROOM-GEN] knowledge_retrieval_failed error=%s",
                type(exc).__name__,
            )
            return None

    @staticmethod
    def _serialize(event: dict) -> str:
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    @staticmethod
    def _terminal_event_from_job(request_id: str, job: dict) -> dict | None:
        status = job.get("status")
        if status == "done":
            return {
                "type": "classroom_done",
                "request_id": request_id,
                "classroom_id": job.get("classroom_id"),
                "scene_count": len((job.get("classroom") or {}).get("scenes", [])),
            }
        if status == "cancelled":
            return {"type": "classroom_cancelled", "request_id": request_id}
        if status == "error":
            return {
                "type": "classroom_error",
                "request_id": request_id,
                "error": job.get("error") or "生成失败",
            }
        return None

    @staticmethod
    def _start_event(request_id: str, job: dict) -> dict:
        return {
            "type": "classroom_start",
            "request_id": request_id,
            "topic": job.get("topic", ""),
            "stages": [stage["key"] for stage in GENERATION_STAGES],
            "stage_total": len(GENERATION_STAGES),
            "stage_labels": {stage["key"]: stage["label"] for stage in GENERATION_STAGES},
            "scene_total": 0,
        }
