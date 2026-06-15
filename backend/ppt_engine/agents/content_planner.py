"""Content Planner agent: generates slide manuscript from a course topic."""

from __future__ import annotations

import re
from pathlib import Path

from ppt_engine.llm import LLMMessage, LLMProvider, LLMResponse
from ppt_engine.agents.provider_guidance import is_deepseek_provider, deepseek_research_guidance

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "content_planner.md"
MAX_TOKENS = 49152  # 翻倍：reasoning 模型（如 mimo-v2.5）需要 reasoning + 输出双预算
_SLIDE_DELIMITER_RE = re.compile(r"(?m)^\s*---\s*$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])\s*")


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


def _split_manuscript_pages(manuscript: str) -> list[str]:
    return [p.strip() for p in _SLIDE_DELIMITER_RE.split(manuscript or "") if p.strip()]


def _split_paragraph_pages(manuscript: str) -> list[str]:
    normalized = (manuscript or "").replace("\r\n", "\n").strip()
    if not normalized:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", normalized) if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs
    return [normalized]


def _coerce_page_list_to_count(pages: list[str], num_slides: int) -> list[str]:
    if num_slides <= 0 or not pages:
        return pages
    if len(pages) == num_slides:
        return pages
    if len(pages) > num_slides:
        head = pages[: num_slides - 1]
        tail = "\n\n".join(pages[num_slides - 1 :]).strip()
        return [*head, tail] if head else [tail]

    expanded = [page.strip() for page in pages if page.strip()]
    while len(expanded) < num_slides:
        split_index = _find_splittable_page_index(expanded)
        if split_index < 0:
            break
        first, second = _split_page_content(expanded[split_index])
        expanded[split_index:split_index + 1] = [first, second]
    return expanded


def _find_splittable_page_index(pages: list[str]) -> int:
    candidates: list[tuple[int, int]] = []
    for idx, page in enumerate(pages):
        sentences = _split_sentences(page)
        if len(sentences) >= 2:
            candidates.append((len(page), idx))
    if not candidates:
        return -1
    return max(candidates)[1]


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text or "") if part.strip()]


def _split_page_content(text: str) -> tuple[str, str]:
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return text, text
    midpoint = max(1, len(sentences) // 2)
    first = "".join(sentences[:midpoint]).strip()
    second = "".join(sentences[midpoint:]).strip()
    return first or text, second or text


def _coerce_manuscript_page_count(manuscript: str, num_slides: int | None) -> str:
    if not num_slides:
        return manuscript

    pages = _split_manuscript_pages(manuscript)
    if len(pages) == num_slides:
        return "\n\n---\n\n".join(pages)

    paragraph_pages = _split_paragraph_pages(manuscript)
    if len(pages) <= 1 and len(paragraph_pages) > 1:
        pages = paragraph_pages

    coerced_pages = _coerce_page_list_to_count(pages, num_slides)
    if len(coerced_pages) == num_slides:
        return "\n\n---\n\n".join(coerced_pages)

    return manuscript


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

    if instruction and instruction.strip():
        user_parts.append(
            f"## 额外要求\n\n{instruction.strip()}\n\n"
            "（请在不违背课程主题和已有参数（页数 / 语言 / 风格 / 详细程度）的前提下，"
            "尽量满足上述额外要求）"
        )

    if num_slides:
        user_parts.append(
            f"\n## 严格页数要求（必须遵守）\n\n"
            f"你必须生成恰好 {num_slides} 页幻灯片，不能多也不能少。"
            f"使用 {num_slides - 1} 个 `---` 分隔符将每页分开。"
            f"\n\n这是硬性要求。如果生成的页数不是 {num_slides} 页，整个输出将被视为无效。"
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
    return _coerce_manuscript_page_count(response.content, num_slides)
