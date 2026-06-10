from __future__ import annotations

import asyncio
import os
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html import unescape
from typing import Any, Callable
from uuid import uuid4

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
DEFAULT_SLIDE_SCENE_MAX_CONCURRENCY = 10
DEFAULT_QUIZ_SCENE_MAX_CONCURRENCY = 4


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
    # 剥离内部 scene ID（如 scene_slide_002、scene_quiz_001）
    value = re.sub(r"\bscene_(?:slide|quiz|mindmap)_\d+\b", "", value)
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
        # 去掉 scene_slide_002 / scene_quiz_001 等内部 ID
        text = re.sub(
            r"^\s*scene_(?:slide|quiz|mindmap)_\d+[\s_\-:：、]*",
            "",
            text,
            flags=re.I,
        )
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


def _speech_text_from_manuscript(text: str, max_len: int = 900) -> str:
    """保留比摘要更完整的备注讲稿，供课堂 TTS 与底部讲稿使用。"""
    cleaned = _clean_text(text)
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip("，。；、 ") + "。"


def _split_speech_segments(text: str, limit: int = 6) -> list[str]:
    """把讲稿拆成可同步高亮的短段，保留句末标点便于前端展示。"""
    cleaned = _clean_text(text)
    if not cleaned:
        return []

    parts = re.findall(r"[^。！？!?；;]+[。！？!?；;]?", cleaned)
    segments: list[str] = []
    for part in parts:
        segment = part.strip()
        if len(segment) < 3:
            continue
        segments.append(segment)
        if len(segments) >= limit:
            break
    return segments or [cleaned]


def _parse_svg_number(attrs: str, name: str, default: float = 0) -> float:
    match = re.search(rf'\b{name}\s*=\s*["\']\s*([-+]?\d+(?:\.\d+)?)', attrs, flags=re.I)
    if not match:
        return default
    try:
        return float(match.group(1))
    except ValueError:
        return default


def _svg_text_content(raw: str) -> str:
    raw = re.sub(r"<[^>]+>", "", raw)
    return _clean_text(raw)


def _extract_svg_highlight_targets(svg: str, limit: int = 12) -> list[dict[str, Any]]:
    """从 SVG 文本节点提取可高亮目标，并估算 bbox。

    当前 PPT 引擎输出的 SVG 文本多数带 x/y/font-size。浏览器端会优先用
    实际 DOM bbox 修正位置；这里的 bbox 让已保存课堂也具备可回放元数据。
    """
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    pattern = re.compile(r"<text\b([^>]*)>(.*?)</text\s*>", flags=re.I | re.S)
    for match in pattern.finditer(svg or ""):
        attrs, body = match.groups()
        text = _svg_text_content(body)
        if len(text) < 2 or text in seen:
            continue
        if re.search(r"\b(slide|page)[_\-\s]*\d+\b", text, flags=re.I):
            continue

        font_size = _parse_svg_number(attrs, "font-size", 24)
        x = _parse_svg_number(attrs, "x", 0)
        baseline_y = _parse_svg_number(attrs, "y", 0)
        width = max(font_size * 2.5, len(text) * font_size * 0.58)
        height = max(font_size * 1.25, 24)
        y = max(0, baseline_y - font_size)
        seen.add(text)
        targets.append(
            {
                "id": f"hl_{len(targets) + 1:03d}",
                "text": text,
                "kind": "text",
                "bbox": {
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "width": round(width, 2),
                    "height": round(height, 2),
                },
            }
        )
        if len(targets) >= limit:
            break
    return targets


def _match_text_score(segment: str, target_text: str) -> int:
    seg = re.sub(r"\W+", "", segment.lower())
    target = re.sub(r"\W+", "", target_text.lower())
    if not seg or not target:
        return 0
    if target in seg:
        return len(target) * 3
    if seg in target:
        return len(seg) * 2
    target_chars = {ch for ch in target if not ch.isspace()}
    return sum(1 for ch in seg if ch in target_chars)


def _highlight_mode_for_segment(segment: str, index: int) -> str:
    if index == 0:
        return "spotlight"
    if re.search(r"(重点|核心|关键|注意|看这里)", segment):
        return "spotlight"
    return "outline"


def _build_highlight_cues(
    segments: list[str],
    targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not segments or not targets:
        return []

    cues: list[dict[str, Any]] = []
    total = len(segments)
    for idx, segment in enumerate(segments):
        best = max(
            targets,
            key=lambda target: _match_text_score(segment, str(target.get("text") or "")),
        )
        if _match_text_score(segment, str(best.get("text") or "")) <= 0:
            best = targets[0]

        start = idx / total
        end = (idx + 1) / total
        cues.append(
            {
                "target_id": best["id"],
                "start_ratio": round(start, 6),
                "end_ratio": round(end, 6),
                "mode": _highlight_mode_for_segment(segment, idx),
                "label": segment,
            }
        )
    return cues


def _safe_segment_mode(value: Any, fallback: str = "outline") -> str:
    return "spotlight" if str(value or "").strip() == "spotlight" else fallback


def _compose_teaching_speech(segments: list[dict[str, Any]]) -> str:
    return "\n".join(str(item.get("text") or "").strip() for item in segments if str(item.get("text") or "").strip())


def _build_highlight_cues_from_teaching_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usable = [item for item in segments if item.get("target_id") and str(item.get("text") or "").strip()]
    if not usable:
        return []
    weights = [max(1, len(_clean_text(str(item.get("text") or "")))) for item in usable]
    total_weight = sum(weights) or len(usable)
    cues: list[dict[str, Any]] = []
    cursor = 0.0
    for idx, item in enumerate(usable):
        start = cursor
        cursor += weights[idx] / total_weight
        end = 1.0 if idx == len(usable) - 1 else cursor
        cues.append(
            {
                "target_id": str(item.get("target_id") or ""),
                "start_ratio": round(start, 6),
                "end_ratio": round(end, 6),
                "mode": _safe_segment_mode(item.get("mode"), "outline"),
                "label": str(item.get("text") or "").strip(),
            }
        )
    return cues


def _fallback_teaching_segments(
    title: str,
    manuscript_note: str,
    targets: list[dict[str, Any]],
    svg_texts: list[str],
) -> list[dict[str, Any]]:
    source_targets = targets[:5]
    if not source_targets:
        source_targets = [
            {"id": f"hl_{idx + 1:03d}", "text": text}
            for idx, text in enumerate(svg_texts[:5])
            if text
        ]
    if not source_targets:
        source_targets = [{"id": "hl_001", "text": title or "本页主题"}]

    note = _clean_text(manuscript_note)
    result: list[dict[str, Any]] = []
    for idx, target in enumerate(source_targets):
        target_text = str(target.get("text") or title or "这一点").strip()
        if idx == 0:
            text = (
                f"这一页我们先把视线放到“{target_text}”。"
                f"{note or f'它是理解“{title}”这页内容的入口。'}"
                f"听的时候先不要急着记结论，先想一想：它在这页中负责回答什么问题，"
                f"又和后面的几个关键词有什么关系。"
            )
            mode = "spotlight"
        else:
            text = (
                f"接着看“{target_text}”。"
                f"这里不是孤立的信息点，而是对刚才主题的进一步展开。"
                f"你可以把它和页面上的前一个重点连起来理解：先看它描述的对象，"
                f"再看它暗示的过程或判断标准。这样回到题目时，就不只是记住一个词，"
                f"而是知道它在真实任务中怎么发挥作用。"
            )
            mode = "outline"
        result.append({"target_id": target["id"], "mode": mode, "text": text})
    return result


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


def _normalize_generation_strategy(strategy: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(strategy, dict):
        return {}
    focus_points = [
        _clean_text(str(value))[:80]
        for value in strategy.get("focus_knowledge_points", [])
        if _clean_text(str(value))
    ][:5]
    content_style = [
        _clean_text(str(value))[:40]
        for value in strategy.get("content_style", [])
        if _clean_text(str(value))
    ][:8]
    avoid = [
        _clean_text(str(value))[:80]
        for value in strategy.get("avoid", [])
        if _clean_text(str(value))
    ][:8]
    return {
        "strategy_version": int(strategy.get("strategy_version", 1) or 1),
        "course_id": _clean_text(str(strategy.get("course_id", "")))[:80],
        "course_name": _clean_text(str(strategy.get("course_name", "")))[:120],
        "explanation_depth": _clean_text(
            str(strategy.get("explanation_depth", "basic_to_intermediate"))
        )[:40],
        "content_style": content_style,
        "quiz_difficulty": _clean_text(
            str(strategy.get("quiz_difficulty", "basic"))
        )[:40],
        "feedback_style": _clean_text(
            str(strategy.get("feedback_style", "guided"))
        )[:40],
        "focus_knowledge_points": focus_points,
        "avoid": avoid,
        "reason": _clean_text(str(strategy.get("reason", "")))[:400],
        "profile_updated_at": _clean_text(
            str(strategy.get("profile_updated_at", ""))
        )[:40],
    }


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

# 开场/封面/目录页关键词 — 用于检测不应出题的非知识内容页
# 注意：只保留明确的开场/封面/目录关键词，避免"学习目标""课程大纲"等
# 可能出现在内容页知识点中的词导致误杀
INTRO_SLIDE_KEYWORDS = (
    # 封面/标题页（高置信度）
    "课程介绍", "课程简介", "课程目录",
    # 目录/大纲页
    "目录", "内容概览", "章节概览",
    "agenda", "contents", "outline",
    # 通用开场
    "自我介绍", "讲师介绍", "欢迎", "开场",
    "welcome", "introduction", "intro",
)


def _is_intro_slide(scene: ClassroomScene, *, is_first_slide: bool = False) -> bool:
    """检测开场/封面/目录页，这些页面不应生成测验题。"""
    title = (scene.title or "").strip()
    title_lower = title.lower()
    points = [p.strip() for p in scene.knowledge_points if p.strip()]
    combined = f"{title_lower} {' '.join(points).lower()}"

    # Signal A: 标题命中关键词 → 直接判定为开场页
    for kw in INTRO_SLIDE_KEYWORDS:
        if kw in title_lower:
            return True

    # Signal B: 标题较短(≤15字符) + (标题+知识点)命中关键词 → 判定为开场页
    # 避免长标题内容页（如"Python 模块导入详解"）被误杀
    if len(title) <= 15:
        for kw in INTRO_SLIDE_KEYWORDS:
            if kw in combined:
                return True

    # Signal C: 首页 + 完全无知识点 → 判定为开场页（纯封面/装饰页）
    if is_first_slide and len(points) == 0:
        return True

    return False


def _is_quiz_source_scene(scene: ClassroomScene, *, is_first_slide: bool = False) -> bool:
    text = " ".join([scene.title, *scene.knowledge_points]).lower()
    if not text.strip():
        return False  # 空标题+空知识点的页面不是有效的出题源
    if _is_intro_slide(scene, is_first_slide=is_first_slide):
        return False
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

    def _build_teaching_segments_prompt(
        self,
        *,
        page_index: int,
        page_total: int,
        title: str,
        manuscript_note: str,
        targets: list[dict[str, Any]],
        student_profile: dict[str, str] | None = None,
    ) -> str:
        target_lines = []
        for target in targets[:8]:
            target_lines.append(f"- id: {target.get('id')}｜text: {target.get('text')}")
        profile_hint = _student_profile_hint(_normalize_student_profile(student_profile))
        position = "first" if page_index == 1 else ("last" if page_index == page_total else "middle")
        return f"""你是智慧课堂的授课脚本设计师。请基于本页 PPT 的可见文字和原始备注，生成自然口语化的讲解段，并让每段讲解绑定一个高亮目标。

## 页面位置
第 {page_index} / {page_total} 页，position={position}

## 页面标题
{title}

## 原始 PPT 备注/讲稿
{manuscript_note or "无"}

## 可高亮目标
{chr(10).join(target_lines) or "无"}

## 学生画像
{profile_hint or "无"}

## 要求
1. 直接返回 JSON，不要 Markdown 代码块。
2. 输出 4 到 6 个 segments；如果可高亮目标少于 4 个，可以重复核心目标，但讲解内容不能重复。
3. 每个 segment 必须从可高亮目标中选择 target_id。
4. 每段 text 80 到 140 个中文字符，口语化，像老师在讲课，不要照抄 PPT。
5. 讲稿必须和当前 target 的文字实际对应：讲“图像分类”就绑定“图像分类”，讲“目标检测”就绑定“目标检测”。
6. 第一段或真正强调“重点/核心/关键”的段落 mode 用 "spotlight"，其他用 "outline"。
7. 中间页不要寒暄；第一页可自然开场；最后一页可总结。

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
    ) -> list[dict[str, Any]]:
        valid_ids = {str(target.get("id")) for target in targets if target.get("id")}
        if targets and self.llm_quiz_enabled:
            try:
                quiz_generator = self._get_quiz_generator()
                prompt = self._build_teaching_segments_prompt(
                    page_index=page_index,
                    page_total=page_total,
                    title=title,
                    manuscript_note=manuscript_note,
                    targets=targets,
                    student_profile=student_profile,
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
                        if target_id not in valid_ids or len(text) < 12:
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
                if len(segments) >= 2:
                    return segments
            except Exception:
                pass

        return _fallback_teaching_segments(title, manuscript_note, targets, svg_texts)

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

        max_workers = min(DEFAULT_SLIDE_SCENE_MAX_CONCURRENCY, len(svg_files))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="classroom-slide") as executor:
            future_to_index = {
                executor.submit(
                    self._build_single_slide_scene_from_svg,
                    idx,
                    fname,
                    svg_dir,
                    manuscript_notes[idx - 1] if idx - 1 < len(manuscript_notes) else "",
                    len(svg_files),
                    ppt_job_id,
                    student_profile,
                    cancel_check,
                ): idx
                for idx, fname in enumerate(svg_files, start=1)
            }

            completed = 0
            scenes_by_index: dict[int, ClassroomScene] = {}
            for future in as_completed(future_to_index):
                _raise_if_cancelled(cancel_check)
                idx = future_to_index[future]
                scene = future.result()
                scenes_by_index[idx] = scene
                completed += 1
                _emit_progress(
                    progress_callback,
                    stage="build_scenes",
                    stage_index=1,
                    scene_index=completed,
                    scene_total=len(svg_files),
                    scene=scene,
                )
            scenes = [scenes_by_index[idx] for idx in sorted(scenes_by_index)]
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
    ) -> ClassroomScene:
        _raise_if_cancelled(cancel_check)
        path = os.path.join(svg_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            svg = f.read()

        svg_texts = _extract_svg_texts(svg)
        title = _derive_slide_title(idx, fname, svg_texts, manuscript_note)
        highlight_targets = _extract_svg_highlight_targets(svg)
        teaching_segments = self._generate_teaching_segments(
            page_index=idx,
            page_total=page_total,
            title=title,
            manuscript_note=manuscript_note,
            targets=highlight_targets,
            svg_texts=svg_texts,
            student_profile=student_profile,
        )
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

    def _build_quiz_questions(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        max_questions: int = 5,
        qid_prefix: str = "q",
    ) -> list[dict[str, Any]]:
        slide_scenes = [scene for scene in scenes if scene.type == "slide"]
        # 过滤开场/目录页，避免生成无意义题目
        eligible_scenes = [
            s for i, s in enumerate(slide_scenes)
            if not _is_intro_slide(s, is_first_slide=(i == 0))
        ]
        if not eligible_scenes:
            # 兜底：如果全部被过滤，跳过第一页使用剩余页面
            eligible_scenes = slide_scenes[1:] if len(slide_scenes) > 1 else slide_scenes
        titles = [scene.title for scene in eligible_scenes if scene.title]
        all_points: list[str] = []
        for scene in eligible_scenes:
            all_points.extend([point for point in scene.knowledge_points if point and point != scene.title])

        questions: list[dict[str, Any]] = []
        for idx, scene in enumerate(eligible_scenes[:3], start=1):
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
            # 抓首条 speech action 的讲稿正文（如果有）—— 讲稿比 SVG 文本更"语义化"
            speech_text = ""
            for action in scene.actions or []:
                if action.type == "speech" and action.text:
                    speech_text = action.text
                    break
            if len(speech_text) > 320:
                speech_text = speech_text[:320].rstrip("，。；、 ") + "…"
            summaries.append(
                {
                    "scene_id": scene.id,
                    "title": scene.title,
                    "knowledge_points": scene.knowledge_points[:8],
                    "extracted_text": extracted[:16] if isinstance(extracted, list) else [],
                    "speech_excerpt": speech_text,
                }
            )
        return summaries

    def _build_context_quiz_prompt(
        self,
        topic: str,
        slide_summaries: list[dict[str, Any]],
        question_count: int,
        student_profile: dict[str, str] | None = None,
        require_short_answer: bool = False,
    ) -> str:
        context_lines = []
        for idx, slide in enumerate(slide_summaries, start=1):
            title = str(slide.get("title", "")).strip()
            points = [str(p).strip() for p in slide.get("knowledge_points", []) if str(p).strip()]
            texts = [str(t).strip() for t in slide.get("extracted_text", []) if str(t).strip()]
            context_lines.append(
                f"{idx}. 页面标题：{title}\n"
                f"   关键点：{'；'.join(points[:6]) or '无'}\n"
                f"   页面文本：{'；'.join(texts[:10]) or '无'}"
            )
        profile_hint = _student_profile_hint(_normalize_student_profile(student_profile))
        profile_section = f"\n## 学生画像\n{profile_hint}\n" if profile_hint else ""

        # 默认规则：每 4 道题里"可以有" 1 道简答（不强制）
        # 强化规则（require_short_answer=True）：本场必须包含 1 道简答，剩余用单选/多选凑齐
        if require_short_answer:
            short_answer_rule = (
                f"7. **本场强制要求 1 道简答题**：本题共 {question_count} 道，必须包含恰好 1 道简答题，"
                f"剩余 {question_count - 1} 道做单选题。简答题要能让学生写 2-4 句作答，"
                f"必须给 `reference_answer`（2-4 句参考答案）和 `rubric`（3 个以内评分维度）。"
                f"**不要给简答题写 options/answer 字段。**"
                f"如果某知识点不好出 4 选项单选，可以把单选改成「为什么…」「如何判断…"
                f"」「对比 X 与 Y」等开放性判断题，再跟 1 道标准简答搭配。"
            )
        else:
            short_answer_rule = (
                "7. **本场不要求简答题**：不要主动出简答题。如果觉得该知识点确实需要 1 道简答才能测出深度，"
                "才出 1 道（且必须给 `reference_answer` 和 `rubric`）。"
                "**不要每场都加简答**——仅当单选/多选无法覆盖某个深度理解时再加。"
            )

        return f"""请基于下面的课堂页面内容，为《{topic}》生成 {question_count} 道随堂测验题，并以 JSON 返回。

## 课堂页面内容
{chr(10).join(context_lines)}
{profile_section}

## 出题要求
1. 题目必须直接来自上面的页面标题、关键点或页面文本，不能泛泛问主题定义。
1b. **跳过开场/目录类页面**：如果某些页面的标题是课程名称、目录、欢迎语、自我介绍、学习目标概述等开场性质的内容，不要基于这些页面出题。只围绕有实质知识点的页面出题。
2. 单选题为主，可少量多选题；每题 4 个选项，干扰项要像真实学生会混淆的错误理解。
   **多选题识别强约束**：如果题干含「以下哪些」「下列哪些」「哪些选项」「哪些是」「多选」等表述，**必须**把 `type` 设为「多选题」并给 `answer` 多个字母（如 "A,C"）。否则前端 UI 会按单选渲染，题干和交互对不上。
3. 每题必须给出 analysis，说明答案为什么对，并尽量指向具体页面编号（如"第 2 页"）或关键点。不要使用任何内部 ID。
4. 每题必须给出 knowledge_point，优先使用对应页面标题或关键点。
5. 不要生成填空题、代码输出题。
6. 如果有学生画像，题目难度、选项干扰方式和解析语言要匹配画像。
{short_answer_rule}

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
        }},
        {{
          "num": "2",
          "type": "简答题",
          "text": "题干",
          "reference_answer": "2-4 句参考答案",
          "rubric": ["维度1", "维度2", "维度3"],
          "analysis": "答题要点提示",
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
        require_short_answer: bool = False,
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
                    require_short_answer=require_short_answer,
                )
            except TypeError:
                # 外部 quiz_generator 不支持新参数，回退到不带参数版本
                return quiz_generator.generate_context_quiz_json(
                    topic=topic,
                    slide_summaries=slide_summaries,
                    question_count=question_count,
                )
        prompt = self._build_context_quiz_prompt(
            topic, slide_summaries, question_count, student_profile, require_short_answer
        )
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
                if not text:
                    continue

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

                qtype_raw = str(row.get("type", "单选题"))
                is_short_answer = "简答" in qtype_raw or qtype_raw.strip().lower() in {"short_answer", "essay", "open"}

                if is_short_answer:
                    # 简答题：不要 options/answer；需要 reference_answer / rubric
                    reference_answer = _clean_quiz_text(
                        str(row.get("reference_answer") or row.get("answer") or "")
                    )
                    rubric_raw = row.get("rubric", [])
                    if isinstance(rubric_raw, list):
                        rubric = [str(r).strip() for r in rubric_raw if str(r).strip()][:5]
                    else:
                        rubric = []
                    if not reference_answer:
                        # 没有参考答案就跳过这道，不让脏数据进课堂
                        continue
                    questions.append(
                        {
                            "id": f"{qid_prefix}{len(questions) + 1}",
                            "type": "short_answer",
                            "question": text,
                            "options": [],
                            "answer": [reference_answer],
                            "analysis": _clean_quiz_text(
                                str(row.get("analysis") or f"参考要点：{reference_answer}")
                            ),
                            "points": 1,
                            "knowledge_point": knowledge_point,
                            "reference_answer": reference_answer,
                            "rubric": rubric,
                        }
                    )
                    continue

                # 单选 / 多选：必须有 4 个选项 + 合法 answer
                raw_options = row.get("options", [])
                answers = self._normalize_llm_answers(row.get("answer", []))
                if not isinstance(raw_options, list) or len(raw_options) < 4 or not answers:
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

                # 多选题识别：双重保险
                # 1) 答案有 2+ 个字母 → 多选（LLM 给的 answer 已经是列表/字符串含多字母）
                # 2) LLM 的 type 字段含"多"（"多选题"等）
                # 3) 题干文字含强信号（"以下哪些"/"下列哪些"/"哪些选项"/"哪些是"/"多选"）
                #    → 即便 LLM 错误地标了"单选题"也强制升级成多选
                is_multi_by_text = bool(
                    re.search(r"(以下哪些|下列哪些|哪些选项|哪些是|多选)", text)
                )
                normalized_type = (
                    "multiple"
                    if len(answers) > 1 or "多" in qtype_raw or is_multi_by_text
                    else "single"
                )
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
        require_short_answer: bool = False,
    ) -> list[dict[str, Any]]:
        _raise_if_cancelled(cancel_check)
        if not self.llm_quiz_enabled:
            return []
        try:
            raw_json = self._generate_context_quiz_json(
                topic, scenes, max_questions, student_profile, require_short_answer
            )
            _raise_if_cancelled(cancel_check)
            questions = self._convert_llm_quiz_json(
                raw_json=raw_json,
                scenes=scenes,
                max_questions=max_questions,
                qid_prefix=qid_prefix,
            )
            # 兜底：LLM 没出简答但要求了 → 把最后一道单选/多选降级为简答
            # 这样即使 LLM 偶尔忽略 prompt，仍然能保证 ~50% 测验有简答
            if (
                require_short_answer
                and questions
                and not any(q.get("type") == "short_answer" for q in questions)
            ):
                questions = self._force_one_short_answer(questions)
            return questions
        except Exception:
            return []

    @staticmethod
    def _force_one_short_answer(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """把最后一道单选/多选降级为简答。

        适用场景：要求 1 道简答但 LLM 没出。直接把最后一道的 options/answer
        丢掉，type 改成 short_answer；用其 analysis 兜底作 reference_answer，
        rubric 用默认三维度。题干是单选问题"X 是 Y 中的哪一类？"
        这种封闭问法对简答来说不理想，但作为兜底可接受——
        真正生产环境 LLM 99% 情况下会按 prompt 出题，落到这条分支的频率低。
        """
        if not questions:
            return questions
        # 已有简答就不强制（避免出现 2 道简答）
        if any(q.get("type") == "short_answer" for q in questions):
            return questions
        idx = len(questions) - 1
        target = dict(questions[idx])
        analysis_text = str(target.get("analysis") or "").strip()
        reference_answer = analysis_text or "请结合课堂内容作答。"
        target["type"] = "short_answer"
        target["options"] = []
        target["answer"] = [reference_answer]
        target["reference_answer"] = reference_answer
        target["rubric"] = ["准确性", "完整性", "表达"]
        questions[idx] = target
        return questions

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
        require_short_answer: bool = False,
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
            require_short_answer=require_short_answer,
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

    def build_practice_quiz_scene(
        self,
        *,
        topic: str,
        knowledge_points: list[str],
        task_type: str,
        generation_strategy: dict[str, Any] | None = None,
    ) -> ClassroomScene:
        clean_points = [
            _clean_text(str(value))[:80]
            for value in knowledge_points
            if _clean_text(str(value))
        ][:5]
        if not clean_points:
            clean_points = [_clean_text(topic) or "综合理解"]
        source_scenes = [
            ClassroomScene(
                id=f"practice_source_{idx:03d}",
                type="slide",
                title=point,
                order=idx,
                knowledge_points=[point],
                content={
                    "extracted_text": [
                        point,
                        (
                            f"围绕{point}完成迁移应用和综合判断。"
                            if task_type == "challenge_practice"
                            else f"围绕{point}复习概念、判断依据和应用步骤。"
                        ),
                    ]
                },
                actions=[],
            )
            for idx, point in enumerate(clean_points, start=1)
        ]
        profile = self._profile_from_generation_strategy(generation_strategy)
        scene = self._build_quiz_scene(
            quiz_index=1,
            order=1,
            topic=topic,
            scenes=source_scenes,
            max_questions=4,
            student_profile=profile,
            require_short_answer=task_type == "challenge_practice",
        )
        scene.title = (
            f"挑战练习：{'、'.join(clean_points[:3])}"
            if task_type == "challenge_practice"
            else f"补强练习：{'、'.join(clean_points[:3])}"
        )
        scene.content["practice_task_type"] = task_type
        scene.content["covered_scene_ids"] = []
        return scene

    def _build_mindmap_prompt(
        self,
        topic: str,
        slide_summaries: list[dict[str, Any]],
        student_profile: dict[str, str] | None = None,
    ) -> str:
        """为 mindmap 场景生成 LLM prompt。

        关键点：传讲稿正文（speech_excerpt），让 LLM 从语义归纳概念，
        而不是只把 slide 标题换皮。
        """
        lines = [
            f"请基于下面的课堂讲稿内容，为《{topic}》整理出一份**真正的知识结构图**（markmap 风格 Markdown）。",
            "",
            "## 课堂页面（含讲稿摘录）",
        ]
        for idx, slide in enumerate(slide_summaries, start=1):
            title = str(slide.get("title") or "").strip() or f"第 {idx} 页"
            points = [
                str(p).strip() for p in (slide.get("knowledge_points") or []) if str(p).strip()
            ][:6]
            excerpt = str(slide.get("speech_excerpt") or "").strip()
            lines.append(f"\n### 第 {idx} 页：{title}")
            if points:
                lines.append(f"- 关键点：{'；'.join(points)}")
            if excerpt:
                lines.append(f"- 讲稿：{excerpt}")

        profile_hint = _student_profile_hint(_normalize_student_profile(student_profile))
        if profile_hint:
            lines.append(f"\n## 学生画像\n{profile_hint}\n")

        lines.extend(
            [
                "\n## 输出要求（务必遵循）",
                "1. **从讲稿里归纳真正的概念**，不要简单把页面标题当成分支名",
                "2. 根节点 = 课堂主题（一级标题 #）",
                "3. 一级分支 3-6 个，**按主题分类**（不是按页面顺序）",
                "4. 二级分支 2-5 个，挂在最合适的一级下；最多两级",
                "5. 每个节点 2-8 字，简洁直白",
                "6. **只返回 Markdown 本身**，不要用 ``` 包裹，不要任何解释、前言、后语",
                "7. 实在归纳不出时，输出：根节点 + 一级分支 = 主要概念（≤5 个），二级分支 = 讲到的关键名词",
            ]
        )
        return "\n".join(lines)

    def _build_fallback_markmap_md(
        self,
        topic: str,
        slide_summaries: list[dict[str, Any]],
    ) -> str:
        """LLM 失败时的兜底：根节点 + 每页标题作一级分支。"""
        lines = [f"# {topic}"]
        for idx, slide in enumerate(slide_summaries, start=1):
            title = str(slide.get("title") or "").strip() or f"第 {idx} 页"
            lines.append(f"- {title}")
        return "\n".join(lines)

    def _call_content_llm_markmap(self, prompt: str) -> str:
        """走 content LLM 通道（与 quiz 共享），不依赖外部资源。"""
        from generators.shared_config import content_llm_call

        return content_llm_call(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一位知识结构整理专家，擅长把课堂内容组织成层级清晰、"
                        "用词简洁的思维导图。只输出 Markdown 大纲本身。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )

    def _build_mindmap_scene(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> ClassroomScene | None:
        """构造一个 mindmap 场景。

        输入是已经排好的 [slide scenes] + [quiz scenes] 列表。
        从 slide scenes 抽 title + knowledge_points，让 LLM 重组为 markmap markdown。
        LLM 失败时回退到 flat fallback（根节点 + 每页标题）。
        """
        _raise_if_cancelled(cancel_check)

        slide_scenes = [s for s in scenes if s.type == "slide"]
        if not slide_scenes:
            return None

        slide_summaries = self._build_slide_summaries(slide_scenes)
        markmap_md = ""
        try:
            prompt = self._build_mindmap_prompt(topic, slide_summaries, student_profile)
            raw = self._call_content_llm_markmap(prompt)
            _raise_if_cancelled(cancel_check)
            # 防御：剥掉 ``` 围栏（即使 prompt 说了不要）
            cleaned = re.sub(r"^```(?:markdown|md)?\s*\n?", "", (raw or "").strip())
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
            cleaned = cleaned.strip()
            # 防御：必须包含至少一个 # 标题
            if cleaned and re.search(r"^#\s+\S", cleaned, flags=re.M):
                markmap_md = cleaned
        except Exception:
            markmap_md = ""

        if not markmap_md:
            markmap_md = self._build_fallback_markmap_md(topic, slide_summaries)

        # 收集所有 slide 知识点到场景 knowledge_points
        merged_points: list[str] = []
        for s in slide_scenes:
            for p in [s.title, *s.knowledge_points]:
                if p and p not in merged_points:
                    merged_points.append(p)

        speech_text = (
            f"接下来我们用一张知识结构图，回顾《{topic}》这堂课讲了什么。"
            f"你可以在图中看到主要的概念和它们之间的层级关系。"
        )

        scene_ts = int(datetime.now().timestamp() * 1000)
        return ClassroomScene(
            id=f"scene_mindmap_{scene_ts}",
            type="mindmap",
            title=f"知识结构：{topic}",
            order=0,  # 后续 _renumber 会重排
            knowledge_points=merged_points[:8] or [topic],
            content={
                "format": "markmap",
                "markmap_md": markmap_md,
                "source": "llm" if markmap_md and len(markmap_md) > 30 else "fallback",
            },
            actions=[
                ClassroomAction(
                    id=f"act_mindmap_{scene_ts}",
                    type="speech",
                    text=speech_text,
                )
            ],
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
        # 密度：每 3 张讲解 → 1 个 mid 测验 + 末尾 1 个 final 测验
        # 实际 mid 数 = max(0, (N-1)//3)，加 1 个 final
        _n = len([s for i, s in enumerate(slide_scenes) if _is_quiz_source_scene(s, is_first_slide=(i == 0))])
        quiz_count_estimate = max(0, (_n - 1) // 3) + 1

        result_plan: list[tuple[str, ClassroomScene | int]] = []
        quiz_jobs: list[dict[str, Any]] = []
        quiz_index = 1
        pending_slides: list[ClassroomScene] = []
        quiz_source_slides = [
            scene for i, scene in enumerate(slide_scenes)
            if _is_quiz_source_scene(scene, is_first_slide=(i == 0))
        ]
        # 兜底：如果所有页面都被过滤为开场页，回退使用全部 slide（避免完全无测验）
        if not quiz_source_slides and slide_scenes:
            quiz_source_slides = list(slide_scenes)
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
            result_plan.append(("slide", scene))
            if scene.id not in quiz_source_ids:
                continue

            quiz_source_index += 1
            pending_slides.append(scene)

            is_last = quiz_source_index == total_quiz_source_slides
            # 密度调整：3 张讲解 → 1 个 mid 测验（之前是 2 张）
            enough_for_mid_quiz = len(pending_slides) >= 3 and not is_last
            enough_for_final_quiz = is_last and pending_slides

            if enough_for_mid_quiz or enough_for_final_quiz:
                # P1-3 调优：每 3 个测验页出 1 道简答题（quiz_index 3/6/9/...）
                # 配合"默认不强制"prompt，理论 ~33% 测验含简答。
                require_short_answer = (quiz_index % 3 == 0)
                quiz_jobs.append(
                    {
                        "quiz_index": quiz_index,
                        "scenes": list(pending_slides),
                        "max_questions": 2 if not is_last else 3,
                        "require_short_answer": require_short_answer,
                    }
                )
                result_plan.append(("quiz", quiz_index))
                quiz_index += 1
                pending_slides = []

        if not quiz_jobs:
            return [item for kind, item in result_plan if kind == "slide" and isinstance(item, ClassroomScene)]

        quiz_by_index: dict[int, ClassroomScene] = {}
        max_workers = min(DEFAULT_QUIZ_SCENE_MAX_CONCURRENCY, len(quiz_jobs))
        if self.llm_quiz_enabled:
            self._get_quiz_generator()
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="classroom-quiz") as executor:
            future_to_job = {
                executor.submit(
                    self._build_quiz_scene,
                    quiz_index=job["quiz_index"],
                    order=0,
                    topic=topic,
                    scenes=job["scenes"],
                    max_questions=job["max_questions"],
                    student_profile=student_profile,
                    cancel_check=cancel_check,
                    progress_callback=progress_callback,
                    require_short_answer=job["require_short_answer"],
                ): job
                for job in quiz_jobs
            }
            for done_idx, future in enumerate(as_completed(future_to_job), start=1):
                _raise_if_cancelled(cancel_check)
                job = future_to_job[future]
                quiz_scene = future.result()
                quiz_by_index[int(job["quiz_index"])] = quiz_scene
                _emit_progress(
                    progress_callback,
                    stage="insert_quizzes",
                    stage_index=2,
                    scene_index=done_idx,
                    scene_total=len(quiz_jobs),
                    scene=quiz_scene,
                )

        result: list[ClassroomScene] = []
        for kind, item in result_plan:
            if kind == "slide" and isinstance(item, ClassroomScene):
                result.append(item)
            elif kind == "quiz":
                quiz_scene = quiz_by_index.get(int(item))
                if quiz_scene is not None:
                    result.append(quiz_scene)
        return result

    def generate(
        self,
        user_id: str,
        topic: str,
        course: str,
        tts_config: dict[str, Any],
        ppt_job_id: str = "",
        student_profile: dict[str, Any] | None = None,
        generation_strategy: dict[str, Any] | None = None,
        lineage: dict[str, Any] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
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
        normalized_profile = (
            self._profile_from_generation_strategy(normalized_strategy)
            if normalized_strategy
            else _normalize_student_profile(student_profile)
        )

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
        slide_count = sum(1 for s in scenes if s.type == "slide")
        if slide_count >= 2:
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="classroom-mindmap") as executor:
                mindmap_future = executor.submit(
                    self._build_mindmap_scene,
                    topic,
                    list(scenes),
                    normalized_profile,
                    cancel_check,
                )
                scenes = self._insert_quiz_scenes(
                    topic, scenes, normalized_profile, cancel_check, progress_callback
                )
                _raise_if_cancelled(cancel_check)
                mindmap_scene = mindmap_future.result()
                if mindmap_scene is not None:
                    _emit_progress(
                        progress_callback,
                        stage="build_scenes",
                        stage_index=1,
                        scene_index=len(scenes),
                        scene_total=len(scenes) + 1,
                    )
                    scenes.append(mindmap_scene)
        else:
            scenes = self._insert_quiz_scenes(
                topic, scenes, normalized_profile, cancel_check, progress_callback
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

        # 阶段 4：合成音频（并发）
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

        if speech_actions:
            # 把 (scene, action) 拍平为 (action_id, text) 给并行函数
            # 保留 scene 引用以便 on_action_done 回写 audio_url
            action_by_id: dict[str, ClassroomAction] = {
                a.id: a for _, a in speech_actions
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
                # 推 progress（按完成顺序，不一定是输入顺序）
                _emit_progress(
                    progress_callback,
                    stage="synthesize_tts",
                    stage_index=3,
                    scene_index=done_idx,
                    scene_total=total,
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
