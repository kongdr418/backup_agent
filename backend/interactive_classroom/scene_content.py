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

def _sorted_svg_files(svg_dir: str) -> list[str]:
    if not os.path.exists(svg_dir):
        return []
    files = [f for f in os.listdir(svg_dir) if f.lower().endswith(".svg")]
    files.sort()
    return files

def _clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = unescape(value)
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s*[-*+]\s+", "", value)
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

def _scene_text_values(scene: ClassroomScene) -> list[str]:
    content = scene.content or {}
    extracted = content.get("extracted_text", [])
    values = [scene.title, *scene.knowledge_points]
    if isinstance(extracted, list):
        values.extend(str(item) for item in extracted)
    return [_clean_text(str(value)) for value in values if _clean_text(str(value))]

def _is_decorative_quiz_text(value: str) -> bool:
    text = _clean_text(value)
    if not text:
        return True
    lower = text.lower()
    # SVG 模板常把零填充章节号和页码计数单独放进 <text>，例如 "01"、
    # "02"、"3 / 10"。这些是视觉导航元素，不是可用于出题的知识点。
    # 保留普通年份、公式数字等内容，避免误删 "1943" 或 "100亿+"。
    if re.fullmatch(r"0\d{1,2}", text):
        return True
    if re.fullmatch(r"\d{1,3}\s*/\s*\d{1,3}", text):
        return True
    if re.fullmatch(r"\d{4}[年/-]\d{1,2}(?:[月/-]\d{1,2})?", text):
        return True
    if re.search(r"(欢迎来到|今天我们|今天，?我们|一起探索|开启.*之旅|探索.*之旅|从.*开始探索)", text):
        return True
    if re.search(r"(welcome|exploration|journey)", lower) and not re.search(r"[\u4e00-\u9fff]", text):
        return True
    if (
        not re.search(r"[\u4e00-\u9fff]", text)
        and " " in text
        and len(text) <= 48
        and re.fullmatch(r"[A-Z0-9][A-Z0-9 &:/+_.-]+", text)
    ):
        return True
    return False

def _is_low_quality_quiz_fragment(value: str) -> bool:
    text = _clean_text(value)
    if not text or _is_decorative_quiz_text(text):
        return True
    if re.match(r"^[—\-–_·•、：:，,\s]+", text):
        return True
    if re.match(r"^(情况[一二三四五六七八九十\d]+|第[一二三四五六七八九十\d]+种情况)\s*[：:、，,]?", text):
        return True
    if re.search(r"(同学们|大家|我们来看|我们来看看|接下来|首先|然后|现在|这里|本页|这一页)", text):
        return True
    if re.search(r"(示意图|页面|标题|主光轴)$", text) and len(text) <= 12:
        return True
    if re.fullmatch(r"[fuv]\s*[<≤>=]\s*[u2f\d\s<≤>=]+", text, flags=re.I):
        return True
    if len(text) < 10 and not re.search(r"(实像|虚像|倒立|正立|放大|缩小|焦距|物距|像距|会聚|发散)", text):
        return True
    return False

def _is_generic_quiz_label(value: str) -> bool:
    text = _clean_text(value)
    if not text:
        return True
    return bool(
        re.fullmatch(
            r"(补强材料\s*\d*|第\s*\d+\s*页|页面|标题|讲解页|课程导入|导入|总结过渡|核心概念|学习目标)",
            text,
        )
    )

def _is_meaningful_quiz_point(value: str) -> bool:
    text = _clean_knowledge_point(value)
    if not text or _is_decorative_quiz_text(text) or _is_generic_quiz_label(text):
        return False
    if not _is_low_quality_quiz_fragment(text):
        return True
    # 很多真实知识点很短（如“遮挡”“场景干扰”）。只要不是泛标签，
    # 就保留短中文概念，避免 fallback 题退回到大主题。
    return bool(re.search(r"[\u4e00-\u9fff]", text) and 2 <= len(text) <= 24)

def _is_explanatory_quiz_sentence(value: str) -> bool:
    text = _clean_text(value)
    if _is_low_quality_quiz_fragment(text):
        return False
    if len(text) < 14:
        return False
    return bool(
        re.search(
            r"(当|如果|因为|因此|所以|会|能够|不能|形成|决定|说明|表示|位于|大于|小于|等于|之间|以内|以外|实际|反向|会聚|发散|倒立|正立|放大|缩小|实像|虚像)",
            text,
        )
    )

def _quiz_points_from_scene(scene: ClassroomScene) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in [*scene.knowledge_points, *_scene_text_values(scene)]:
        text = _clean_knowledge_point(value)
        if (
            not text
            or text in seen
            or _is_decorative_quiz_text(text)
            or not _is_meaningful_quiz_point(text)
        ):
            continue
        seen.add(text)
        result.append(text)
    return result

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
    cleaned = _soften_repetitive_classroom_opening(_clean_text(text))
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip("，。；、 ") + "。"

def _soften_repetitive_classroom_opening(text: str) -> str:
    """避免每页语音都读成同一套“同学们，今天我们...”开场。"""
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    cleaned = re.sub(r"^同学们(?:好)?[，,、\s]*", "", cleaned)
    cleaned = re.sub(r"^今天(?:这节课)?(?:我们|咱们)(?:来|要|一起)?", "这一页我们", cleaned)
    return cleaned.strip()

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

def _merge_short_speech_segments(segments: list[str], min_chars: int = 24) -> list[str]:
    merged: list[str] = []
    idx = 0
    while idx < len(segments):
        current = segments[idx]
        if len(current) < min_chars and idx + 1 < len(segments):
            current = f"{current}{segments[idx + 1]}"
            idx += 2
        else:
            idx += 1
        merged.append(current)
    return merged

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

def _extract_svg_highlight_targets(svg: str, limit: int = 48) -> list[dict[str, Any]]:
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

def _is_low_signal_teaching_target(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return True
    if re.fullmatch(r"[xw]\s*[₀-₉0-9]+", cleaned, flags=re.I):
        return True
    if re.fullmatch(r"[a-z]\s*[₀-₉0-9]?", cleaned, flags=re.I):
        return True
    if re.fullmatch(r"\d+\s*/\s*\d+", cleaned):
        return True
    return False

def _teaching_target_score(text: str) -> int:
    cleaned = _clean_text(text)
    score = 0
    if re.search(r"[\u4e00-\u9fff]", cleaned):
        score += 4
    if re.search(r"(核心|步骤|流程|要点|类比|数学|表达|公式|输入|权重|求和|偏置|激活|输出|判断)", cleaned):
        score += 6
    if re.search(r"(Σ|σ|=|\+|×)", cleaned):
        score += 3
    if re.match(r"^\d+[.、]\s*", cleaned):
        score += 4
    if _is_low_signal_teaching_target(cleaned):
        score -= 8
    return score

def _select_teaching_targets(targets: list[dict[str, Any]], limit: int = 28) -> list[dict[str, Any]]:
    """选择给讲稿 LLM 的高亮目标，避免只截 SVG DOM 前几个碎片。

    SVG 文本通常按视觉顺序展开，前面可能连续出现 x1/x2/x3/w1 这类局部标注。
    如果直接 `targets[:8]`，讲稿模型会看不到后面的求和、激活函数、输出和核心要点。
    这里优先保留高信息目标，并从整页目标中做有序采样，保证前中后内容都能进入 prompt。
    """
    if len(targets) <= limit:
        return targets

    selected_indexes: set[int] = set()
    scored = [
        (idx, _teaching_target_score(str(target.get("text") or "")))
        for idx, target in enumerate(targets)
    ]

    for idx, score in sorted(scored, key=lambda item: (-item[1], item[0])):
        if score <= 0:
            continue
        selected_indexes.add(idx)
        if len(selected_indexes) >= limit:
            break

    if len(selected_indexes) < min(limit, len(targets)):
        step = max(1, len(targets) // limit)
        for idx in range(0, len(targets), step):
            selected_indexes.add(idx)
            if len(selected_indexes) >= limit:
                break

    if len(selected_indexes) < min(limit, len(targets)):
        for idx, _score in scored:
            selected_indexes.add(idx)
            if len(selected_indexes) >= limit:
                break

    return [targets[idx] for idx in sorted(selected_indexes)]

def _visible_text_lines_for_prompt(
    svg_texts: list[str],
    targets: list[dict[str, Any]] | None = None,
    limit: int = 48,
) -> list[str]:
    lines: list[str] = []
    target_texts = [str(target.get("text") or "") for target in (targets or [])]
    for text in [*svg_texts, *target_texts]:
        cleaned = _clean_text(text)
        if (
            not cleaned
            or cleaned in lines
            or re.search(r"\bpage\s*\d+\s*/\s*\d+\b", cleaned, flags=re.I)
        ):
            continue
        lines.append(cleaned)
        if len(lines) >= limit:
            break
    return lines

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

def _truncate_speech_text(text: str, max_chars: int) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    candidate = cleaned[:max_chars]
    sentence_end = max(candidate.rfind(mark) for mark in "。！？；")
    if sentence_end >= max_chars // 2:
        return candidate[: sentence_end + 1].strip()
    return candidate.rstrip("，、：； ") + "。"

def _segments_are_similar(left: str, right: str) -> bool:
    left_key = re.sub(r"[\W_]+", "", left.lower(), flags=re.UNICODE)
    right_key = re.sub(r"[\W_]+", "", right.lower(), flags=re.UNICODE)
    if not left_key or not right_key:
        return False
    if left_key in right_key or right_key in left_key:
        return min(len(left_key), len(right_key)) >= 18
    return SequenceMatcher(None, left_key, right_key).ratio() >= 0.82

def _normalize_teaching_segments(
    segments: list[dict[str, Any]],
    *,
    is_intro: bool,
    is_last: bool,
) -> list[dict[str, Any]]:
    """按页面类型限制讲稿长度，并删除重复或近似重复段落。"""
    if is_intro:
        max_segments, max_segment_chars, max_total_chars = 2, 80, 140
    elif is_last:
        max_segments, max_segment_chars, max_total_chars = 3, 110, 260
    else:
        max_segments, max_segment_chars, max_total_chars = 4, 130, 420

    result: list[dict[str, Any]] = []
    used_chars = 0
    for row in segments:
        if not isinstance(row, dict):
            continue
        target_id = str(row.get("target_id") or "").strip()
        text = _truncate_speech_text(str(row.get("text") or ""), max_segment_chars)
        if not target_id or len(text) < 12:
            continue
        if any(_segments_are_similar(text, str(item.get("text") or "")) for item in result):
            continue
        remaining = max_total_chars - used_chars
        if remaining < 12:
            break
        if len(text) > remaining:
            text = _truncate_speech_text(text, remaining)
        if len(text) < 12:
            break
        result.append(
            {
                "target_id": target_id,
                "mode": _safe_segment_mode(row.get("mode"), "outline"),
                "text": text,
            }
        )
        used_chars += len(text)
        if len(result) >= max_segments:
            break
    return result

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

def _target_for_teaching_text(
    text: str,
    targets: list[dict[str, Any]],
    used_target_ids: set[str],
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = 0
    text_key = re.sub(r"[\W_]+", "", text.lower(), flags=re.UNICODE)
    for target in targets:
        target_id = str(target.get("id") or "")
        target_text = str(target.get("text") or "")
        if not target_id or target_id in used_target_ids or _is_low_signal_teaching_target(target_text):
            continue
        target_key = re.sub(r"[\W_]+", "", target_text.lower(), flags=re.UNICODE)
        score = _match_text_score(text, target_text) + max(0, _teaching_target_score(target_text) // 4)
        if target_key and target_key in text_key:
            score += 20
        if "输出" in text and "输出" in target_text:
            score += 30
        if "激活" in text and "激活" in target_text:
            score += 20
        if "求和" in text and "求和" in target_text:
            score += 20
        if score > best_score:
            best = target
            best_score = score

    if best is not None and best_score > 0:
        return best

    for target in targets:
        target_id = str(target.get("id") or "")
        target_text = str(target.get("text") or "")
        if target_id and target_id not in used_target_ids and not _is_low_signal_teaching_target(target_text):
            return target
    return None

def _build_process_summary_text(svg_texts: list[str]) -> str:
    visible_text = " ".join(_visible_text_lines_for_prompt(svg_texts, limit=48))
    has_process = all(term in visible_text for term in ("输入", "权重")) and any(
        term in visible_text for term in ("求和", "激活函数", "输出")
    )
    if not has_process:
        return ""

    formula = "右侧公式里的 z 对应加权求和加偏置，y=σ(z) 对应经过激活函数后的输出。"
    if "z = Σ" in visible_text and "y = σ" in visible_text:
        formula = "右侧公式 z = Σ(xᵢ × wᵢ) + b 对应加权求和，y = σ(z) 对应激活后的输出。"
    return (
        "把流程连起来看：多个输入先乘以对应权重并加上偏置完成求和，"
        "再交给激活函数判断，最后得到输出 y，也就是激活或抑制信号。"
        f"{formula}"
    )

def _build_formula_summary_text(svg_texts: list[str], targets: list[dict[str, Any]] | None = None) -> str:
    target_text = " ".join(str(target.get("text") or "") for target in (targets or []))
    visible_text = f"{' '.join(_visible_text_lines_for_prompt(svg_texts, targets, limit=48))} {target_text}"
    if "z = Σ" not in visible_text and "y = σ" not in visible_text:
        return ""
    return (
        "页面右侧的数学表达可以对应到这条流程："
        "z = Σ(xᵢ × wᵢ) + b 表示把输入按权重求和并加上偏置，"
        "y = σ(z) 表示激活函数把结果转换成最终输出。"
    )

def _build_learning_process_summary_text(
    svg_texts: list[str],
    targets: list[dict[str, Any]] | None = None,
) -> str:
    visible_text = " ".join(_visible_text_lines_for_prompt(svg_texts, targets, limit=64))
    has_learning_process = all(
        term in visible_text
        for term in ("随机初始化", "训练数据", "计算误差", "反向传播")
    )
    if not has_learning_process:
        return ""

    if "反复迭代" in visible_text:
        return (
            "把流程按顺序串起来：先随机初始化权重；再用训练数据给出正确答案；"
            "接着计算预测和真实答案之间的误差；最后通过反向传播调整权重，"
            "并反复迭代直到准确率达标。"
        )
    return (
        "把流程按顺序串起来：先随机初始化权重，所以一开始输出可能是错的；"
        "再用训练数据做教材；接着计算预测和真实答案之间的误差；"
        "最后通过反向传播持续调整权重。"
    )

def _supplement_teaching_segments_from_targets(
    result: list[dict[str, Any]],
    source_targets: list[dict[str, Any]],
    *,
    title: str,
    min_segments: int = 3,
) -> None:
    """用页面可见高亮目标补足过短讲稿，避免 TTS 只读一句话就结束。"""
    if not source_targets:
        return

    used_target_ids = {str(item.get("target_id") or "") for item in result}
    existing_text = " ".join(str(item.get("text") or "") for item in result)
    target_limit = min(len(source_targets), max(min_segments, len(result)))
    for idx, target in enumerate(source_targets):
        if len(result) >= target_limit:
            break
        target_id = str(target.get("id") or "").strip()
        target_text = _clean_text(str(target.get("text") or ""))
        if (
            not target_id
            or not target_text
            or target_id in used_target_ids
            or _is_low_signal_teaching_target(target_text)
        ):
            continue
        if target_text in existing_text and len(result) >= 2:
            continue

        variant = len(result) % 3
        if idx == 0 and not result:
            text = (
                f"这一页我们先把视线放到“{target_text}”。"
                f"它是理解“{title or target_text}”这页内容的入口，"
                "先抓住它回答的问题，再看后续概念如何展开。"
            )
            mode = "spotlight"
        elif variant == 0:
            text = (
                f"接着看“{target_text}”。"
                f"把它和“{title or source_targets[0].get('text') or '本页主题'}”联系起来，"
                "先判断它描述的是对象、任务还是方法，再用一个具体场景复述它的作用。"
            )
            mode = "outline"
        elif variant == 1:
            text = (
                f"再关注“{target_text}”。"
                "这里更适合从学习任务角度理解：它通常对应一个需要完成的判断或处理步骤，"
                "所以听到例子时要先找输入信息，再看最终要得到什么结果。"
            )
            mode = "outline"
        else:
            text = (
                f"最后看“{target_text}”。"
                "请把它和前面概念做一次区分：它关注的范围、输出形式和应用场景各不相同。"
                "能说清这三个差别，就说明你已经抓住本页结构。"
            )
            mode = "outline"
        result.append({"target_id": target_id, "mode": mode, "text": text})
        used_target_ids.add(target_id)
        existing_text = f"{existing_text} {text}"

def _fallback_teaching_segments(
    title: str,
    manuscript_note: str,
    targets: list[dict[str, Any]],
    svg_texts: list[str],
    *,
    is_intro: bool = False,
    is_last: bool = False,
) -> list[dict[str, Any]]:
    source_targets = _select_teaching_targets(targets, limit=24)
    if not source_targets:
        source_targets = [
            {"id": f"hl_{idx + 1:03d}", "text": text}
            for idx, text in enumerate(svg_texts[:5])
            if text
        ]
    if not source_targets:
        source_targets = [{"id": "hl_001", "text": title or "本页主题"}]

    note = _clean_text(manuscript_note)
    if is_intro:
        opening = (
            f"这一页先认识本节主题“{title}”。"
            "这里先建立整体方向，具体概念和案例会在后续页面逐步展开。"
        )
        return _normalize_teaching_segments(
            [
                {
                    "target_id": source_targets[0]["id"],
                    "mode": "spotlight",
                    "text": opening,
                }
            ],
            is_intro=True,
            is_last=False,
        )

    if note:
        used_target_ids: set[str] = set()
        result: list[dict[str, Any]] = []
        note_segments = _merge_short_speech_segments(_split_speech_segments(note, limit=6))
        for idx, segment in enumerate(note_segments[:5]):
            target = _target_for_teaching_text(segment, source_targets, used_target_ids)
            if target is None:
                continue
            segment_text = segment
            if len(_clean_text(segment_text)) < 12:
                target_text = _clean_text(str(target.get("text") or title or "本页主题"))
                segment_text = (
                    f"{segment_text}"
                    f"这里先抓住“{target_text}”这个核心词：它是本页其它概念的上位主题，"
                    "后面几个关键词都可以围绕它来判断用途和区别。"
                )
            used_target_ids.add(str(target["id"]))
            result.append(
                {
                    "target_id": target["id"],
                    "mode": "spotlight" if idx == 0 else "outline",
                    "text": segment_text,
                }
            )

        process_summary = _build_process_summary_text(svg_texts)
        if process_summary and not any(_segments_are_similar(process_summary, str(item.get("text") or "")) for item in result):
            target = _target_for_teaching_text(process_summary, source_targets, used_target_ids)
            if target is not None:
                used_target_ids.add(str(target["id"]))
                result.append(
                    {
                        "target_id": target["id"],
                        "mode": "outline",
                        "text": process_summary,
                    }
                )
        formula_summary = _build_formula_summary_text(svg_texts, targets)
        if formula_summary and not any(_segments_are_similar(formula_summary, str(item.get("text") or "")) for item in result):
            target = _target_for_teaching_text(formula_summary, source_targets, used_target_ids)
            if target is not None:
                result.append(
                    {
                        "target_id": target["id"],
                        "mode": "outline",
                        "text": formula_summary,
                    }
                )
        learning_summary = _build_learning_process_summary_text(svg_texts, targets)
        if learning_summary and not any(_segments_are_similar(learning_summary, str(item.get("text") or "")) for item in result):
            target = _target_for_teaching_text(learning_summary, source_targets, used_target_ids)
            if target is not None:
                result.append(
                    {
                        "target_id": target["id"],
                        "mode": "outline",
                        "text": learning_summary,
                    }
                )

        if result:
            _supplement_teaching_segments_from_targets(
                result,
                source_targets,
                title=title,
                min_segments=3,
            )
            return _normalize_teaching_segments(
                result,
                is_intro=False,
                is_last=is_last,
            )

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
            patterns = (
                (
                    f"接着看“{target_text}”。先确认它描述的对象或任务，"
                    "再结合页面文字判断它与主题的关系。重点不是孤立记名词，"
                    "而是理解它在实际场景中解决什么问题。"
                ),
                (
                    f"再关注“{target_text}”。把它和前面的重点做一次区分，"
                    "分别观察输入、处理目标和输出结果。这样遇到具体例子时，"
                    "就能判断当前讨论的是哪个概念。"
                ),
                (
                    f"最后看“{target_text}”。尝试用自己的话说明它的作用，"
                    "再想一个能够体现这个作用的场景。能完成这两步，"
                    "才算真正理解了页面上的信息。"
                ),
            )
            text = patterns[(idx - 1) % len(patterns)]
            mode = "outline"
        result.append({"target_id": target["id"], "mode": mode, "text": text})
    return _normalize_teaching_segments(
        result,
        is_intro=False,
        is_last=is_last,
    )

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
    result = {
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
    for key in ("content_strategy", "assessment_strategy", "interaction_strategy"):
        value = strategy.get(key)
        result[key] = value if isinstance(value, dict) else {}
    result["evidence_ids"] = [
        _clean_text(str(value))[:180]
        for value in strategy.get("evidence_ids", [])
        if _clean_text(str(value))
    ][:20]
    return result

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

def _scene_text_snippets(scene: ClassroomScene, max_items: int = 3) -> list[str]:
    content = scene.content or {}
    values: list[str] = []
    for action in scene.actions or []:
        if action.type == "speech" and action.text:
            values.append(action.text)
    markdown = content.get("markdown", "")
    if markdown:
        values.append(str(markdown))
    extracted = content.get("extracted_text", [])
    if isinstance(extracted, list):
        values.extend(str(item) for item in extracted)

    snippets: list[str] = []
    for value in values:
        cleaned = _clean_text(re.sub(r"[#*_`>\-\s]+", " ", str(value)))
        if not cleaned:
            continue
        for part in re.split(r"[。！？!?；;]\s*", cleaned):
            part = _clean_text(part)
            if len(part) < 8:
                continue
            if not _is_explanatory_quiz_sentence(part):
                continue
            if part not in snippets:
                snippets.append(part[:90])
            if len(snippets) >= max_items:
                return snippets
    return snippets

def _conceptual_distractors(
    correct: str,
    *,
    scene_title: str,
    topic: str,
    pool: list[str],
) -> list[str]:
    generic = [
        f"只记住“{scene_title or topic}”这个标题，不需要说明判断依据",
        "优先关注页面顺序和视觉样式，而不是概念之间的关系",
        "遇到题目时直接选择看起来最熟悉的词，不需要结合情境分析",
        f"把所有问题都归因于{topic or '本节主题'}，不用区分具体条件",
    ]
    candidates = [
        item
        for item in [*pool, *generic]
        if item and item != correct and not _is_low_quality_quiz_fragment(item)
    ]
    result: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        cleaned = _clean_text(item)[:90]
        if not cleaned or cleaned in seen or cleaned == correct:
            continue
        seen.add(cleaned)
        result.append(cleaned)
        if len(result) >= 6:
            break
    return result

def _question_has_scene_index(text: str) -> bool:
    return bool(re.search(r"第\s*\d+\s*个讲解场景", text or ""))

def _is_meta_practice_question_text(text: str) -> bool:
    return bool(
        re.search(
            r"(学习报告|报告建议|课堂建议|推荐优先复习|被推荐优先复习|推荐原因|掌握证据|本次课堂报告|复习范围|应围绕哪些核心方面)",
            _clean_text(text),
        )
    )

def _practice_evidence_by_point(assessment: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    evidence_rows = assessment.get("practice_evidence", [])
    if not isinstance(evidence_rows, list):
        return result
    for row in evidence_rows:
        if not isinstance(row, dict):
            continue
        point = _clean_text(str(row.get("point") or ""))
        snippets = [
            _clean_text(str(value))
            for value in row.get("snippets", [])
            if _clean_text(str(value))
        ][:8]
        if point:
            result[point] = snippets
    return result

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

QUIZ_SOURCE_SUMMARY_SKIP_KEYWORDS = (
    "\u8bfe\u7a0b\u603b\u7ed3",
    "\u603b\u7ed3",
    "\u590d\u76d8",
    "\u56de\u987e",
    "\u62d3\u5c55",
    "\u5c55\u671b",
    "\u4e0b\u4e00\u6b65",
    "\u8bfe\u540e",
    "summary",
    "review",
    "wrap up",
    "next step",
)

QUIZ_SOURCE_INTERACTION_TITLE_KEYWORDS = (
    "\u63d0\u95ee",
    "\u95ee\u9898",
    "\u8ba8\u8bba",
    "\u7b54\u7591",
    "\u4e92\u52a8",
    "\u95ee\u7b54",
    "q&a",
    "qa",
    "question",
    "discussion",
)

INTRO_SLIDE_KEYWORDS = (
    # 封面/标题页（高置信度）
    "课程介绍", "课程简介", "课程目录", "课程导览", "课程安排",
    # 目录/大纲页
    "目录", "内容概览", "章节概览", "学习路径",
    "agenda", "contents", "outline",
    # 通用开场
    "自我介绍", "讲师介绍", "欢迎", "开场",
    "welcome", "introduction", "intro", "导论",
)

INTRO_SLIDE_FULL_TEXT_KEYWORDS = (
    "overview",
    "课程学习路径",
    "课程学习路线",
)

INTRO_FIRST_SLIDE_TITLE_KEYWORDS = (
    "项目导入",
    "课程导入",
    "学习导入",
    "导学",
)

def _is_intro_slide(scene: ClassroomScene, *, is_first_slide: bool = False) -> bool:
    """检测开场/封面/目录页，这些页面不应生成测验题。"""
    title = (scene.title or "").strip()
    title_lower = title.lower()
    points = [p.strip() for p in scene.knowledge_points if p.strip()]
    visible_texts = _scene_text_values(scene)
    combined_raw = f"{title} {' '.join(points)} {' '.join(visible_texts)}"
    combined = combined_raw.lower()

    # Signal A: 标题命中关键词 → 直接判定为开场页
    for kw in INTRO_SLIDE_KEYWORDS:
        if kw in title_lower:
            return True

    # Signal A2: 明确的总览/学习路径页，即使标题较长也不作为测验来源。
    for kw in INTRO_SLIDE_FULL_TEXT_KEYWORDS:
        if kw.lower() in combined:
            return True

    # Signal A3: 首页导入页不是知识检测来源；避免泛化到"模块导入"等内容页。
    if is_first_slide and any(kw in title_lower for kw in INTRO_FIRST_SLIDE_TITLE_KEYWORDS):
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

    # Signal D: 首页 + 欢迎/探索之旅/装饰英文标题等封面话术 → 判定为开场页
    if is_first_slide and (
        re.search(r"(欢迎来到|今天我们|今天，?我们|一起探索|开启.*之旅|探索.*之旅|从.*开始探索)", combined_raw)
        or any(_is_decorative_quiz_text(text) for text in visible_texts)
    ):
        return True

    return False

def _is_quiz_source_scene(scene: ClassroomScene, *, is_first_slide: bool = False) -> bool:
    text = " ".join([scene.title, *_quiz_points_from_scene(scene)]).lower()
    if not text.strip():
        return False  # 空标题+空知识点的页面不是有效的出题源
    if _is_intro_slide(scene, is_first_slide=is_first_slide):
        return False
    title = (scene.title or "").lower()
    if any(keyword in text for keyword in QUIZ_SOURCE_SUMMARY_SKIP_KEYWORDS):
        return False
    if any(keyword in title for keyword in QUIZ_SOURCE_INTERACTION_TITLE_KEYWORDS):
        return False
    return True

