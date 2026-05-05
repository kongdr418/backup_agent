"""Strategist agent: produces a design specification from a manuscript."""

from __future__ import annotations

import re
from pathlib import Path

from ppt_engine.config import CANVAS_FORMATS, DESIGN_STYLES
from ppt_engine.llm import LLMMessage, LLMProvider, LLMResponse

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "design_strategist.md"
DESIGN_SPEC_MAX_TOKENS = 24576
MAX_DESIGN_SPEC_ATTEMPTS = 4

_SLIDE_DELIMITER_RE = re.compile(r"(?m)^\s*---\s*$")


def _count_manuscript_pages(manuscript: str) -> int:
    return len([p.strip() for p in _SLIDE_DELIMITER_RE.split(manuscript) if p.strip()])


def _is_deepseek(llm: LLMProvider, model: str) -> bool:
    model_id = (model or "").lower()
    if model_id.startswith("deepseek"):
        return True
    provider_name = str(getattr(llm, "_provider_name", "") or "").lower()
    if provider_name == "deepseek":
        return True
    base_url = str(getattr(llm, "_base_url", "") or "").lower()
    if "api.deepseek.com" in base_url:
        return True
    try:
        info = llm.get_provider_info()
        return getattr(info, "name", "").lower() == "deepseek"
    except Exception:
        return False


def _design_spec_validation_error(content: str) -> str | None:
    text = content.strip()
    if len(text) < 1200:
        return f"design_spec.md is too short ({len(text)} characters)"
    required = {
        "I": "Project Information",
        "II": "Canvas Specification",
        "III": "Visual Theme",
        "IX": "Content Outline",
        "XI": "Technical Constraints",
    }
    for roman, title in required.items():
        pattern = rf"(?im)^#+\s*{roman}\.\s+.*{re.escape(title)}"
        if not re.search(pattern, text):
            return f"design_spec.md is missing section {roman}. {title}"
    return None


def _language_constraint(language: str) -> str:
    normalized = language.strip().lower()
    if normalized == "zh":
        return "所有幻灯片标题、标签、要点和注释必须使用简体中文（专有名词除外）。"
    if normalized == "en":
        return "All slide titles, labels, bullets, and annotations must be in English."
    if normalized == "bilingual":
        return "Page titles and core bullets may include both Chinese and English."
    return f"All visible slide text must be in {language}."


def _deepseek_strategy_guidance(detail_level: str) -> str:
    if detail_level != "very_high":
        return (
            "## DeepSeek Calibration\n\n"
            "将手稿内容转化为具体的布局计划。不要将丰富的幻灯片简化为装饰性标签。"
        )
    return (
        "## DeepSeek Calibration\n\n"
        "对于 `very_high` 详细程度，设计规范必须保留手稿的分析深度：\n"
        "- 在第九节中，每个非封面页必须列出要渲染的具体内容块。\n"
        "- 保留手稿中的原理、证据/数据和结论。\n"
        "- 避免纯标签式幻灯片，使用标签仅作为有意义的分类。\n"
        "- 优先使用 3-5 个可读的内容块，而不是许多小碎片。"
    )


async def create_design_spec(
    manuscript: str,
    llm: LLMProvider,
    model: str,
    *,
    canvas_format: str = "ppt169",
    style: str = "education",
    language: str = "zh",
    detail_level: str = "normal",
    style_overrides: dict | None = None,
) -> str:
    """Generate a design specification from a manuscript.

    Returns:
        Design specification markdown (design_spec.md content).
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    fmt = CANVAS_FORMATS.get(canvas_format, CANVAS_FORMATS["ppt169"])
    style_info = DESIGN_STYLES.get(style, DESIGN_STYLES["education"])
    page_count = _count_manuscript_pages(manuscript)

    user_parts = [
        f"## Manuscript\n\n{manuscript}",
        f"\n## Canvas Format: {fmt['name']} ({fmt['ratio']}), viewBox: `{fmt['viewbox']}`",
        f"\n## Design Style: {style_info['name']}",
        f"\n## Page Count: {page_count}",
        f"\n## Language: {language}",
        f"\n## Detail Level: {detail_level}",
        f"\n## Pre-resolved Confirmations",
        f"- Canvas Format: {fmt['name']}",
        f"- Page Count: {page_count}",
        f"- Audience: Students / Learners",
        f"- Style: {style_info['name']}",
        f"- Primary Color: {style_info['primary']}",
        f"- Accent Color: {style_info['accent']}",
        "- Typography: Sans-serif (Inter/Arial for body, bold for headings)",
        "\n## Hard Constraints",
        "- Respect the selected design style.",
        f"- The visible slide language must be `{language}`.",
        f"- {_language_constraint(language)}",
    ]

    if _is_deepseek(llm, model):
        user_parts.append("\n" + _deepseek_strategy_guidance(detail_level))

    if style_overrides:
        override_lines = ["\n## Style Overrides (must override defaults)"]
        palette = style_overrides.get("palette") if isinstance(style_overrides, dict) else None
        font = style_overrides.get("font") if isinstance(style_overrides, dict) else None
        density = style_overrides.get("density") if isinstance(style_overrides, dict) else None
        if palette:
            try:
                colors = ", ".join(str(c) for c in palette if c)
            except TypeError:
                colors = ""
            if colors:
                override_lines.append(f"- Palette: {colors}")
        if font:
            override_lines.append(f"- Font-family: `{font}`")
        if density:
            override_lines.append(f"- Layout density: `{density}`")
        user_parts.append("\n".join(override_lines))

    user_parts.append(
        "\n\nGenerate the complete design_spec.md following the template structure. "
        "All 11 sections (I through XI) must be present."
    )

    base_messages = [
        LLMMessage.system(system_prompt),
        LLMMessage.user("\n".join(user_parts)),
    ]

    last_error = ""
    for attempt in range(1, MAX_DESIGN_SPEC_ATTEMPTS + 1):
        messages = list(base_messages)
        if last_error:
            messages.append(
                LLMMessage.user(
                    f"The previous design_spec.md response was invalid: {last_error}. "
                    "Regenerate the complete design_spec.md now."
                )
            )

        response: LLMResponse = await llm.chat(
            messages,
            model,
            temperature=0.25 if attempt > 1 else 0.4,
            max_tokens=DESIGN_SPEC_MAX_TOKENS,
        )
        content = response.content.strip()
        error = _design_spec_validation_error(content)
        if error is None:
            return content
        last_error = error

    raise RuntimeError(f"Invalid design specification from strategist: {last_error}")
