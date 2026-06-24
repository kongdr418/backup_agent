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

from .enrichment_scene_builder import (
    ANIMATION_LAB_EMBED_STYLE,
    _inject_animation_embed_style,
    _repair_animation_html_for_display,
    _repair_animation_js_line_comments,
    _sanitize_animation_lab_html,
    _upgrade_animation_canvas_resolution,
)
from .generation_progress import (
    CancelCheck,
    ClassroomGenerationCancelled,
    DEFAULT_ANIMATION_LAB_MAX_TOKENS,
    GENERATION_STAGES,
    GENERATION_STAGE_KEYS,
    ProgressCallback,
    _emit_ordered_ready_scenes,
    _emit_progress,
    _raise_if_cancelled,
    _synthesize_scene_speech_actions,
)
from .scene_content import (
    INTRO_FIRST_SLIDE_TITLE_KEYWORDS,
    INTRO_SLIDE_FULL_TEXT_KEYWORDS,
    INTRO_SLIDE_KEYWORDS,
    QUIZ_SOURCE_INTERACTION_TITLE_KEYWORDS,
    QUIZ_SOURCE_SKIP_KEYWORDS,
    QUIZ_SOURCE_SUMMARY_SKIP_KEYWORDS,
    _brief,
    _build_formula_summary_text,
    _build_highlight_cues,
    _build_highlight_cues_from_teaching_segments,
    _build_learning_process_summary_text,
    _build_process_summary_text,
    _clean_knowledge_point,
    _clean_quiz_text,
    _clean_text,
    _compose_teaching_speech,
    _conceptual_distractors,
    _derive_slide_title,
    _extract_svg_highlight_targets,
    _extract_svg_texts,
    _fallback_teaching_segments,
    _highlight_mode_for_segment,
    _is_decorative_quiz_text,
    _is_explanatory_quiz_sentence,
    _is_generic_quiz_label,
    _is_intro_slide,
    _is_low_quality_quiz_fragment,
    _is_low_signal_teaching_target,
    _is_meaningful_quiz_point,
    _is_meta_practice_question_text,
    _is_quiz_source_scene,
    _is_safe_job_id,
    _match_text_score,
    _merge_short_speech_segments,
    _normalize_generation_strategy,
    _normalize_student_profile,
    _normalize_teaching_segments,
    _option_rows,
    _parse_svg_number,
    _practice_evidence_by_point,
    _question,
    _question_has_scene_index,
    _quiz_points_from_scene,
    _safe_segment_mode,
    _scene_text_snippets,
    _scene_text_values,
    _segments_are_similar,
    _select_teaching_targets,
    _soften_repetitive_classroom_opening,
    _sorted_svg_files,
    _speech_text_from_manuscript,
    _split_manuscript,
    _split_speech_segments,
    _student_profile_hint,
    _supplement_teaching_segments_from_targets,
    _svg_text_content,
    _target_for_teaching_text,
    _teaching_target_score,
    _truncate_speech_text,
    _unique_texts,
    _visible_text_lines_for_prompt,
)
from .slide_scene_builder import SlideSceneBuilderMixin
from .quiz_scene_builder import QuizSceneBuilderMixin
from .enrichment_scene_builder import EnrichmentSceneBuilderMixin
from .generation_pipeline import GenerationPipelineMixin


class InteractiveClassroomGenerator(
    GenerationPipelineMixin,
    EnrichmentSceneBuilderMixin,
    QuizSceneBuilderMixin,
    SlideSceneBuilderMixin,
):
    def __init__(
        self,
        backend_dir: str,
        storage: ClassroomStorage,
        quiz_generator: Any | None = None,
        llm_quiz_enabled: bool = True,
        semantic_reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.backend_dir = backend_dir
        self.storage = storage
        self.quiz_generator = quiz_generator
        self.llm_quiz_enabled = llm_quiz_enabled
        self.semantic_reviewer = semantic_reviewer

    @staticmethod
    def _critic_summary(
        result: CriticResult,
        *,
        retried: bool = False,
        fallback: bool = False,
    ) -> dict[str, Any]:
        summary = result.to_dict()
        summary["retried"] = retried
        summary["fallback"] = fallback
        return summary

    @staticmethod
    def _aggregate_critic_summary(
        mode: str,
        scenes: list[ClassroomScene],
    ) -> dict[str, Any]:
        summaries = [
            scene.content.get("critic")
            for scene in scenes
            if isinstance(scene.content, dict)
            and isinstance(scene.content.get("critic"), dict)
        ]
        issues: list[str] = []
        for summary in summaries:
            for issue in summary.get("issue_codes", []):
                if issue and issue not in issues:
                    issues.append(str(issue))
        return {
            "mode": normalize_critic_mode(mode),
            "checks": len(summaries),
            "llm_checks": sum(bool(row.get("llm_checked")) for row in summaries),
            "retries": sum(bool(row.get("retried")) for row in summaries),
            "fallbacks": sum(bool(row.get("fallback")) for row in summaries),
            "duration_ms": sum(int(row.get("duration_ms", 0) or 0) for row in summaries),
            "issues": issues[:20],
        }
