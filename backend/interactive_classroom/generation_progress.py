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

class ClassroomGenerationCancelled(Exception):
    """Raised when an interactive classroom generation request is cancelled."""

CancelCheck = Callable[[], bool]

ProgressCallback = Callable[[dict[str, Any]], None]

DEFAULT_ANIMATION_LAB_MAX_TOKENS = 6500

def _emit_progress(
    callback: ProgressCallback | None,
    *,
    stage: str,
    stage_index: int,
    scene_index: int = 0,
    scene_total: int = 0,
    expected_scene_total: int = 0,
    expected_slide_total: int = 0,
    scene: ClassroomScene | None = None,
) -> None:
    """向订阅者推送一帧 progress 事件。callback 抛错不会中断生成。"""
    if callback is None:
        return
    try:
        stage_label = next(
            (s["label"] for s in GENERATION_STAGES if s["key"] == stage),
            stage,
        )
        payload: dict[str, Any] = {
            "type": "classroom_progress",
            "stage": stage,
            "stage_index": stage_index,
            "stage_total": len(GENERATION_STAGES),
            "stage_label": stage_label,
            "scene_index": scene_index,
            "scene_total": scene_total,
        }
        if expected_scene_total:
            payload["expected_scene_total"] = expected_scene_total
        if expected_slide_total:
            payload["expected_slide_total"] = expected_slide_total
        if scene is not None:
            payload["scene"] = {
                "id": scene.id,
                "type": scene.type,
                "title": scene.title,
                "order": scene.order,
            }
            payload["scene_payload"] = {
                "id": scene.id,
                "type": scene.type,
                "title": scene.title,
                "order": scene.order,
                "knowledge_points": scene.knowledge_points,
                "content": scene.content,
                "actions": [
                    {
                        "id": action.id,
                        "type": action.type,
                        "agent_id": action.agent_id,
                        "text": action.text,
                        "audio_url": action.audio_url,
                        "speed": action.speed,
                        "payload": action.payload,
                    }
                    for action in scene.actions
                ],
            }
        callback(payload)
    except Exception:
        # 进度推送永远不能让生成失败；吞掉回调异常
        pass

def _emit_ordered_ready_scenes(
    callback: ProgressCallback | None,
    *,
    stage: str,
    stage_index: int,
    ready_scenes: dict[int, ClassroomScene],
    completed_indexes: set[int] | None = None,
    next_emit_index: int,
    scene_total: int,
    expected_scene_total: int = 0,
    expected_slide_total: int = 0,
) -> int:
    completed = completed_indexes or set(ready_scenes)
    while next_emit_index in completed:
        scene = ready_scenes.get(next_emit_index)
        if scene is not None:
            _emit_progress(
                callback,
                stage=stage,
                stage_index=stage_index,
                scene_index=next_emit_index,
                scene_total=scene_total,
                expected_scene_total=expected_scene_total,
                expected_slide_total=expected_slide_total,
                scene=scene,
            )
        next_emit_index += 1
    return next_emit_index

def _synthesize_scene_speech_actions(
    *,
    service: ClassroomTTSService,
    scene: ClassroomScene,
    audio_dir: str,
    classroom_id: str,
    cancel_check: CancelCheck | None = None,
) -> None:
    for action in scene.actions:
        _raise_if_cancelled(cancel_check)
        if action.type != "speech" or action.audio_url:
            continue
        try:
            filename = service.synthesize_action(action.id, action.text, audio_dir)
        except Exception:
            filename = ""
        if filename:
            action.audio_url = f"/api/interactive-classroom/{classroom_id}/audio/{filename}"

GENERATION_STAGES: list[dict[str, str]] = [
    {"key": "read_ppt",        "label": "读取课件"},
    {"key": "build_scenes",    "label": "组织课堂"},
    {"key": "insert_quizzes",  "label": "生成互动"},
    {"key": "synthesize_tts",  "label": "合成音频"},
    {"key": "save",            "label": "保存跳转"},
]

GENERATION_STAGE_KEYS: tuple[str, ...] = tuple(s["key"] for s in GENERATION_STAGES)

def _raise_if_cancelled(cancel_check: CancelCheck | None) -> None:
    if cancel_check and cancel_check():
        raise ClassroomGenerationCancelled("interactive classroom generation cancelled")

