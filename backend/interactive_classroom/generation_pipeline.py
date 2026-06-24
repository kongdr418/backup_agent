from __future__ import annotations

import asyncio
import os
import re
import json
from datetime import datetime
from difflib import SequenceMatcher
from html import unescape
from typing import Any, Callable
from uuid import uuid4

from .critic_service import (
    ClassroomCriticService,
    CriticResult,
    build_grounding_context,
    normalize_critic_mode,
)
from .schema import ClassroomAction, ClassroomScene, InteractiveClassroom
from .storage import ClassroomStorage
from .tts_service import (
    DEFAULT_TTS_MAX_CONCURRENCY,
    ClassroomTTSService,
    synthesize_actions_parallel_with_progress,
)

from .generation_progress import (
    CancelCheck,
    ProgressCallback,
    _emit_progress,
    _raise_if_cancelled,
)
from .scene_content import (
    _clean_text,
    _normalize_generation_strategy,
    _normalize_student_profile,
)

class GenerationPipelineMixin:
    def generate(
        self,
        user_id: str,
        topic: str,
        course: str,
        tts_config: dict[str, Any],
        ppt_job_id: str = "",
        student_profile: dict[str, Any] | None = None,
        generation_strategy: dict[str, Any] | None = None,
        knowledge_context: dict[str, Any] | None = None,
        lineage: dict[str, Any] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
        critic_mode: str = "standard",
        semantic_reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        _raise_if_cancelled(cancel_check)
        now = datetime.now().isoformat()
        classroom_id = f"cls_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        lineage = lineage if isinstance(lineage, dict) else {}
        parent_classroom_id = _clean_text(str(lineage.get("parent_classroom_id") or ""))[:128]
        course_root_id = _clean_text(str(lineage.get("course_root_id") or ""))[:128] or (
            parent_classroom_id or classroom_id
        )
        try:
            lesson_depth = max(0, int(lineage.get("lesson_depth", 0) or 0))
        except (TypeError, ValueError):
            lesson_depth = 0
        try:
            lesson_index = max(1, int(lineage.get("lesson_index", 1) or 1))
        except (TypeError, ValueError):
            lesson_index = 1
        lesson_kind = _clean_text(str(lineage.get("lesson_kind") or ""))[:40] or (
            "next_lesson" if parent_classroom_id else "root"
        )
        normalized_strategy = _normalize_generation_strategy(generation_strategy)
        normalized_critic_mode = normalize_critic_mode(critic_mode)
        normalized_profile = (
            self._profile_from_generation_strategy(normalized_strategy)
            if normalized_strategy
            else _normalize_student_profile(student_profile)
        )
        audio_dir = self.storage.audio_dir(user_id, classroom_id)
        tts = ClassroomTTSService(output_dir=audio_dir, tts_config=tts_config)
        scenes_are_materialized = False

        if ppt_job_id:
            scenes = self._build_ordered_scenes_from_ppt_job(
                user_id=user_id,
                ppt_job_id=ppt_job_id,
                topic=topic,
                course=course,
                student_profile=normalized_profile,
                cancel_check=cancel_check,
                progress_callback=progress_callback,
                tts_service=tts,
                audio_dir=audio_dir,
                classroom_id=classroom_id,
                critic_mode=normalized_critic_mode,
                knowledge_context=knowledge_context,
                semantic_reviewer=semantic_reviewer,
            )
            scenes_are_materialized = bool(scenes)
            if not scenes:
                scenes = self._build_fallback_slide_scenes(
                    topic, normalized_profile, cancel_check, progress_callback
                )
        else:
            scenes = self._build_fallback_slide_scenes(
                topic, normalized_profile, cancel_check, progress_callback
            )

        _raise_if_cancelled(cancel_check)
        if scenes_are_materialized:
            for idx, scene in enumerate(scenes, start=1):
                _raise_if_cancelled(cancel_check)
                scene.order = idx
        else:
            slide_count = sum(1 for s in scenes if s.type == "slide")
            animation_scene = (
                self._maybe_build_animation_lab_scene(
                    topic=topic,
                    course=course or "通用课程",
                    scenes=scenes,
                    student_profile=normalized_profile,
                    cancel_check=cancel_check,
                )
                if semantic_reviewer is not None
                else None
            )
            if animation_scene is not None:
                scenes = self._insert_animation_lab_scene(scenes, animation_scene)

            if slide_count >= 2:
                scenes = self._insert_quiz_scenes(
                    topic,
                    scenes,
                    normalized_profile,
                    cancel_check,
                    progress_callback,
                    expected_extra_scene_count=1,
                    critic_mode=normalized_critic_mode,
                    knowledge_context=knowledge_context,
                    semantic_reviewer=semantic_reviewer,
                )
                _raise_if_cancelled(cancel_check)
                mindmap_scene = self._build_mindmap_scene(
                    topic,
                    list(scenes),
                    normalized_profile,
                    cancel_check,
                )
                if mindmap_scene is not None:
                    mindmap_scene.order = len(scenes) + 1
                    scenes.append(mindmap_scene)
                    _emit_progress(
                        progress_callback,
                        stage="build_scenes",
                        stage_index=1,
                        scene_index=len(scenes),
                        scene_total=len(scenes),
                        scene=mindmap_scene,
                    )
            else:
                scenes = self._insert_quiz_scenes(
                    topic,
                    scenes,
                    normalized_profile,
                    cancel_check,
                    progress_callback,
                    critic_mode=normalized_critic_mode,
                    knowledge_context=knowledge_context,
                    semantic_reviewer=semantic_reviewer,
                )

            for idx, scene in enumerate(scenes, start=1):
                _raise_if_cancelled(cancel_check)
                scene.order = idx

        classroom = InteractiveClassroom(
            id=classroom_id,
            user_id=user_id,
            title=f"{topic}交互式课堂",
            topic=topic,
            course=course or "通用课程",
            status="ready",
            created_at=now,
            updated_at=now,
            tts={
                "provider": tts_config.get("provider", ""),
                "model": tts_config.get("model", ""),
                "voice": tts_config.get("voice", ""),
            },
            student_profile=normalized_profile,
            generation_strategy=normalized_strategy,
            course_root_id=course_root_id,
            parent_classroom_id=parent_classroom_id,
            lesson_depth=lesson_depth,
            lesson_index=lesson_index,
            lesson_kind=lesson_kind,
            source={"type": "ppt_svg_job" if ppt_job_id else "topic_fallback", "job_id": ppt_job_id},
            critic_summary=self._aggregate_critic_summary(
                normalized_critic_mode,
                scenes,
            ),
            agents=[
                {
                    "id": "teacher",
                    "name": "AI 教师",
                    "role": "teacher",
                    "avatar": "",
                    "color": "#0f766e",
                    "persona": "讲解清晰，先讲重点，再做练习。",
                }
            ],
            knowledge_points=self._merge_knowledge_points([topic], knowledge_context),
            scenes=scenes,
        )

        # 阶段 4：合成音频（并发）
        speech_actions: list[tuple[ClassroomScene, ClassroomAction]] = []
        for scene in classroom.scenes:
            for action in scene.actions:
                if action.type == "speech" and not action.audio_url:
                    speech_actions.append((scene, action))
        _emit_progress(
            progress_callback,
            stage="synthesize_tts",
            stage_index=3,
            scene_index=0,
            scene_total=len(speech_actions),
        )

        if speech_actions:
            # 把 (scene, action) 拍平为 (action_id, text) 给并行函数
            # 保留 scene 引用以便 on_action_done 回写 audio_url
            action_by_id: dict[str, ClassroomAction] = {
                a.id: a for _, a in speech_actions
            }
            scene_by_action_id: dict[str, ClassroomScene] = {
                a.id: scene for scene, a in speech_actions
            }
            tts_input: list[tuple[str, str]] = [
                (a.id, a.text) for _, a in speech_actions
            ]

            def _on_tts_done(
                done_idx: int,
                total: int,
                action_id: str,
                filename: str | None,
                error: Exception | None,
            ) -> None:
                # 写回 audio_url（成功才有 filename）
                action = action_by_id.get(action_id)
                if action is not None and filename:
                    action.audio_url = (
                        f"/api/interactive-classroom/{classroom_id}/audio/{filename}"
                    )
                scene = scene_by_action_id.get(action_id)
                # 推 progress（按完成顺序，不一定是输入顺序）
                _emit_progress(
                    progress_callback,
                    stage="synthesize_tts",
                    stage_index=3,
                    scene_index=done_idx,
                    scene_total=total,
                    scene=scene,
                )

            # ClassroomGenerationCancelled 由并行函数内部透传，asyncio.run 会重新抛
            # 其它异常会冒泡到 run_generation_job 的 except 分支标记 error
            asyncio.run(
                synthesize_actions_parallel_with_progress(
                    service=tts,
                    actions=tts_input,
                    output_dir=audio_dir,
                    max_concurrency=DEFAULT_TTS_MAX_CONCURRENCY,
                    cancel_check=cancel_check,
                    on_action_done=_on_tts_done,
                )
            )

        _raise_if_cancelled(cancel_check)
        # 阶段 5：保存
        _emit_progress(
            progress_callback,
            stage="save",
            stage_index=4,
            scene_index=0,
            scene_total=1,
        )
        payload = classroom.to_dict()
        self.storage.save_classroom(user_id, classroom_id, payload)
        _emit_progress(
            progress_callback,
            stage="save",
            stage_index=4,
            scene_index=1,
            scene_total=1,
        )
        return payload

