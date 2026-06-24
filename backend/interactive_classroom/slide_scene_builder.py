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
    _synthesize_scene_speech_actions,
)
from .scene_content import (
    _build_highlight_cues,
    _build_highlight_cues_from_teaching_segments,
    _clean_text,
    _compose_teaching_speech,
    _derive_slide_title,
    _extract_svg_highlight_targets,
    _extract_svg_texts,
    _fallback_teaching_segments,
    _is_intro_slide,
    _is_quiz_source_scene,
    _is_safe_job_id,
    _normalize_generation_strategy,
    _normalize_student_profile,
    _normalize_teaching_segments,
    _safe_segment_mode,
    _select_teaching_targets,
    _sorted_svg_files,
    _speech_text_from_manuscript,
    _split_manuscript,
    _split_speech_segments,
    _student_profile_hint,
    _visible_text_lines_for_prompt,
)

class SlideSceneBuilderMixin:
    def _resolve_ppt_job_dir(self, user_id: str, ppt_job_id: str) -> str:
        if not _is_safe_job_id(ppt_job_id):
            return ""
        user_job_dir = os.path.join(self.backend_dir, "generated_svg_ppt", "users", user_id, ppt_job_id)
        if os.path.exists(user_job_dir):
            return user_job_dir
        return os.path.join(self.backend_dir, "generated_svg_ppt", ppt_job_id)

    def _load_manuscript_notes(self, job_dir: str) -> list[str]:
        manuscript_path = os.path.join(job_dir, "manuscript.md")
        if not os.path.exists(manuscript_path):
            return []
        try:
            with open(manuscript_path, "r", encoding="utf-8") as f:
                return _split_manuscript(f.read())
        except OSError:
            return []

    def _build_speech_text(
        self,
        idx: int,
        title: str,
        svg_texts: list[str],
        manuscript_note: str = "",
        student_profile: dict[str, str] | None = None,
    ) -> str:
        if manuscript_note:
            return _speech_text_from_manuscript(manuscript_note)

        key_points = [text for text in svg_texts if text != title][:4]
        if key_points:
            joined = "；".join(key_points)
            return f"这一页的主题是“{title}”。请重点关注：{joined}。我们先把这些关键点串起来理解。"

        return f"现在进入第 {idx} 页“{title}”。这一页主要帮助我们建立整体印象，先抓住标题和页面中的核心关系。"

    def _profile_from_generation_strategy(
        self,
        generation_strategy: dict[str, Any] | None,
    ) -> dict[str, str]:
        strategy = _normalize_generation_strategy(generation_strategy)
        if not strategy:
            return {}
        focus_points = strategy.get("focus_knowledge_points", [])
        goal_parts = []
        if focus_points:
            goal_parts.append(f"重点补强：{'、'.join(focus_points)}")
        return _normalize_student_profile(
            {
                "basis": strategy.get("explanation_depth", ""),
                "goal": "；".join(goal_parts),
                "style": "+".join(strategy.get("content_style", [])),
                "difficulty": strategy.get("quiz_difficulty", ""),
            }
        )

    @staticmethod
    def _merge_knowledge_points(
        base_points: list[str],
        knowledge_context: dict[str, Any] | None,
    ) -> list[str]:
        if not knowledge_context:
            return base_points
        standard_points = knowledge_context.get("knowledge_points", [])
        merged = list(base_points)
        for kp in standard_points:
            label = kp.get("label", "").strip() if isinstance(kp, dict) else str(kp).strip()
            if label and label not in merged:
                merged.append(label)
        return merged

    def _build_teaching_segments_prompt(
        self,
        *,
        page_index: int,
        page_total: int,
        title: str,
        manuscript_note: str,
        targets: list[dict[str, Any]],
        svg_texts: list[str],
        student_profile: dict[str, str] | None = None,
        is_intro: bool = False,
    ) -> str:
        target_lines = []
        prompt_targets = _select_teaching_targets(targets)
        for target in prompt_targets:
            target_lines.append(f"- id: {target.get('id')}｜text: {target.get('text')}")
        visible_lines = [f"- {text}" for text in _visible_text_lines_for_prompt(svg_texts, targets)]
        profile_hint = _student_profile_hint(_normalize_student_profile(student_profile))
        position = "first" if page_index == 1 else ("last" if page_index == page_total else "middle")
        is_last = page_total > 1 and page_index == page_total
        if is_intro:
            length_rules = (
                "2. 输出 1 到 2 个 segments，总计不超过 140 个中文字符；每段 35 到 80 个中文字符。\n"
                "3. 这是标题/封面页，只做主题导入和学习方向提示，不要展开后续页面的知识点，"
                "不要在标题页讲完整节课。"
            )
        elif is_last:
            length_rules = (
                "2. 输出 1 到 3 个 segments，总计不超过 260 个中文字符；每段 40 到 110 个中文字符。\n"
                "3. 只提炼结论和下一步，不要逐页复述整堂课。"
            )
        else:
            length_rules = (
                "2. 输出 3 到 4 个 segments，总计不超过 420 个中文字符；每段 45 到 130 个中文字符。\n"
                "3. 每段只讲一个当前页面能看到的具体结构、标签、流程箭头、实验卡片或目标条，"
                "不要写跨页总结、职业发展展望或泛泛的学习鸡汤。"
            )
        return f"""你是智创空间智慧课堂的授课脚本设计智能体。请基于本页 PPT 的可见文字和原始备注，生成自然口语化的讲解段，并让每段讲解绑定一个高亮目标。

## 页面位置
第 {page_index} / {page_total} 页，position={position}

## 页面标题
{title}

## 原始 PPT 备注/讲稿
{manuscript_note or "无"}

## 本页可见文字
{chr(10).join(visible_lines) or "无"}

## 可高亮目标
{chr(10).join(target_lines) or "无"}

## 学生画像
{profile_hint or "无"}

## 要求
1. 直接返回 JSON，不要 Markdown 代码块。
{length_rules}
4. 每个 segment 必须从可高亮目标中选择 target_id；高亮目标少时就减少段数，不得为了凑段数重复 target_id。
5. 不得重复句子、结论、例子或同义改写；原始备注与可见文字重复时只讲一次。
6. 口语化，像老师在讲课，但不要照抄 PPT，不要使用“接下来我们再来看看”一类空泛填充句。
7. 讲稿必须和当前 target 的文字实际对应：讲“图像分类”就绑定“图像分类”，讲“目标检测”就绑定“目标检测”。
8. 第一段或真正强调“重点/核心/关键”的段落 mode 用 "spotlight"，其他用 "outline"。
9. 中间页不要寒暄；第一页仅在封面页自然开场；最后一页可简短总结。
10. 中间页如果出现流程、步骤、公式、输出或核心要点，必须覆盖前中后关键环节，不要只讲开头几个标签。
11. 如果页面有编号、卡片或底部目标条，至少选择其中两个具体元素讲清楚它们的关系；不要把它们合并成一段大而空的总结。
12. 不要主动补充页面没有出现的信息；不要使用“为未来学习和职业发展做好准备”这类泛化结尾。

## JSON 格式
{{
  "segments": [
    {{"target_id": "hl_001", "mode": "spotlight", "text": "讲解内容"}},
    {{"target_id": "hl_002", "mode": "outline", "text": "讲解内容"}}
  ]
}}"""

    def _generate_teaching_segments(
        self,
        *,
        page_index: int,
        page_total: int,
        title: str,
        manuscript_note: str,
        targets: list[dict[str, Any]],
        svg_texts: list[str],
        student_profile: dict[str, str] | None = None,
        critic_mode: str = "off",
        knowledge_context: dict[str, Any] | None = None,
        include_critic: bool = False,
        semantic_reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        is_intro: bool = False,
    ) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
        valid_ids = {str(target.get("id")) for target in targets if target.get("id")}
        mode = normalize_critic_mode(critic_mode)
        is_last = page_total > 1 and page_index == page_total and not is_intro
        grounding = build_grounding_context(
            knowledge_context=knowledge_context,
            visible_texts=svg_texts,
            manuscript_note=manuscript_note,
        )
        critic = ClassroomCriticService(
            mode=mode,
            semantic_reviewer=semantic_reviewer or self.semantic_reviewer,
        )
        last_result = CriticResult(
            passed=False,
            severity="error",
            issue_codes=["generation_failed"],
            grounding_level=grounding.level,
            retry_required=True,
        )
        if targets and self.llm_quiz_enabled:
            for attempt in range(2):
                try:
                    quiz_generator = self._get_quiz_generator()
                    prompt = self._build_teaching_segments_prompt(
                        page_index=page_index,
                        page_total=page_total,
                        title=title,
                        manuscript_note=manuscript_note,
                        targets=targets,
                        svg_texts=svg_texts,
                        student_profile=student_profile,
                        is_intro=is_intro,
                    )
                    if attempt:
                        prompt += (
                            "\n\n上一次输出未通过检查。请修复过长、重复、目标绑定错误、"
                            "依据不足或内部画像字段泄露问题。不要增加段数，仍按原 JSON 结构返回。"
                        )
                    raw = quiz_generator._call_llm(prompt)  # noqa: SLF001
                    data = json.loads(self._clean_llm_json(raw))
                    rows = data.get("segments") if isinstance(data, dict) else None
                    segments: list[dict[str, Any]] = []
                    if isinstance(rows, list):
                        for row in rows:
                            if not isinstance(row, dict):
                                continue
                            target_id = str(row.get("target_id") or "").strip()
                            text = _clean_text(str(row.get("text") or ""))
                            if not target_id or len(text) < 12:
                                continue
                            segments.append(
                                {
                                    "target_id": target_id,
                                    "mode": _safe_segment_mode(row.get("mode"), "outline"),
                                    "text": text,
                                }
                            )
                            if len(segments) >= 6:
                                break
                    segments = _normalize_teaching_segments(
                        segments,
                        is_intro=is_intro,
                        is_last=is_last,
                    )
                    last_result = critic.review_teaching_segments(
                        segments=segments,
                        valid_target_ids=valid_ids,
                        grounding=grounding,
                        is_intro=is_intro,
                        is_last=is_last,
                    )
                    if segments and last_result.passed:
                        summary = self._critic_summary(
                            last_result,
                            retried=attempt > 0,
                        )
                        return (segments, summary) if include_critic else segments
                except Exception:
                    last_result = CriticResult(
                        passed=False,
                        severity="error",
                        issue_codes=["generation_failed"],
                        grounding_level=grounding.level,
                        retry_required=True,
                    )

        fallback_segments = _fallback_teaching_segments(
            title,
            manuscript_note,
            targets,
            svg_texts,
            is_intro=is_intro,
            is_last=is_last,
        )
        summary = self._critic_summary(
            last_result,
            retried=targets and self.llm_quiz_enabled,
            fallback=True,
        )
        return (fallback_segments, summary) if include_critic else fallback_segments

    def _build_slide_scenes_from_ppt_job(
        self,
        user_id: str,
        ppt_job_id: str,
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
        tts_service: ClassroomTTSService | None = None,
        audio_dir: str = "",
        classroom_id: str = "",
        critic_mode: str = "off",
        knowledge_context: dict[str, Any] | None = None,
        semantic_reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> list[ClassroomScene]:
        job_dir = self._resolve_ppt_job_dir(user_id, ppt_job_id)
        if not job_dir:
            return []
        svg_dir = os.path.join(job_dir, "svg_final")
        if not os.path.exists(svg_dir):
            svg_dir = os.path.join(job_dir, "svg_output")

        manuscript_notes = self._load_manuscript_notes(job_dir)
        svg_files = _sorted_svg_files(svg_dir)
        scenes: list[ClassroomScene] = []
        if not svg_files:
            return scenes

        # 阶段 1 推进：开始读课件
        _emit_progress(
            progress_callback,
            stage="read_ppt",
            stage_index=0,
            scene_index=0,
            scene_total=len(svg_files),
        )
        # 阶段 2 推进：开始组织课堂
        _emit_progress(
            progress_callback,
            stage="build_scenes",
            stage_index=1,
            scene_index=0,
            scene_total=len(svg_files),
        )

        for idx, fname in enumerate(svg_files, start=1):
            _raise_if_cancelled(cancel_check)
            scene = self._build_single_slide_scene_from_svg(
                idx,
                fname,
                svg_dir,
                manuscript_notes[idx - 1] if idx - 1 < len(manuscript_notes) else "",
                len(svg_files),
                ppt_job_id,
                student_profile,
                cancel_check,
                critic_mode,
                knowledge_context,
                semantic_reviewer,
            )
            scenes.append(scene)

            if tts_service is None or not audio_dir or not classroom_id:
                _emit_progress(
                    progress_callback,
                    stage="build_scenes",
                    stage_index=1,
                    scene_index=idx,
                    scene_total=len(svg_files),
                    scene=scene,
                )
                continue

            _emit_progress(
                progress_callback,
                stage="synthesize_tts",
                stage_index=3,
                scene_index=idx - 1,
                scene_total=len(svg_files),
            )
            _synthesize_scene_speech_actions(
                service=tts_service,
                scene=scene,
                audio_dir=audio_dir,
                classroom_id=classroom_id,
                cancel_check=cancel_check,
            )
            _emit_progress(
                progress_callback,
                stage="synthesize_tts",
                stage_index=3,
                scene_index=idx,
                scene_total=len(svg_files),
                scene=scene,
            )
        return scenes

    def _load_ppt_job_sources(
        self,
        user_id: str,
        ppt_job_id: str,
    ) -> tuple[str, list[str], list[str]]:
        job_dir = self._resolve_ppt_job_dir(user_id, ppt_job_id)
        if not job_dir:
            return "", [], []
        svg_dir = os.path.join(job_dir, "svg_final")
        if not os.path.exists(svg_dir):
            svg_dir = os.path.join(job_dir, "svg_output")
        return svg_dir, _sorted_svg_files(svg_dir), self._load_manuscript_notes(job_dir)

    def _build_slide_probe_from_svg(
        self,
        idx: int,
        fname: str,
        svg_dir: str,
        manuscript_note: str = "",
    ) -> ClassroomScene:
        path = os.path.join(svg_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            svg = f.read()
        svg_texts = _extract_svg_texts(svg)
        title = _derive_slide_title(idx, fname, svg_texts, manuscript_note)
        return ClassroomScene(
            id=f"scene_slide_{idx:03d}",
            type="slide",
            title=title,
            order=idx,
            knowledge_points=svg_texts[:4],
            content={"extracted_text": svg_texts},
            actions=[],
        )

    def _plan_quiz_jobs_by_slide_id(
        self,
        slide_probes: list[ClassroomScene],
    ) -> dict[str, dict[str, Any]]:
        quiz_source_slides = [
            scene
            for i, scene in enumerate(slide_probes)
            if _is_quiz_source_scene(scene, is_first_slide=(i == 0))
        ]
        if not quiz_source_slides and slide_probes:
            quiz_source_slides = list(slide_probes)

        quiz_source_ids = {scene.id for scene in quiz_source_slides}
        total_quiz_source_slides = len(quiz_source_slides)
        quiz_source_index = 0
        quiz_index = 1
        pending_slide_ids: list[str] = []
        jobs_by_after_slide_id: dict[str, dict[str, Any]] = {}

        for scene in slide_probes:
            if scene.id not in quiz_source_ids:
                continue
            quiz_source_index += 1
            pending_slide_ids.append(scene.id)

            is_last = quiz_source_index == total_quiz_source_slides
            enough_for_mid_quiz = len(pending_slide_ids) >= 3 and not is_last
            enough_for_final_quiz = is_last and pending_slide_ids
            if not (enough_for_mid_quiz or enough_for_final_quiz):
                continue

            jobs_by_after_slide_id[scene.id] = {
                "quiz_index": quiz_index,
                "source_ids": list(pending_slide_ids),
                "max_questions": 2 if not is_last else 3,
                "require_short_answer": quiz_index % 3 == 0,
            }
            quiz_index += 1
            pending_slide_ids = []

        return jobs_by_after_slide_id

    @staticmethod
    def _resolve_animation_after_slide_id(
        animation_scene: ClassroomScene | None,
        slide_probes: list[ClassroomScene],
    ) -> str:
        if animation_scene is None or not slide_probes:
            return ""
        slide_ids = {scene.id for scene in slide_probes}
        placement_after_scene_id = str(
            (animation_scene.content or {}).get("placement_after_scene_id") or ""
        ).strip()
        if placement_after_scene_id in slide_ids:
            return placement_after_scene_id

        for idx, scene in enumerate(slide_probes):
            if _is_quiz_source_scene(scene, is_first_slide=(idx == 0)):
                return scene.id
        return slide_probes[0].id

    def _build_ordered_scenes_from_ppt_job(
        self,
        *,
        user_id: str,
        ppt_job_id: str,
        topic: str,
        course: str,
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
        tts_service: ClassroomTTSService | None = None,
        audio_dir: str = "",
        classroom_id: str = "",
        critic_mode: str = "off",
        knowledge_context: dict[str, Any] | None = None,
        semantic_reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> list[ClassroomScene]:
        svg_dir, svg_files, manuscript_notes = self._load_ppt_job_sources(user_id, ppt_job_id)
        if not svg_files:
            return []

        _emit_progress(
            progress_callback,
            stage="read_ppt",
            stage_index=0,
            scene_index=0,
            scene_total=len(svg_files),
        )

        slide_probes = [
            self._build_slide_probe_from_svg(
                idx,
                fname,
                svg_dir,
                manuscript_notes[idx - 1] if idx - 1 < len(manuscript_notes) else "",
            )
            for idx, fname in enumerate(svg_files, start=1)
        ]
        quiz_jobs_by_after_slide_id = self._plan_quiz_jobs_by_slide_id(slide_probes)
        animation_scene = (
            self._maybe_build_animation_lab_scene(
                topic=topic,
                course=course or "通用课程",
                scenes=slide_probes,
                student_profile=student_profile,
                cancel_check=cancel_check,
            )
            if semantic_reviewer is not None
            else None
        )
        animation_after_slide_id = self._resolve_animation_after_slide_id(animation_scene, slide_probes)
        expected_mindmap = len(slide_probes) >= 2
        expected_scene_total = (
            len(slide_probes)
            + len(quiz_jobs_by_after_slide_id)
            + (1 if animation_scene is not None else 0)
            + (1 if expected_mindmap else 0)
        )

        _emit_progress(
            progress_callback,
            stage="build_scenes",
            stage_index=1,
            scene_index=0,
            scene_total=expected_scene_total,
            expected_scene_total=expected_scene_total,
            expected_slide_total=len(slide_probes),
        )

        scenes: list[ClassroomScene] = []
        generated_slides_by_id: dict[str, ClassroomScene] = {}
        completed_quiz_jobs = 0
        animation_inserted = False

        def _append_and_emit(
            scene: ClassroomScene,
            *,
            stage: str,
            stage_index: int,
            scene_index: int,
            scene_total: int,
        ) -> None:
            scene.order = len(scenes) + 1
            scenes.append(scene)
            _emit_progress(
                progress_callback,
                stage=stage,
                stage_index=stage_index,
                scene_index=scene_index,
                scene_total=scene_total,
                expected_scene_total=expected_scene_total,
                expected_slide_total=len(slide_probes),
                scene=scene,
            )

        for idx, fname in enumerate(svg_files, start=1):
            _raise_if_cancelled(cancel_check)
            slide_scene = self._build_single_slide_scene_from_svg(
                idx,
                fname,
                svg_dir,
                manuscript_notes[idx - 1] if idx - 1 < len(manuscript_notes) else "",
                len(svg_files),
                ppt_job_id,
                student_profile,
                cancel_check,
                critic_mode,
                knowledge_context,
                semantic_reviewer,
            )
            if tts_service is not None and audio_dir and classroom_id:
                _synthesize_scene_speech_actions(
                    service=tts_service,
                    scene=slide_scene,
                    audio_dir=audio_dir,
                    classroom_id=classroom_id,
                    cancel_check=cancel_check,
                )
            generated_slides_by_id[slide_scene.id] = slide_scene
            _append_and_emit(
                slide_scene,
                stage="build_scenes",
                stage_index=1,
                scene_index=len(scenes) + 1,
                scene_total=expected_scene_total,
            )

            if (
                animation_scene is not None
                and not animation_inserted
                and animation_after_slide_id == slide_scene.id
            ):
                animation_inserted = True
                _append_and_emit(
                    animation_scene,
                    stage="build_scenes",
                    stage_index=1,
                    scene_index=len(scenes) + 1,
                    scene_total=expected_scene_total,
                )

            quiz_job = quiz_jobs_by_after_slide_id.get(slide_scene.id)
            if quiz_job is None:
                continue

            completed_quiz_jobs += 1
            quiz_source_scenes = [
                generated_slides_by_id[scene_id]
                for scene_id in quiz_job["source_ids"]
                if scene_id in generated_slides_by_id
            ]
            quiz_scene = self._build_quiz_scene(
                quiz_index=int(quiz_job["quiz_index"]),
                order=len(scenes) + 1,
                topic=topic,
                scenes=quiz_source_scenes,
                max_questions=int(quiz_job["max_questions"]),
                student_profile=student_profile,
                cancel_check=cancel_check,
                progress_callback=progress_callback,
                require_short_answer=bool(quiz_job["require_short_answer"]),
                critic_mode=critic_mode,
                knowledge_context=knowledge_context,
                semantic_reviewer=semantic_reviewer,
            )
            if quiz_scene is None:
                _emit_progress(
                    progress_callback,
                    stage="insert_quizzes",
                    stage_index=2,
                    scene_index=completed_quiz_jobs,
                    scene_total=len(quiz_jobs_by_after_slide_id),
                    expected_scene_total=expected_scene_total,
                    expected_slide_total=len(slide_probes),
                )
                continue

            self._renumber_quiz_scenes([*scenes, quiz_scene], topic)
            _append_and_emit(
                quiz_scene,
                stage="insert_quizzes",
                stage_index=2,
                scene_index=completed_quiz_jobs,
                scene_total=len(quiz_jobs_by_after_slide_id),
            )

        if animation_scene is not None and not animation_inserted:
            _append_and_emit(
                animation_scene,
                stage="build_scenes",
                stage_index=1,
                scene_index=len(scenes) + 1,
                scene_total=expected_scene_total,
            )

        if expected_mindmap:
            _raise_if_cancelled(cancel_check)
            mindmap_scene = self._build_mindmap_scene(
                topic,
                list(scenes),
                student_profile,
                cancel_check,
            )
            if mindmap_scene is not None:
                _append_and_emit(
                    mindmap_scene,
                    stage="build_scenes",
                    stage_index=1,
                    scene_index=len(scenes) + 1,
                    scene_total=expected_scene_total,
                )

        return scenes

    def _build_single_slide_scene_from_svg(
        self,
        idx: int,
        fname: str,
        svg_dir: str,
        manuscript_note: str,
        page_total: int,
        ppt_job_id: str,
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        critic_mode: str = "off",
        knowledge_context: dict[str, Any] | None = None,
        semantic_reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> ClassroomScene:
        _raise_if_cancelled(cancel_check)
        path = os.path.join(svg_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            svg = f.read()

        svg_texts = _extract_svg_texts(svg)
        title = _derive_slide_title(idx, fname, svg_texts, manuscript_note)
        highlight_targets = _extract_svg_highlight_targets(svg)
        intro_probe = ClassroomScene(
            id=f"scene_slide_{idx:03d}",
            type="slide",
            title=title,
            order=idx,
            knowledge_points=svg_texts[:4],
            content={"extracted_text": svg_texts},
        )
        is_intro = _is_intro_slide(intro_probe, is_first_slide=idx == 1) or (
            idx == 1
            and len(svg_texts) <= 2
            and not manuscript_note
        )
        teaching_result = self._generate_teaching_segments(
            page_index=idx,
            page_total=page_total,
            title=title,
            manuscript_note=manuscript_note,
            targets=highlight_targets,
            svg_texts=svg_texts,
            student_profile=student_profile,
            critic_mode=critic_mode,
            knowledge_context=knowledge_context,
            include_critic=True,
            semantic_reviewer=semantic_reviewer,
            is_intro=is_intro,
        )
        if (
            isinstance(teaching_result, tuple)
            and len(teaching_result) == 2
            and isinstance(teaching_result[1], dict)
        ):
            teaching_segments, critic_summary = teaching_result
        else:
            teaching_segments = teaching_result  # type: ignore[assignment]
            critic_summary = {}
        speech_text = _compose_teaching_speech(teaching_segments)
        if not speech_text:
            speech_text = self._build_speech_text(idx, title, svg_texts, manuscript_note, student_profile)
            teaching_segments = [
                {"target_id": item["target_id"], "mode": item["mode"], "text": item["label"]}
                for item in _build_highlight_cues(_split_speech_segments(speech_text), highlight_targets)
            ]
        speech_segments = [
            str(item.get("text") or "").strip()
            for item in teaching_segments
            if str(item.get("text") or "").strip()
        ]
        highlight_cues = _build_highlight_cues_from_teaching_segments(teaching_segments)

        return ClassroomScene(
            id=f"scene_slide_{idx:03d}",
            type="slide",
            title=title,
            order=idx,
            knowledge_points=svg_texts[:4],
            content={
                "format": "svg",
                "svg": svg,
                "ppt_slide": {"job_id": ppt_job_id, "page": idx, "filename": fname},
                "extracted_text": svg_texts,
                "speech_source": "manuscript" if manuscript_note else "svg_text",
                "speech_segments": speech_segments,
                "highlight_targets": highlight_targets,
                "critic": critic_summary,
            },
            actions=[
                ClassroomAction(
                    id=f"act_slide_{idx:03d}",
                    type="speech",
                    text=speech_text,
                    payload={"highlight_cues": highlight_cues},
                )
            ],
        )

    def _build_fallback_slide_scenes(
        self,
        topic: str,
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[ClassroomScene]:
        _raise_if_cancelled(cancel_check)
        profile_hint = _student_profile_hint(_normalize_student_profile(student_profile))
        suffix = f"本节会按学生画像调整：{profile_hint}。" if profile_hint else ""
        slides = [
            ("课程导入", f"欢迎来到《{topic}》交互式课堂。我们先从这个主题解决什么问题开始。{suffix}"),
            ("核心概念", f"这一部分解释 {topic} 的核心概念、常见误区和一个最容易理解的例子。{suffix}"),
            ("总结过渡", f"我们先总结一遍 {topic} 的关键点，然后进入随堂测验，看看哪些地方已经掌握。{suffix}"),
        ]
        _emit_progress(
            progress_callback,
            stage="read_ppt",
            stage_index=0,
            scene_index=0,
            scene_total=len(slides),
        )
        _emit_progress(
            progress_callback,
            stage="build_scenes",
            stage_index=1,
            scene_index=0,
            scene_total=len(slides),
        )
        scenes: list[ClassroomScene] = []
        for idx, (title, speech) in enumerate(slides, start=1):
            _raise_if_cancelled(cancel_check)
            scene = ClassroomScene(
                id=f"scene_slide_{idx:03d}",
                type="slide",
                title=title,
                order=idx,
                content={"format": "markdown", "markdown": f"## {title}\n\n{speech}"},
                actions=[ClassroomAction(id=f"act_slide_{idx:03d}", type="speech", text=speech)],
            )
            scenes.append(scene)
            _emit_progress(
                progress_callback,
                stage="build_scenes",
                stage_index=1,
                scene_index=idx,
                scene_total=len(slides),
                scene=scene,
            )
        return scenes

