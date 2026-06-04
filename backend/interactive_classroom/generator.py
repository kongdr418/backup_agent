from __future__ import annotations

import os
import re
import json
from datetime import datetime
from html import unescape
from typing import Any, Callable
from uuid import uuid4

from .schema import ClassroomAction, ClassroomScene, InteractiveClassroom
from .storage import ClassroomStorage
from .tts_service import ClassroomTTSService


class ClassroomGenerationCancelled(Exception):
    """Raised when an interactive classroom generation request is cancelled."""


CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[dict[str, Any]], None]


def _emit_progress(
    callback: ProgressCallback | None,
    *,
    stage: str,
    stage_index: int,
    scene_index: int = 0,
    scene_total: int = 0,
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
        if scene is not None:
            payload["scene"] = {
                "id": scene.id,
                "type": scene.type,
                "title": scene.title,
                "order": scene.order,
            }
        callback(payload)
    except Exception:
        # 进度推送永远不能让生成失败；吞掉回调异常
        pass


# 阶段定义：与前端 classRoomProgressSteps 的标题一一对应
# 前端若要改名同步改两处
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


def _clean_quiz_text(value: str) -> str:
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
        # 过滤 SVG 里的占位符文本，如 slide_001、page 1、（slide_001 关键点）等
        if re.search(r"\b(slide|page)[_\-\s]*\d+\b", text, flags=re.I):
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


def _clean_knowledge_point(value: str) -> str:
    """清洗 LLM 直给的 knowledge_point 文本。

    LLM 经常把页面占位符粘进来，例：
      "page 15 关键点：布尔索引筛选"
      "slide_5 要点:xxx"
      "  page15关键点：xxx"

    目标：剥掉 "page N" / "slide N" 和 "关键点" / "要点" 这类前缀，
    保留真正的核心内容（"布尔索引筛选"），便于学习报告按知识点聚合。
    """
    text = (value or "").strip()
    if not text:
        return ""

    # 反复剥前缀，最长 4 次（page N 关键点：xxx 关键点：xxx 这种叠层）
    for _ in range(4):
        prev = text
        # 去掉开头的 page/slide + 可选分隔 + 数字（中文数字 / 阿拉伯数字）+ 可选分隔
        text = re.sub(
            r"^\s*(page|slide)\s*[\d_一-鿿]+[\s_\-:：、]*",
            "",
            text,
            flags=re.I,
        )
        # 去掉开头的 "关键点" / "要点" / "知识点" + 可选分隔
        text = re.sub(
            r"^\s*(关键点|知识点|要点|核心点)\s*[：:、\s]*",
            "",
            text,
        )
        # 去掉开头的 "第N页/页N"（如 "第15页" / "页 15"）
        text = re.sub(r"^\s*第?\s*\d+\s*页\s*[：:、\s]*", "", text)
        if text == prev:
            break
        text = text.strip()

    return text


def _derive_slide_title(idx: int, filename: str, svg_texts: list[str], manuscript_note: str = "") -> str:
    # 1) 优先从讲稿（manuscript）提炼标题 —— 讲稿是对本页内容最准确的概括
    if manuscript_note:
        first = manuscript_note.split("。")[0].strip()
        # 去掉常见的引导前缀，保留核心主题
        first = re.sub(
            r"^(在本章中|在这一页|在本节|本页|本节|本章|首先|接下来|我们|下面|现在|这里)\s*[，,、．.]?\s*",
            "",
            first,
        )
        first = _clean_text(first)
        if 4 <= len(first) <= 20:
            return first
        if len(first) > 20:
            return first[:18] + "..."

    # 2) 从文件名提取（过滤 slide N / page N 等占位符）
    stem = os.path.splitext(os.path.basename(filename))[0]
    stem = re.sub(r"^\s*\d+[\s_.\-、]*", "", stem)
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = _clean_text(stem)
    if 2 <= len(stem) <= 40 and not re.match(r"^(slide|page)\s*\d+$", stem, flags=re.I):
        return stem

    # 3) 从 SVG 文本提取（兜底，不再优先）
    for text in svg_texts:
        candidate = _clean_text(text)
        if 2 <= len(candidate) <= 40:
            return candidate

    return f"第 {idx} 页"


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


def _normalize_student_profile(profile: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(profile, dict):
        return {}
    result: dict[str, str] = {}
    for key in ("basis", "goal", "style", "difficulty"):
        value = _clean_text(str(profile.get(key, "")))[:40]
        if value:
            result[key] = value
    return result


def _student_profile_hint(profile: dict[str, str]) -> str:
    if not profile:
        return ""
    parts = []
    labels = {
        "basis": "基础",
        "goal": "目标",
        "style": "偏好",
        "difficulty": "难度",
    }
    for key in ("basis", "goal", "style", "difficulty"):
        value = profile.get(key)
        if value:
            parts.append(f"{labels[key]}：{value}")
    return "；".join(parts)


def _option_rows(correct: str, distractors: list[str], offset: int = 0) -> tuple[list[dict[str, str]], str]:
    values = ["A", "B", "C", "D"]
    rows: list[str] = []
    seen: set[str] = set()

    for item in [correct, *distractors]:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
        if len(rows) == 4:
            break

    while len(rows) < 4:
        fallback = [
            "只关注页面颜色和装饰",
            "跳过示例直接背结论",
            "忽略题目反馈继续下一章",
            "只看最后一页标题",
        ][len(rows) - 1]
        if fallback not in seen:
            rows.append(fallback)
            seen.add(fallback)

    rows = rows[:4]
    correct_index = min(offset % 4, len(rows) - 1)
    rows[0], rows[correct_index] = rows[correct_index], rows[0]
    return [{"label": label, "value": values[idx]} for idx, label in enumerate(rows)], values[correct_index]


def _question(
    qid: str,
    question: str,
    correct: str,
    distractors: list[str],
    analysis: str,
    knowledge_point: str,
) -> dict[str, Any]:
    options, answer = _option_rows(correct, distractors, offset=sum(ord(ch) for ch in qid))
    return {
        "id": qid,
        "type": "single",
        "question": question,
        "options": options,
        "answer": [answer],
        "analysis": analysis,
        "points": 1,
        "knowledge_point": knowledge_point,
    }


QUIZ_SOURCE_SKIP_KEYWORDS = (
    "课程总结",
    "总结",
    "复盘",
    "回顾",
    "拓展",
    "展望",
    "下一步",
    "课后",
    "提问",
    "问题",
    "讨论",
    "答疑",
    "互动",
    "问答",
    "q&a",
    "qa",
)


def _is_quiz_source_scene(scene: ClassroomScene) -> bool:
    text = " ".join([scene.title, *scene.knowledge_points]).lower()
    if not text.strip():
        return True
    return not any(keyword in text for keyword in QUIZ_SOURCE_SKIP_KEYWORDS)


class InteractiveClassroomGenerator:
    def __init__(
        self,
        backend_dir: str,
        storage: ClassroomStorage,
        quiz_generator: Any | None = None,
        llm_quiz_enabled: bool = True,
    ) -> None:
        self.backend_dir = backend_dir
        self.storage = storage
        self.quiz_generator = quiz_generator
        self.llm_quiz_enabled = llm_quiz_enabled

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
            return _brief(manuscript_note)

        key_points = [text for text in svg_texts if text != title][:4]
        if key_points:
            joined = "；".join(key_points)
            return f"这一页的主题是“{title}”。请重点关注：{joined}。我们先把这些关键点串起来理解。"

        return f"现在进入第 {idx} 页“{title}”。这一页主要帮助我们建立整体印象，先抓住标题和页面中的核心关系。"

    def _build_slide_scenes_from_ppt_job(
        self,
        user_id: str,
        ppt_job_id: str,
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
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
            path = os.path.join(svg_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                svg = f.read()

            svg_texts = _extract_svg_texts(svg)
            manuscript_note = manuscript_notes[idx - 1] if idx - 1 < len(manuscript_notes) else ""
            title = _derive_slide_title(idx, fname, svg_texts, manuscript_note)
            speech_text = self._build_speech_text(idx, title, svg_texts, manuscript_note, student_profile)

            scene = ClassroomScene(
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
            scenes.append(scene)
            _emit_progress(
                progress_callback,
                stage="build_scenes",
                stage_index=1,
                scene_index=idx,
                scene_total=len(svg_files),
                scene=scene,
            )
        return scenes

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

    def _build_quiz_questions(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        max_questions: int = 5,
        qid_prefix: str = "q",
    ) -> list[dict[str, Any]]:
        slide_scenes = [scene for scene in scenes if scene.type == "slide"]
        titles = [scene.title for scene in slide_scenes if scene.title]
        all_points: list[str] = []
        for scene in slide_scenes:
            all_points.extend([point for point in scene.knowledge_points if point and point != scene.title])

        questions: list[dict[str, Any]] = []
        for idx, scene in enumerate(slide_scenes[:3], start=1):
            other_titles = [title for title in titles if title != scene.title]
            questions.append(
                _question(
                    qid=f"{qid_prefix}{len(questions) + 1}",
                    question=f"第 {idx} 个讲解场景主要围绕哪一项内容展开？",
                    correct=scene.title,
                    distractors=other_titles,
                    analysis=f"该场景标题为“{scene.title}”，课堂讲解和页面内容都围绕这个主题组织。",
                    knowledge_point=scene.title or topic,
                )
            )

            key_points = [point for point in scene.knowledge_points if point and point != scene.title]
            if key_points:
                correct = key_points[0]
                distractors = [point for point in all_points if point != correct]
                questions.append(
                    _question(
                        qid=f"{qid_prefix}{len(questions) + 1}",
                        question=f"以下哪一项是“{scene.title}”页中提到的关键内容？",
                        correct=correct,
                        distractors=distractors,
                        analysis=f"“{correct}”来自该页抽取文本，说明学生需要回到对应页面理解这一要点。",
                        knowledge_point=scene.title or topic,
                    )
                )

            if len(questions) >= max_questions:
                break

        if questions:
            return questions[:max_questions]

        return [
            _question(
                qid=f"{qid_prefix}1",
                question=f"本节《{topic}》课堂首先要抓住什么？",
                correct=f"{topic} 的核心概念、适用场景和关键步骤",
                distractors=[
                    "页面颜色和装饰元素",
                    "与主题无关的背景故事",
                    "只背最后一页标题",
                ],
                analysis="交互式课堂的目标是理解本节主题的概念、场景和关键步骤，而不是记住页面形式。",
                knowledge_point=topic,
            )
        ]

    def _get_quiz_generator(self) -> Any:
        if self.quiz_generator is not None:
            return self.quiz_generator
        from generators.quiz_generator import QuizGenerator

        self.quiz_generator = QuizGenerator()
        return self.quiz_generator

    def _build_slide_summaries(self, scenes: list[ClassroomScene]) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for scene in scenes:
            content = scene.content or {}
            extracted = content.get("extracted_text", [])
            summaries.append(
                {
                    "scene_id": scene.id,
                    "title": scene.title,
                    "knowledge_points": scene.knowledge_points[:8],
                    "extracted_text": extracted[:16] if isinstance(extracted, list) else [],
                }
            )
        return summaries

    def _build_context_quiz_prompt(
        self,
        topic: str,
        slide_summaries: list[dict[str, Any]],
        question_count: int,
        student_profile: dict[str, str] | None = None,
    ) -> str:
        context_lines = []
        for idx, slide in enumerate(slide_summaries, start=1):
            title = str(slide.get("title", "")).strip()
            points = [str(p).strip() for p in slide.get("knowledge_points", []) if str(p).strip()]
            texts = [str(t).strip() for t in slide.get("extracted_text", []) if str(t).strip()]
            context_lines.append(
                f"{idx}. 页面标题：{title}\n"
                f"   覆盖 slide_id：{slide.get('scene_id', '')}\n"
                f"   关键点：{'；'.join(points[:6]) or '无'}\n"
                f"   页面文本：{'；'.join(texts[:10]) or '无'}"
            )
        profile_hint = _student_profile_hint(_normalize_student_profile(student_profile))
        profile_section = f"\n## 学生画像\n{profile_hint}\n" if profile_hint else ""

        return f"""请基于下面的课堂页面内容，为《{topic}》生成 {question_count} 道随堂测验题，并以 JSON 返回。

## 课堂页面内容
{chr(10).join(context_lines)}
{profile_section}

## 出题要求
1. 题目必须直接来自上面的页面标题、关键点或页面文本，不能泛泛问主题定义。
2. 单选题为主，可少量多选题；每题 4 个选项，干扰项要像真实学生会混淆的错误理解。
3. 每题必须给出 analysis，说明答案为什么对，并尽量指向具体页面或关键点。
4. 每题必须给出 knowledge_point，优先使用对应页面标题或关键点。
5. 不要生成填空题、问答题、代码输出题。
6. 如果有学生画像，题目难度、选项干扰方式和解析语言要匹配画像。

## JSON 格式
直接返回 JSON，不要 Markdown 代码块，不要解释文字。
{{
  "title": "{topic}",
  "modules": [
    {{
      "title": "模块名",
      "questions": [
        {{
          "num": "1",
          "type": "单选题",
          "text": "题干",
          "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
          "answer": "A",
          "analysis": "解析",
          "knowledge_point": "知识点"
        }}
      ]
    }}
  ]
}}"""

    def _generate_context_quiz_json(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        question_count: int,
        student_profile: dict[str, str] | None = None,
    ) -> str:
        quiz_generator = self._get_quiz_generator()
        slide_summaries = self._build_slide_summaries(scenes)
        if hasattr(quiz_generator, "generate_context_quiz_json"):
            try:
                return quiz_generator.generate_context_quiz_json(
                    topic=topic,
                    slide_summaries=slide_summaries,
                    question_count=question_count,
                    student_profile=_normalize_student_profile(student_profile),
                )
            except TypeError:
                return quiz_generator.generate_context_quiz_json(
                    topic=topic,
                    slide_summaries=slide_summaries,
                    question_count=question_count,
                )
        prompt = self._build_context_quiz_prompt(topic, slide_summaries, question_count, student_profile)
        return quiz_generator._call_llm(prompt)  # noqa: SLF001

    def _clean_llm_json(self, value: str) -> str:
        text = (value or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return text.strip()

    def _parse_option(self, option: Any, fallback_label: str) -> tuple[str, str]:
        raw = _clean_quiz_text(str(option))
        match = re.match(r"^([A-Da-d])[\.\、\)\s：:]+(.+)$", raw)
        if match:
            return match.group(1).upper(), _clean_quiz_text(match.group(2))
        return fallback_label, raw

    def _normalize_llm_answers(self, value: Any) -> list[str]:
        if isinstance(value, list):
            rows = value
        else:
            rows = re.findall(r"[A-Da-d]", str(value or ""))
        answers = sorted({str(row).strip().upper() for row in rows if str(row).strip().upper() in {"A", "B", "C", "D"}})
        return answers

    def _convert_llm_quiz_json(
        self,
        raw_json: str,
        scenes: list[ClassroomScene],
        max_questions: int,
        qid_prefix: str,
    ) -> list[dict[str, Any]]:
        data = json.loads(self._clean_llm_json(raw_json))
        modules = data.get("modules", [])
        if not isinstance(modules, list):
            return []

        scene_points: list[str] = []
        for scene in scenes:
            scene_points.extend([scene.title, *scene.knowledge_points])

        questions: list[dict[str, Any]] = []
        for module in modules:
            for row in module.get("questions", []) if isinstance(module, dict) else []:
                if len(questions) >= max_questions:
                    break
                text = _clean_quiz_text(str(row.get("text") or row.get("question") or ""))
                raw_options = row.get("options", [])
                answers = self._normalize_llm_answers(row.get("answer", []))
                if not text or not isinstance(raw_options, list) or len(raw_options) < 4 or not answers:
                    continue

                options: list[dict[str, str]] = []
                used_values: set[str] = set()
                for idx, option in enumerate(raw_options[:4]):
                    value, label = self._parse_option(option, ["A", "B", "C", "D"][idx])
                    if value in used_values or value not in {"A", "B", "C", "D"} or not label:
                        continue
                    used_values.add(value)
                    options.append({"label": label, "value": value})
                if len(options) != 4 or any(answer not in used_values for answer in answers):
                    continue

                qtype = str(row.get("type", "单选题"))
                normalized_type = "multiple" if len(answers) > 1 or "多" in qtype else "single"
                # 修复：原先不过滤 LLM 直给的 knowledge_point，导致 "page 15 关键点：xxx"
                # 这种带 slide/page 占位符 + 关键点/要点 前缀的脏数据直接落到题目里，
                # 进而污染 report.weak_points 标签。先清洗 LLM 提供的值；若清洗后仍
                # 命中占位符模式或为空，再回退到 scene_points。
                raw_kp = _clean_text(str(row.get("knowledge_point") or module.get("title") or ""))
                knowledge_point = _clean_knowledge_point(raw_kp) if raw_kp else ""
                if not knowledge_point or re.search(r"\b(slide|page)[_\-\s]*\d+\b", knowledge_point, flags=re.I):
                    knowledge_point = next(
                        (
                            point
                            for point in scene_points
                            if point and not re.search(r"\b(slide|page)[_\-\s]*\d+\b", point, flags=re.I)
                        ),
                        "",
                    )
                if not knowledge_point:
                    knowledge_point = topic

                questions.append(
                    {
                        "id": f"{qid_prefix}{len(questions) + 1}",
                        "type": normalized_type,
                        "question": text,
                        "options": options,
                        "answer": answers,
                        "analysis": _clean_quiz_text(str(row.get("analysis") or "请回到对应课堂页面复习该知识点。")),
                        "points": 1,
                        "knowledge_point": knowledge_point,
                    }
                )
            if len(questions) >= max_questions:
                break
        return questions

    def _build_llm_quiz_questions(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        max_questions: int,
        qid_prefix: str,
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> list[dict[str, Any]]:
        _raise_if_cancelled(cancel_check)
        if not self.llm_quiz_enabled:
            return []
        try:
            raw_json = self._generate_context_quiz_json(topic, scenes, max_questions, student_profile)
            _raise_if_cancelled(cancel_check)
            return self._convert_llm_quiz_json(
                raw_json=raw_json,
                scenes=scenes,
                max_questions=max_questions,
                qid_prefix=qid_prefix,
            )
        except Exception:
            return []

    def _build_quiz_scene(
        self,
        quiz_index: int,
        order: int,
        topic: str,
        scenes: list[ClassroomScene],
        max_questions: int = 3,
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ClassroomScene:
        _raise_if_cancelled(cancel_check)
        qid_prefix = f"q{quiz_index}_"
        questions = self._build_llm_quiz_questions(
            topic,
            scenes,
            max_questions=max_questions,
            qid_prefix=qid_prefix,
            student_profile=student_profile,
            cancel_check=cancel_check,
        )
        _raise_if_cancelled(cancel_check)
        quiz_source = "llm_json" if questions else "slide_text"
        if not questions:
            questions = self._build_quiz_questions(
                topic,
                scenes,
                max_questions=max_questions,
                qid_prefix=qid_prefix,
            )
        knowledge_points: list[str] = []
        for scene in scenes:
            for point in [scene.title, *scene.knowledge_points]:
                if point and point not in knowledge_points:
                    knowledge_points.append(point)

        return ClassroomScene(
            id=f"scene_quiz_{quiz_index:03d}",
            type="quiz",
            title=f"随堂测验 {quiz_index}：{topic}",
            order=order,
            knowledge_points=knowledge_points[:6] or [topic],
            content={
                "questions": questions,
                "quiz_source": quiz_source,
                "covered_scene_ids": [scene.id for scene in scenes],
            },
            actions=[],
        )

    def _insert_quiz_scenes(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[ClassroomScene]:
        _raise_if_cancelled(cancel_check)
        slide_scenes = [scene for scene in scenes if scene.type == "slide"]
        if not slide_scenes:
            return scenes

        # 估计要插入的 quiz 数量（按现有规则），用于阶段 3 的 scene_total
        quiz_count_estimate = max(0, len([s for s in slide_scenes if _is_quiz_source_scene(s)]) // 2)

        result: list[ClassroomScene] = []
        quiz_index = 1
        pending_slides: list[ClassroomScene] = []
        quiz_source_slides = [scene for scene in slide_scenes if _is_quiz_source_scene(scene)]
        quiz_source_ids = {scene.id for scene in quiz_source_slides}
        total_quiz_source_slides = len(quiz_source_slides)
        quiz_source_index = 0

        # 阶段 3 推进：开始生成互动
        _emit_progress(
            progress_callback,
            stage="insert_quizzes",
            stage_index=2,
            scene_index=0,
            scene_total=max(quiz_count_estimate, 1),
        )

        for scene in slide_scenes:
            _raise_if_cancelled(cancel_check)
            result.append(scene)
            if scene.id not in quiz_source_ids:
                continue

            quiz_source_index += 1
            pending_slides.append(scene)

            is_last = quiz_source_index == total_quiz_source_slides
            enough_for_mid_quiz = len(pending_slides) >= 2 and not is_last
            enough_for_final_quiz = is_last and pending_slides

            if enough_for_mid_quiz or enough_for_final_quiz:
                quiz_scene = self._build_quiz_scene(
                    quiz_index=quiz_index,
                    order=0,
                    topic=topic,
                    scenes=pending_slides,
                    max_questions=2 if not is_last else 3,
                    student_profile=student_profile,
                    cancel_check=cancel_check,
                    progress_callback=progress_callback,
                )
                result.append(quiz_scene)
                _emit_progress(
                    progress_callback,
                    stage="insert_quizzes",
                    stage_index=2,
                    scene_index=quiz_index,
                    scene_total=max(quiz_count_estimate, 1),
                    scene=quiz_scene,
                )
                quiz_index += 1
                pending_slides = []

        return result

    def generate(
        self,
        user_id: str,
        topic: str,
        course: str,
        tts_config: dict[str, Any],
        ppt_job_id: str = "",
        student_profile: dict[str, Any] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        _raise_if_cancelled(cancel_check)
        now = datetime.now().isoformat()
        classroom_id = f"cls_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        normalized_profile = _normalize_student_profile(student_profile)

        if ppt_job_id:
            scenes = self._build_slide_scenes_from_ppt_job(
                user_id, ppt_job_id, normalized_profile, cancel_check, progress_callback
            )
            if not scenes:
                scenes = self._build_fallback_slide_scenes(
                    topic, normalized_profile, cancel_check, progress_callback
                )
        else:
            scenes = self._build_fallback_slide_scenes(
                topic, normalized_profile, cancel_check, progress_callback
            )

        _raise_if_cancelled(cancel_check)
        scenes = self._insert_quiz_scenes(topic, scenes, normalized_profile, cancel_check, progress_callback)
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

        # 阶段 4：合成音频
        speech_actions: list[tuple[ClassroomScene, ClassroomAction]] = []
        for scene in classroom.scenes:
            for action in scene.actions:
                if action.type == "speech":
                    speech_actions.append((scene, action))
        _emit_progress(
            progress_callback,
            stage="synthesize_tts",
            stage_index=3,
            scene_index=0,
            scene_total=len(speech_actions),
        )
        for idx, (_scene, action) in enumerate(speech_actions, start=1):
            _raise_if_cancelled(cancel_check)
            try:
                filename = tts.synthesize_action(action.id, action.text, audio_dir)
                if filename:
                    action.audio_url = f"/api/interactive-classroom/{classroom_id}/audio/{filename}"
            except Exception:
                action.audio_url = ""
            _emit_progress(
                progress_callback,
                stage="synthesize_tts",
                stage_index=3,
                scene_index=idx,
                scene_total=len(speech_actions),
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
