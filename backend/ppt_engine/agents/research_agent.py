"""Deep Research agent: 4-pass analysis of educational topics for slide manuscripts.

Architecture:
    Pass 1 — Topic Deep Analysis: multi-angle analysis of the topic.
    Pass 2 — Teaching Narrative Arc: design a pedagogical narrative structure.
    Pass 3 — Manuscript: generate the actual slide manuscript.
    Pass 4 — Self-Review: evaluate quality and revise if needed.

Deep research is opt-in. Without it, the standard content_planner is used.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from ppt_engine.llm import LLMMessage, LLMProvider, LLMResponse
from ppt_engine.agents.provider_guidance import deepseek_research_guidance, is_deepseek_provider

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

PASS1_PROMPT = PROMPTS_DIR / "research_pass1_topic_analysis.md"
PASS2_PROMPT = PROMPTS_DIR / "research_pass2_narrative.md"
PASS3_PROMPT = PROMPTS_DIR / "research_pass3_manuscript.md"
PASS4_PROMPT = PROMPTS_DIR / "research_pass4_review.md"

DEEPSEEK_MAX_TOKENS = 24576
QUALITY_THRESHOLD = 28  # out of 35 (7 dimensions x 5 points each)
MAX_MANUSCRIPT_ATTEMPTS = 3

_SLIDE_DELIMITER_RE = re.compile(r"(?m)^\s*---\s*$")
_SLIDE_HEADING_RE = re.compile(r"^##\s+(?:slide|幻灯片)\s*\d+\s*[:：].*$", re.IGNORECASE)
_MANUSCRIPT_MARKER_RE = re.compile(
    r"^##\s+(?:slide\s+manuscript(?:\s*\([^)]*\))?|"
    r"revised\s+slide\s+manuscript|final\s+slide\s+manuscript|"
    r"revised\s+manuscript|final\s+manuscript)\s*$",
    re.IGNORECASE,
)
_REVIEW_HEADING_RE = re.compile(
    r"^##\s+(?:step\s*\d+|assessment|review|quality|evaluation|consensus|issues)\b",
    re.IGNORECASE,
)


@dataclass
class ResearchEvent:
    stage: str
    status: str
    message: str
    progress: float
    data: dict | None = None


def _language_guidance(language: str) -> str:
    guidance = {
        "zh": (
            "使用简体中文撰写所有幻灯片标题、要点和内容。"
            "专有名词、技术术语可保留英文原文。"
        ),
        "en": "Write all slide titles, bullets, and content in English.",
        "bilingual": (
            "Slide titles and core bullets may include both Chinese and English. "
            "Keep terminology aligned across both languages."
        ),
    }
    normalized = language.strip().lower()
    if normalized in guidance:
        return guidance[normalized]
    return f"Write all visible slide content in {language.strip()}."


DETAIL_GUIDANCE = {
    "normal": (
        "生成简洁清晰的课程幻灯片内容，覆盖核心知识点，"
        "每页 2-4 个要点，适合 30-45 分钟的课堂讲解。"
    ),
    "high": (
        "生成较详细的课程内容，深入讲解每个知识点，"
        "包含更多示例和应用场景，每页 3-5 个要点。"
    ),
    "very_high": (
        "生成详尽的课程内容，包含完整原理解释、多个示例、"
        "对比分析和扩展知识，适合研究生级别的深入讲解。"
    ),
}


def _target_slides_guidance(num_slides: int | None, detail_level: str) -> str:
    if num_slides:
        return (
            f"Target exactly {num_slides} slides. Use {num_slides - 1} standalone `---` delimiters.\n"
            f"Structure: cover (1) + content chapters ({num_slides - 2}) + ending (1)."
        )
    return (
        "Determine slide count automatically based on topic complexity (typically 10-12).\n"
        "Use standalone `---` lines as slide delimiters."
    )


def _normalize_manuscript_delimiters(text: str) -> str:
    """Normalize slide delimiters to standalone --- lines."""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped == "---" or stripped == "***" or stripped == "___":
            if not result or result[-1].strip() != "---":
                result.append("---")
        else:
            result.append(line)
    return "\n".join(result).strip()


def _manuscript_structure_error(
    manuscript: str,
    num_slides: int | None,
    detail_level: str,
) -> str | None:
    """Validate manuscript structure."""
    pages = [p.strip() for p in _SLIDE_DELIMITER_RE.split(manuscript) if p.strip()]
    if len(pages) < 3:
        return f"Too few slides ({len(pages)}); expected at least 3."

    if num_slides and abs(len(pages) - num_slides) > 2:
        return f"Expected ~{num_slides} slides, got {len(pages)}."

    # Check first page has title-like content
    first_page = pages[0]
    if not re.search(r"^#\s+", first_page, re.MULTILINE) and len(first_page) < 20:
        return "First slide (cover) appears to lack a title."

    return None


def _manuscript_depth_feedback(manuscript: str, detail_level: str) -> str | None:
    """Check content slides for sufficient depth."""
    if detail_level == "normal":
        return None

    pages = [p.strip() for p in _SLIDE_DELIMITER_RE.split(manuscript) if p.strip()]
    thin_pages = []
    for i, page in enumerate(pages, 1):
        # Skip cover and ending pages
        if i == 1 or i == len(pages):
            continue
        char_count = len(page)
        threshold = {"high": 100, "very_high": 150}.get(detail_level, 100)
        if char_count < threshold:
            thin_pages.append(f"Slide {i} ({char_count} chars)")

    if thin_pages and len(thin_pages) >= 2:
        return (
            f"These content slides appear too thin for '{detail_level}' detail: "
            f"{', '.join(thin_pages[:5])}. Add more explanation, examples, or evidence."
        )
    return None


def _extract_manuscript_from_review(review_output: str, original_manuscript: str) -> str:
    """Extract the final manuscript from Pass 4 review output."""
    if "QUALITY_CHECK_PASSED" in review_output:
        return original_manuscript

    # Try to find manuscript marker
    lines = review_output.splitlines()
    for i, line in enumerate(lines):
        if _MANUSCRIPT_MARKER_RE.match(line.strip()):
            start = i + 1
            while start < len(lines) and (
                not lines[start].strip()
                or lines[start].strip() == "---"
                or lines[start].strip() == "QUALITY_CHECK_PASSED"
            ):
                start += 1
            if start < len(lines):
                return "\n".join(lines[start:]).strip()

    # Try numbered slide headings
    for i, line in enumerate(lines):
        if _SLIDE_HEADING_RE.match(line.strip()):
            return "\n".join(lines[i:]).strip()

    # If it has slide separators, try to extract after assessment
    if review_output.count("---") >= 2:
        manuscript_start = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("## ") and i > 0 and not _REVIEW_HEADING_RE.match(stripped):
                for j in range(i, min(i + 30, len(lines))):
                    if lines[j].strip() == "---":
                        manuscript_start = i
                        break
                if manuscript_start is not None:
                    break
        if manuscript_start is not None:
            return "\n".join(lines[manuscript_start:]).strip()

    logger.warning("Could not extract revised manuscript from review; using original")
    return original_manuscript


def _debug_write(debug_dir: Path | None, filename: str, content: str) -> None:
    if debug_dir is None:
        return
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / filename).write_text(content, encoding="utf-8")
    except OSError:
        logger.exception("Failed to write debug file %s", filename)


async def run_deep_research(
    topic: str,
    llm: LLMProvider,
    model: str,
    *,
    language: str = "zh",
    num_slides: int | None = None,
    detail_level: str = "normal",
    provider_guidance: str = "",
    debug_dir: Path | None = None,
) -> AsyncIterator[ResearchEvent]:
    """4-Pass deep research flow for educational topics.

    Pass 1: Topic Deep Analysis
    Pass 2: Teaching Narrative Arc Design
    Pass 3: Manuscript Generation
    Pass 4: Quality Self-Review

    Yields ResearchEvent objects for progress tracking.
    """
    is_deepseek = is_deepseek_provider(llm, model)
    detail_text = DETAIL_GUIDANCE.get(detail_level, DETAIL_GUIDANCE["normal"])
    slides_guidance = _target_slides_guidance(num_slides, detail_level)

    # ── Pass 1: Topic Deep Analysis ──────────────────────────────────────
    yield ResearchEvent("research_pass1", "started", "Pass 1: Topic deep analysis...", 0.05)

    pass1_system = PASS1_PROMPT.read_text(encoding="utf-8")
    pass1_user_parts = [
        f"## 教学主题\n\n{topic}",
        f"\n## 详细程度\n\n{detail_level}\n\n{detail_text}",
        f"\n## 语言\n\n{language}\n\n{_language_guidance(language)}",
    ]
    if provider_guidance:
        pass1_user_parts.append(f"\n{provider_guidance}")
    if is_deepseek:
        pass1_user_parts.append("\n" + deepseek_research_guidance(detail_level))
    pass1_user_parts.append(
        "\n\n请按照上述结构对主题进行深度分析。要具体、有洞察力。"
    )

    pass1_messages = [
        LLMMessage.system(pass1_system),
        LLMMessage.user("\n".join(pass1_user_parts)),
    ]
    pass1_response = await llm.chat(
        pass1_messages, model, temperature=0.4,
        max_tokens=DEEPSEEK_MAX_TOKENS if is_deepseek else None,
    )
    deep_analysis = pass1_response.content
    _debug_write(debug_dir, "research_pass1_response.md", deep_analysis)
    logger.info("Research Pass 1 complete (%d chars)", len(deep_analysis))
    yield ResearchEvent("research_pass1", "completed", "Topic analysis complete", 0.15)

    # ── Pass 2: Teaching Narrative Arc ───────────────────────────────────
    yield ResearchEvent("research_pass2", "started", "Pass 2: Narrative arc design...", 0.15)

    pass2_system = PASS2_PROMPT.read_text(encoding="utf-8")
    pass2_user_parts = [
        f"## 主题深度分析\n\n{deep_analysis}",
        f"\n## 目标页数\n\n{slides_guidance}",
        f"\n## 详细程度\n\n{detail_level}",
    ]
    pass2_user_parts.append(
        "\n\n请设计这个主题的教学叙事弧。选择最佳叙事策略，"
        "并为每页指定角色、核心内容和视觉策略。"
    )

    pass2_messages = [
        LLMMessage.system(pass2_system),
        LLMMessage.user("\n".join(pass2_user_parts)),
    ]
    pass2_response = await llm.chat(
        pass2_messages, model, temperature=0.5,
        max_tokens=DEEPSEEK_MAX_TOKENS if is_deepseek else None,
    )
    narrative_plan = pass2_response.content
    _debug_write(debug_dir, "research_pass2_response.md", narrative_plan)
    logger.info("Research Pass 2 complete (%d chars)", len(narrative_plan))
    yield ResearchEvent("research_pass2", "completed", "Narrative arc designed", 0.20)

    # ── Pass 3: Manuscript Generation ────────────────────────────────────
    yield ResearchEvent("research_pass3", "started", "Pass 3: Manuscript generation...", 0.20)

    pass3_system = PASS3_PROMPT.read_text(encoding="utf-8")
    pass3_user_parts = [
        f"## 主题深度分析\n\n{deep_analysis}",
        f"\n## 教学叙事弧\n\n{narrative_plan}",
        f"\n## 目标语言\n\n{language}\n\n{_language_guidance(language)}",
        f"\n## 目标页数\n\n{slides_guidance}",
        f"\n## 详细程度\n\n{detail_level}\n\n{detail_text}",
    ]
    if provider_guidance:
        pass3_user_parts.append(f"\n{provider_guidance}")
    if is_deepseek:
        pass3_user_parts.append("\n" + deepseek_research_guidance(detail_level))
    pass3_user_parts.append(
        "\n\n请生成完整的幻灯片手稿。使用 `---` 分隔幻灯片。"
        "按照教学叙事弧计划编写。"
    )

    pass3_base_messages = [
        LLMMessage.system(pass3_system),
        LLMMessage.user("\n".join(pass3_user_parts)),
    ]

    manuscript = ""
    last_error = ""
    for attempt in range(1, MAX_MANUSCRIPT_ATTEMPTS + 1):
        pass3_messages = list(pass3_base_messages)
        if last_error:
            pass3_messages.append(
                LLMMessage.user(
                    f"Previous manuscript had structural issues: {last_error}. "
                    "Regenerate the complete manuscript fixing these issues."
                )
            )
        pass3_response = await llm.chat(
            pass3_messages, model,
            temperature=0.35 if attempt > 1 else 0.5,
            max_tokens=DEEPSEEK_MAX_TOKENS if is_deepseek else None,
        )
        manuscript = _normalize_manuscript_delimiters(pass3_response.content)
        _debug_write(debug_dir, f"research_pass3_attempt{attempt}.md", pass3_response.content)

        last_error = _manuscript_structure_error(manuscript, num_slides, detail_level) or ""
        if not last_error:
            # Check depth
            depth_feedback = _manuscript_depth_feedback(manuscript, detail_level)
            if not depth_feedback:
                break
            # Try depth rewrite
            rewrite_messages = list(pass3_base_messages)
            rewrite_messages.extend([
                LLMMessage.assistant(manuscript),
                LLMMessage.user(
                    f"Manuscript needs more depth: {depth_feedback}. "
                    "Rewrite with more detail while keeping the same structure."
                ),
            ])
            rewrite_response = await llm.chat(
                rewrite_messages, model, temperature=0.35,
                max_tokens=DEEPSEEK_MAX_TOKENS if is_deepseek else None,
            )
            revised = _normalize_manuscript_delimiters(rewrite_response.content)
            revised_error = _manuscript_structure_error(revised, num_slides, detail_level)
            if not revised_error:
                manuscript = revised
                break

    if last_error:
        logger.warning("Pass 3 manuscript structure invalid after retry: %s", last_error)
    logger.info("Research Pass 3 complete (%d chars)", len(manuscript))
    yield ResearchEvent("research_pass3", "completed", "Manuscript generated", 0.25)

    # ── Pass 4: Quality Self-Review ──────────────────────────────────────
    yield ResearchEvent("research_pass4", "started", "Pass 4: Quality review...", 0.25)

    pass4_system = PASS4_PROMPT.read_text(encoding="utf-8")
    pass4_user_parts = [
        f"## 待评审的手稿\n\n{manuscript}",
        f"\n## 原始深度分析\n\n{deep_analysis[:3000]}",
        f"\n## 叙事弧计划\n\n{narrative_plan[:2000]}",
        f"\n## 目标语言\n\n{language}",
        f"\n## 详细程度\n\n{detail_level}",
    ]
    pass4_user_parts.append(
        "\n\n请按照七个维度评估手稿。如果总分低于 28/35 或任何维度低于 3 分，"
        "请修订有问题的幻灯片并输出完整修订后的手稿。"
        "否则，输出 QUALITY_CHECK_PASSED 后跟未修改的手稿。"
    )

    pass4_messages = [
        LLMMessage.system(pass4_system),
        LLMMessage.user("\n".join(pass4_user_parts)),
    ]
    pass4_response = await llm.chat(
        pass4_messages, model, temperature=0.3,
        max_tokens=DEEPSEEK_MAX_TOKENS if is_deepseek else None,
    )
    _debug_write(debug_dir, "research_pass4_response.md", pass4_response.content)

    final_output = _normalize_manuscript_delimiters(
        _extract_manuscript_from_review(pass4_response.content, manuscript)
    )
    final_error = _manuscript_structure_error(final_output, num_slides, detail_level)
    manuscript_error = _manuscript_structure_error(manuscript, num_slides, detail_level)
    if final_error and not manuscript_error:
        logger.warning("Pass 4 changed structure; keeping Pass 3: %s", final_error)
        final_output = manuscript

    _debug_write(debug_dir, "research_final_manuscript.md", final_output)
    logger.info("Research Pass 4 complete. Final: %d chars", len(final_output))
    yield ResearchEvent("research_pass4", "completed", "Quality review complete", 0.28)

    # Return the final manuscript via a special event
    yield ResearchEvent("research_complete", "completed", final_output, 0.30, {"manuscript": final_output})
