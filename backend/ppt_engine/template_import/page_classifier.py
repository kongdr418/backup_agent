"""Classify slides into cover/toc/chapter/content/ending page types.

Combines weighted heuristic signals (position, text density, keywords,
decoration ratio, chapter-number pattern, large-font ratio) with an
optional LLM tie-break. Output is partition-complete: each slot is
either null or a slide index in [1, slide_count], with content forced
non-null when slide_count >= 1.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

from .types import PageClassification

if TYPE_CHECKING:  # pragma: no cover
    from .types import PageType, SlideMetrics


# Constants

_PRIORITY: tuple[str, ...] = ("cover", "ending", "chapter", "toc", "content")
_PAGE_TYPES: tuple[str, ...] = ("cover", "toc", "chapter", "content", "ending")

WEIGHTS: dict[str, dict[str, float]] = {
    "cover": {
        "is_first_slide": 1.0, "is_last_slide": -1.0,
        "text_density": -0.3, "keyword_toc": -0.5,
        "keyword_thanks": -0.5, "keyword_chapter": -0.3,
        "decoration_ratio": 0.4, "chapter_number_pattern": 0.0,
        "large_font_ratio": 0.5,
    },
    "toc": {
        "is_first_slide": -0.4, "is_last_slide": -0.4,
        "text_density": 0.4, "keyword_toc": 1.2,
        "keyword_thanks": -0.5, "keyword_chapter": -0.3,
        "decoration_ratio": -0.2, "chapter_number_pattern": 0.0,
        "large_font_ratio": 0.2,
    },
    "chapter": {
        "is_first_slide": -0.2, "is_last_slide": -0.2,
        "text_density": -0.2, "keyword_toc": -0.5,
        "keyword_thanks": -0.5, "keyword_chapter": 1.2,
        "decoration_ratio": 0.5, "chapter_number_pattern": 0.8,
        "large_font_ratio": 0.6,
    },
    "content": {
        "is_first_slide": -0.5, "is_last_slide": -0.5,
        "text_density": 0.7, "keyword_toc": -0.3,
        "keyword_thanks": -0.3, "keyword_chapter": -0.5,
        "decoration_ratio": -0.4, "chapter_number_pattern": -0.2,
        "large_font_ratio": -0.4,
    },
    "ending": {
        "is_first_slide": -1.0, "is_last_slide": 1.0,
        "text_density": -0.3, "keyword_toc": -0.5,
        "keyword_thanks": 1.2, "keyword_chapter": -0.5,
        "decoration_ratio": 0.3, "chapter_number_pattern": 0.0,
        "large_font_ratio": 0.3,
    },
}

# General-purpose keywords (not paper-specific)
_TOC_KEYWORDS: tuple[str, ...] = ("目录", "contents", "outline", "agenda")
_THANKS_KEYWORDS: tuple[str, ...] = ("谢谢", "thanks", "thank you", "结束", "q&a", "questions")
_CHAPTER_KEYWORDS: tuple[str, ...] = (
    "章", "节", "chapter", "part", "section", "模块", "单元",
)
_CHAPTER_SMALL_TEXT_THRESHOLD: int = 5
_LARGE_FONT_PX: float = 32.0

_CHAPTER_NUMBER_RE = re.compile(
    r"^\s*(?:(?:0?[1-9]|10)\b|第[一二三四五六七八九十\d]+[章模块单元]|"
    r"(?:PART|CHAPTER|SECTION|MODULE|UNIT)\s+\d+)",
    re.IGNORECASE,
)

_LLM_OVERRIDE_THRESHOLD: float = 0.6


# Helpers

def _clamp01(x: float) -> float:
    if x != x:
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return float(x)


def _get(slide: Any, key: str, default: Any) -> Any:
    if isinstance(slide, dict):
        return slide.get(key, default)
    return getattr(slide, key, default)


def _any_keyword_in_runs(runs: list[str], keywords: tuple[str, ...]) -> bool:
    for run in runs:
        if not isinstance(run, str):
            continue
        lower = run.lower()
        for kw in keywords:
            if kw.lower() in lower:
                return True
    return False


def _softmax(logits: dict[str, float]) -> dict[str, float]:
    if not logits:
        return {}
    max_l = max(logits.values())
    exps = {k: math.exp(v - max_l) for k, v in logits.items()}
    total = sum(exps.values())
    if total == 0.0:
        n = len(logits)
        return {k: 1.0 / n for k in logits}
    return {k: v / total for k, v in exps.items()}


# Signal extraction

def extract_signals(slide: Any, metrics: "SlideMetrics") -> dict[str, float]:
    slide_index = int(_get(slide, "slide_index", 1))
    total_slides = int(_get(slide, "total_slides", 1))
    text_runs_raw = _get(slide, "text_runs", []) or []
    text_runs: list[str] = [r for r in text_runs_raw if isinstance(r, str)]
    images = _get(slide, "images", []) or []
    font_sizes_raw = _get(slide, "font_sizes", []) or []

    is_first = 1.0 if slide_index == 1 else 0.0
    is_last = 1.0 if slide_index == total_slides else 0.0
    text_density = _clamp01(float(_get(slide, "text_density", 0.0) or 0.0))

    keyword_toc = 1.0 if _any_keyword_in_runs(text_runs, _TOC_KEYWORDS) else 0.0
    keyword_thanks = 1.0 if _any_keyword_in_runs(text_runs, _THANKS_KEYWORDS) else 0.0
    chapter_kw_present = _any_keyword_in_runs(text_runs, _CHAPTER_KEYWORDS)
    keyword_chapter = (
        1.0
        if chapter_kw_present and len(text_runs) <= _CHAPTER_SMALL_TEXT_THRESHOLD
        else 0.0
    )

    canvas_w = float(getattr(metrics, "canvas_width", 0) or 0)
    canvas_h = float(getattr(metrics, "canvas_height", 0) or 0)
    canvas_area = canvas_w * canvas_h
    if canvas_area > 0:
        total_area = 0.0
        for img in images:
            if not isinstance(img, dict):
                continue
            area = img.get("area")
            if area is None:
                w = float(img.get("width", 0) or 0)
                h = float(img.get("height", 0) or 0)
                area = w * h
            try:
                total_area += float(area)
            except (TypeError, ValueError):
                continue
        decoration_ratio = _clamp01(total_area / canvas_area)
    else:
        decoration_ratio = 0.0

    chapter_number_pattern = 0.0
    for run in text_runs:
        if _CHAPTER_NUMBER_RE.match(run):
            chapter_number_pattern = 1.0
            break

    large_count = 0
    total_fonts = 0
    for fs in font_sizes_raw:
        try:
            size = float(fs)
        except (TypeError, ValueError):
            continue
        total_fonts += 1
        if size >= _LARGE_FONT_PX:
            large_count += 1
    large_font_ratio = _clamp01(large_count / total_fonts) if total_fonts else 0.0

    return {
        "is_first_slide": is_first,
        "is_last_slide": is_last,
        "text_density": text_density,
        "keyword_toc": keyword_toc,
        "keyword_thanks": keyword_thanks,
        "keyword_chapter": keyword_chapter,
        "decoration_ratio": decoration_ratio,
        "chapter_number_pattern": chapter_number_pattern,
        "large_font_ratio": large_font_ratio,
    }


# classify()

def classify(
    slides: list[Any],
    metrics: list["SlideMetrics"],
    *,
    llm_hint: dict[str, int | None] | None = None,
) -> dict[int, PageClassification]:
    del llm_hint

    if not slides:
        return {}

    metrics_by_index: dict[int, "SlideMetrics"] = {}
    for m in metrics:
        idx = int(getattr(m, "slide_index", 0) or 0)
        if idx > 0:
            metrics_by_index[idx] = m

    fallback_metric: "SlideMetrics" | None = metrics[0] if metrics else None

    out: dict[int, PageClassification] = {}
    for slide in slides:
        slide_index = int(_get(slide, "slide_index", 0) or 0)
        if slide_index <= 0:
            continue
        metric = metrics_by_index.get(slide_index, fallback_metric)
        if metric is None:
            signals = {k: 0.0 for k in WEIGHTS["cover"]}
        else:
            signals = extract_signals(slide, metric)

        logits: dict[str, float] = {}
        for page_type in _PAGE_TYPES:
            weights = WEIGHTS[page_type]
            logits[page_type] = sum(
                weights[k] * signals.get(k, 0.0) for k in weights
            )

        probs = _softmax(logits)
        best_type: str | None = None
        best_prob: float = -1.0
        for pt in _PAGE_TYPES:
            p = probs.get(pt, 0.0)
            if p > best_prob:
                best_prob = p
                best_type = pt

        signals_with_probs = dict(signals)
        for pt, p in probs.items():
            signals_with_probs[f"p_{pt}"] = p

        out[slide_index] = PageClassification(
            page_type=best_type,  # type: ignore[arg-type]
            confidence=float(best_prob if best_prob >= 0 else 0.0),
            signals=signals_with_probs,
        )
    return out


# select_representatives()

def select_representatives(
    classifications: dict[int, PageClassification],
    *,
    llm_selections: dict[str, Any] | None = None,
) -> tuple[dict[str, int | None], list[str]]:
    selections: dict[str, int | None] = {pt: None for pt in _PAGE_TYPES}
    rule_patches: list[str] = []

    if not classifications:
        return selections, rule_patches

    slide_count = len(classifications)
    valid_indices = set(classifications.keys())

    # Rule-based greedy by priority
    rule_selections: dict[str, int | None] = {pt: None for pt in _PAGE_TYPES}
    used: set[int] = set()
    for page_type in _PRIORITY:
        best_idx: int | None = None
        best_conf: float = -1.0
        for idx in sorted(classifications.keys()):
            if idx in used:
                continue
            cls = classifications[idx]
            if cls.page_type != page_type:
                continue
            if cls.confidence > best_conf:
                best_conf = cls.confidence
                best_idx = idx
        if best_idx is not None:
            rule_selections[page_type] = best_idx
            used.add(best_idx)

    # Optional LLM override
    use_llm = False
    llm_conf = 0.0
    llm_map: dict[str, int | None] = {}
    if llm_selections:
        try:
            llm_conf = float(llm_selections.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            llm_conf = 0.0
        if llm_conf >= _LLM_OVERRIDE_THRESHOLD:
            use_llm = True
            for pt in _PAGE_TYPES:
                v = llm_selections.get(pt)
                if v is None:
                    llm_map[pt] = None
                else:
                    try:
                        idx = int(v)
                    except (TypeError, ValueError):
                        continue
                    if idx in valid_indices:
                        llm_map[pt] = idx

    if use_llm:
        used_llm: set[int] = set()
        for page_type in _PRIORITY:
            rule_pick = rule_selections.get(page_type)
            llm_pick = llm_map.get(page_type, rule_pick)
            choice: int | None
            if page_type in llm_map:
                if llm_pick is not None and llm_pick in used_llm:
                    choice = rule_pick if (rule_pick is not None and rule_pick not in used_llm) else None
                else:
                    choice = llm_pick
                if choice != rule_pick:
                    rule_patches.append(
                        f"page_selections.{page_type}: rule={rule_pick} -> llm={llm_pick} "
                        f"(confidence={llm_conf:.2f})"
                    )
            else:
                choice = rule_pick if (rule_pick is None or rule_pick not in used_llm) else None
            selections[page_type] = choice
            if choice is not None:
                used_llm.add(choice)
        used = used_llm
    else:
        selections = dict(rule_selections)
        used = {v for v in selections.values() if v is not None}

    # Content fallback
    if slide_count >= 1 and selections.get("content") is None:
        candidates: list[tuple[float, int]] = []
        for idx, cls in classifications.items():
            if idx in used:
                continue
            density = float(cls.signals.get("text_density", 0.0) or 0.0)
            candidates.append((density, idx))
        if candidates:
            candidates.sort(key=lambda t: (-t[0], t[1]))
            chosen = candidates[0][1]
            selections["content"] = chosen
            used.add(chosen)
        else:
            for page_type in reversed(_PRIORITY):
                if page_type == "content":
                    continue
                pick = selections.get(page_type)
                if pick is not None:
                    selections["content"] = pick
                    selections[page_type] = None
                    break

    return selections, rule_patches


__all__ = ["WEIGHTS", "extract_signals", "classify", "select_representatives"]
