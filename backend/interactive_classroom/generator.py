from __future__ import annotations

import os
import re
from datetime import datetime
from html import unescape
from typing import Any
from uuid import uuid4

from .schema import ClassroomAction, ClassroomScene, InteractiveClassroom
from .storage import ClassroomStorage
from .tts_service import ClassroomTTSService


def _sorted_svg_files(svg_dir: str) -> list[str]:
    if not os.path.exists(svg_dir):
        return []
    files = [f for f in os.listdir(svg_dir) if f.lower().endswith(".svg")]
    files.sort()
    return files


def _clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _unique_texts(rows: list[str], limit: int = 12) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for row in rows:
        text = _clean_text(row)
        if len(text) < 2 or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _extract_svg_texts(svg: str) -> list[str]:
    matches = re.findall(r"<(?:text|tspan)\b[^>]*>(.*?)</(?:text|tspan)>", svg, flags=re.I | re.S)
    if not matches:
        matches = re.findall(r">([^<>]{2,})<", svg)
    return _unique_texts(matches)


def _split_manuscript(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    sections = [s.strip() for s in re.split(r"\n\s*---+\s*\n", text) if s.strip()]
    if len(sections) > 1:
        return sections
    return [s.strip() for s in re.split(r"\n\s*\n", text) if s.strip()]


def _is_safe_job_id(value: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_.-]{1,128}$", value or ""))


def _brief(text: str, max_len: int = 220) -> str:
    text = _clean_text(text)
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip("，。；、 ") + "。"


class InteractiveClassroomGenerator:
    def __init__(self, backend_dir: str, storage: ClassroomStorage) -> None:
        self.backend_dir = backend_dir
        self.storage = storage

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

    def _build_speech_text(self, idx: int, title: str, svg_texts: list[str], manuscript_note: str = "") -> str:
        if manuscript_note:
            return _brief(manuscript_note)

        key_points = [text for text in svg_texts if text != title][:4]
        if key_points:
            joined = "；".join(key_points)
            return f"这一页的主题是“{title}”。请重点关注：{joined}。我们先把这些关键点串起来理解。"

        return f"现在进入第 {idx} 页“{title}”。这一页主要帮助我们建立整体印象，先抓住标题和页面中的核心关系。"

    def _build_slide_scenes_from_ppt_job(self, user_id: str, ppt_job_id: str) -> list[ClassroomScene]:
        job_dir = self._resolve_ppt_job_dir(user_id, ppt_job_id)
        if not job_dir:
            return []
        svg_dir = os.path.join(job_dir, "svg_final")
        if not os.path.exists(svg_dir):
            svg_dir = os.path.join(job_dir, "svg_output")

        manuscript_notes = self._load_manuscript_notes(job_dir)
        svg_files = _sorted_svg_files(svg_dir)
        scenes: list[ClassroomScene] = []

        for idx, fname in enumerate(svg_files, start=1):
            path = os.path.join(svg_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                svg = f.read()

            svg_texts = _extract_svg_texts(svg)
            title = svg_texts[0] if svg_texts else f"第 {idx} 页"
            manuscript_note = manuscript_notes[idx - 1] if idx - 1 < len(manuscript_notes) else ""
            speech_text = self._build_speech_text(idx, title, svg_texts, manuscript_note)

            scenes.append(
                ClassroomScene(
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
                    },
                    actions=[
                        ClassroomAction(
                            id=f"act_slide_{idx:03d}",
                            type="speech",
                            text=speech_text,
                        )
                    ],
                )
            )
        return scenes

    def _build_fallback_slide_scenes(self, topic: str) -> list[ClassroomScene]:
        slides = [
            ("课程导入", f"欢迎来到《{topic}》交互式课堂。我们先从这个主题解决什么问题开始。"),
            ("核心概念", f"这一部分解释 {topic} 的核心概念、常见误区和一个最容易理解的例子。"),
            ("总结过渡", f"我们先总结一遍 {topic} 的关键点，然后进入随堂测验，看看哪些地方已经掌握。"),
        ]
        scenes: list[ClassroomScene] = []
        for idx, (title, speech) in enumerate(slides, start=1):
            scenes.append(
                ClassroomScene(
                    id=f"scene_slide_{idx:03d}",
                    type="slide",
                    title=title,
                    order=idx,
                    content={"format": "markdown", "markdown": f"## {title}\n\n{speech}"},
                    actions=[ClassroomAction(id=f"act_slide_{idx:03d}", type="speech", text=speech)],
                )
            )
        return scenes

    def _build_quiz_scene(self, order: int, topic: str) -> ClassroomScene:
        return ClassroomScene(
            id="scene_quiz_001",
            type="quiz",
            title=f"随堂测验：{topic}",
            order=order,
            knowledge_points=[topic],
            content={
                "questions": [
                    {
                        "id": "q1",
                        "type": "single",
                        "question": f"学习 {topic} 时，最重要的是先抓住什么？",
                        "options": [
                            {"label": "只记住页面颜色和布局", "value": "A"},
                            {"label": "理解核心概念、适用场景和关键步骤", "value": "B"},
                            {"label": "跳过示例，直接背答案", "value": "C"},
                            {"label": "只看最后一页总结", "value": "D"},
                        ],
                        "answer": ["B"],
                        "analysis": "交互式课堂的目标不是背页面，而是理解概念、场景和步骤之间的关系。",
                        "points": 1,
                        "knowledge_point": topic,
                    },
                    {
                        "id": "q2",
                        "type": "single",
                        "question": "如果答题后发现薄弱点，下一步最合理的做法是？",
                        "options": [
                            {"label": "忽略薄弱点，继续下一章", "value": "A"},
                            {"label": "回到对应页面复听讲解，并完成同类练习", "value": "B"},
                            {"label": "只修改得分显示", "value": "C"},
                            {"label": "重新生成一个完全无关的课堂", "value": "D"},
                        ],
                        "answer": ["B"],
                        "analysis": "反馈要服务于学习闭环，复听、复盘和同类练习最能补强薄弱知识点。",
                        "points": 1,
                        "knowledge_point": "学习反馈",
                    },
                ]
            },
            actions=[],
        )

    def generate(
        self,
        user_id: str,
        topic: str,
        course: str,
        tts_config: dict[str, Any],
        ppt_job_id: str = "",
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        classroom_id = f"cls_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"

        if ppt_job_id:
            scenes = self._build_slide_scenes_from_ppt_job(user_id, ppt_job_id)
            if not scenes:
                scenes = self._build_fallback_slide_scenes(topic)
        else:
            scenes = self._build_fallback_slide_scenes(topic)

        scenes.append(self._build_quiz_scene(order=len(scenes) + 1, topic=topic))
        for idx, scene in enumerate(scenes, start=1):
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
            source={"type": "ppt_svg_job" if ppt_job_id else "topic_fallback", "job_id": ppt_job_id},
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
            knowledge_points=[topic],
            scenes=scenes,
        )

        audio_dir = self.storage.audio_dir(user_id, classroom_id)
        tts = ClassroomTTSService(output_dir=audio_dir, tts_config=tts_config)
        for scene in classroom.scenes:
            for action in scene.actions:
                if action.type != "speech":
                    continue
                try:
                    filename = tts.synthesize_action(action.id, action.text, audio_dir)
                    if filename:
                        action.audio_url = f"/api/interactive-classroom/{classroom_id}/audio/{filename}"
                except Exception:
                    action.audio_url = ""

        payload = classroom.to_dict()
        self.storage.save_classroom(user_id, classroom_id, payload)
        return payload
