"""Content Planner agent: generates slide manuscript from a course topic."""

from __future__ import annotations

from pathlib import Path

from ppt_engine.llm import LLMMessage, LLMProvider, LLMResponse
from ppt_engine.agents.provider_guidance import is_deepseek_provider, deepseek_research_guidance

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "content_planner.md"
MAX_TOKENS = 24576


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


async def plan_content(
    topic: str,
    llm: LLMProvider,
    model: str,
    *,
    instruction: str = "",
    num_slides: int | None = None,
    language: str = "zh",
    detail_level: str = "normal",
) -> str:
    """Generate a slide manuscript from a course topic.

    Args:
        topic: Course topic or title.
        llm: LLM provider instance.
        model: Model ID to use.
        instruction: Optional user instruction for customization.
        num_slides: Target number of slides (None = auto, typically 10-12).
        language: Target language for slide text.
        detail_level: Controls content depth (normal/high/very_high).

    Returns:
        Manuscript markdown with --- page separators.
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    detail_guidance = {
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

    user_parts = [f"## 课程主题\n\n{topic}"]

    if instruction:
        user_parts.append(f"\n## 额外要求\n\n{instruction}")

    if num_slides:
        user_parts.append(
            f"\n## 目标页数\n\n"
            f"生成恰好 {num_slides} 页幻灯片。使用 {num_slides - 1} 个 `---` 分隔符。"
        )
    else:
        user_parts.append(
            "\n## 目标页数\n\n"
            "根据内容自动确定（通常 10-12 页）。"
        )

    user_parts.append(f"\n## 语言\n\n{language}\n\n{_language_guidance(language)}")
    user_parts.append(
        f"\n## 详细程度\n\n{detail_level}\n\n"
        f"{detail_guidance.get(detail_level, detail_guidance['normal'])}"
    )

    if is_deepseek_provider(llm, model):
        user_parts.append("\n" + deepseek_research_guidance(detail_level))

    user_parts.append(
        "\n\n请根据以上主题生成幻灯片手稿。"
        "每页用独立的 `---` 行分隔。现在开始。"
    )

    messages = [
        LLMMessage.system(system_prompt),
        LLMMessage.user("\n".join(user_parts)),
    ]

    response: LLMResponse = await llm.chat(
        messages,
        model,
        temperature=0.5,
        max_tokens=MAX_TOKENS,
    )
    return response.content
