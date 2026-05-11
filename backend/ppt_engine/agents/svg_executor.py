"""SVG Executor agent: generates SVG page code from design spec.

Each page is checked by the static critic. If violations are found,
a targeted repair prompt is fed back to the LLM (bounded retries).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

from ppt_engine.config import REFERENCES_DIR, SVG_MAX_CONCURRENCY
from ppt_engine.critic import CriticConfig, CriticReport, check_svg
from ppt_engine.llm import LLMMessage, LLMProvider, LLMResponse

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "svg_executor.md"

MAX_REPAIR_ATTEMPTS = 2
MAX_SVG_EXTRACTION_ATTEMPTS = 2

_SLIDE_DELIMITER_RE = re.compile(r"(?m)^\s*---\s*$")

CriticCallback = Callable[[int, int, CriticReport], Awaitable[None]]


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


def _split_manuscript_pages(manuscript: str) -> list[str]:
    return [p.strip() for p in _SLIDE_DELIMITER_RE.split(manuscript) if p.strip()]


def _make_page_name(num: int, content: str) -> str:
    match = re.match(r"^##?\s+(.+)$", content, re.MULTILINE)
    if match:
        name = match.group(1).strip()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"\s+", "_", name)
        return name[:40].lower()
    return f"page_{num}"


def _extract_svg(text: str) -> str | None:
    match = re.search(r"```(?:svg|xml)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        svg = match.group(1).strip()
        if svg.startswith("<svg"):
            return svg
    match = re.search(r"(<svg[^>]*>.*?</svg>)", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _build_extraction_retry_prompt(
    *,
    page_num: int,
    total_pages: int,
    page_name: str,
    page_content: str,
    attempt: int,
) -> str:
    return (
        "## Generation Validation Report\n\n"
        f"The previous response for page {page_num}/{total_pages} ({page_name}) "
        "did not contain a parseable complete SVG document.\n\n"
        "## Failure\n"
        "- No complete `<svg ...>...</svg>` block could be extracted.\n\n"
        "## Regeneration Instructions\n"
        f"- Regenerate page {page_num}/{total_pages} only.\n"
        "- Return one complete SVG document, wrapped in a ```svg code block.\n"
        "- The SVG must start with `<svg` and end with `</svg>`.\n\n"
        f"## Page Content To Render\n\n{page_content}\n\n"
        f"## Retry Attempt\n\n{attempt}"
    )


def _deepseek_executor_guidance(detail_level: str) -> str:
    if detail_level != "very_high":
        return (
            "## DeepSeek Execution Calibration\n\n"
            "忠实渲染手稿内容。不要将内容折叠为几个通用标签。"
        )
    return (
        "## DeepSeek Execution Calibration\n\n"
        "对于 `very_high`，保留深度而不拥挤：\n"
        "- 每个实质性幻灯片应渲染手稿的核心机制、证据/数据和结论。\n"
        "- 避免纯标签式幻灯片和过多的胶囊标签。\n"
        "- 优先使用 3-5 个可读的内容块。\n"
        "- 保持所有文本在安全边距内，留有充足的内边距。"
    )


async def _generate_single_page(
    page_num: int,
    total_pages: int,
    page_content: str,
    design_spec: str,
    standards: str,
    style: str,
    language: str,
    detail_level: str,
    extra_block: str,
    llm: LLMProvider,
    model: str,
    svg_output_dir: Path,
    critic_config: CriticConfig | None,
    on_critic: CriticCallback | None,
) -> tuple[int, str]:
    """Generate one SVG page independently (no cross-page context)."""
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    page_name = _make_page_name(page_num, page_content)

    conversation: list[LLMMessage] = [
        LLMMessage.system(system_prompt),
        LLMMessage.user(
            f"## Design Specification\n\n{design_spec}\n\n"
            f"## SVG Technical Standards\n\n{standards}\n\n"
            f"## Fixed Runtime Configuration\n\n"
            f"- Selected style preset: {style}\n"
            f"- Selected language: {language}\n"
            f"- Selected detail level: {detail_level}\n"
            f"- Do not replace the requested style with another preset.\n"
            f"- All visible SVG text must follow the selected language unless a proper noun must stay in its original form.\n\n"
            f"## Page Content To Render\n\n"
            f"Page {page_num}/{total_pages}: {page_name}\n\n"
            f"{page_content}\n\n"
            f"Generate the complete SVG code for this page only. "
            f"Output ONLY the SVG code, wrapped in a ```svg code block."
            f"{extra_block}"
        ),
    ]

    response: LLMResponse = await llm.chat(
        conversation, model, temperature=0.3, max_tokens=16384
    )

    svg_content = _extract_svg(response.content)
    for extraction_attempt in range(2, MAX_SVG_EXTRACTION_ATTEMPTS + 1):
        if svg_content:
            break
        # Don't append the full failed response — use a short summary instead
        # to keep conversation context lean and reduce token processing time.
        conversation.append(LLMMessage.assistant("[SVG extraction failed]"))
        conversation.append(
            LLMMessage.user(
                _build_extraction_retry_prompt(
                    page_num=page_num,
                    total_pages=total_pages,
                    page_name=page_name,
                    page_content=page_content,
                    attempt=extraction_attempt,
                )
            )
        )
        response = await llm.chat(
            conversation, model, temperature=0.2, max_tokens=16384
        )
        svg_content = _extract_svg(response.content)

    if not svg_content:
        raise RuntimeError(
            f"Failed to generate parseable SVG for page {page_num}/{total_pages} "
            f"({page_name}) after {MAX_SVG_EXTRACTION_ATTEMPTS} attempts"
        )

    best_svg = svg_content
    for attempt in range(2, MAX_REPAIR_ATTEMPTS + 2):
        report = check_svg(svg_content, critic_config)
        if on_critic is not None:
            await on_critic(page_num, attempt - 1, report)

        if report.passed:
            best_svg = svg_content
            break

        # Build a clean repair conversation instead of accumulating history.
        # This keeps context focused and avoids token bloat from prior SVGs.
        repair_conversation = [
            conversation[0],  # system prompt
            conversation[1],  # original user prompt with design_spec
            LLMMessage.user(
                "The following SVG has violations that must be fixed.\n\n"
                f"```svg\n{svg_content}\n```\n\n"
                + report.to_prompt_block()
                + "\n\nReturn the complete corrected SVG only, "
                "wrapped in a ```svg code block."
            ),
        ]
        repair_temp = max(0.1, 0.3 - 0.1 * (attempt - 1))
        response = await llm.chat(
            repair_conversation, model, temperature=repair_temp, max_tokens=16384
        )

        repaired = _extract_svg(response.content)
        if repaired:
            svg_content = repaired
            best_svg = repaired
        else:
            break

    svg_path = svg_output_dir / f"{page_num:02d}_{page_name}.svg"
    svg_path.write_text(best_svg, encoding="utf-8")
    return page_num, best_svg


async def generate_svg_pages(
    design_spec: str,
    manuscript: str,
    project_dir: Path,
    llm: LLMProvider,
    model: str,
    *,
    style: str = "education",
    language: str = "zh",
    detail_level: str = "normal",
    extra_instruction: str = "",
    target_pages: set[int] | None = None,
    critic_config: CriticConfig | None = None,
    on_critic: CriticCallback | None = None,
) -> AsyncIterator[tuple[int, str]]:
    """Generate SVG code for each slide page concurrently.

    Yields (page_num, svg_content) tuples sorted by page number.
    """
    pages = _split_manuscript_pages(manuscript)
    svg_output_dir = project_dir / "svg_output"
    svg_output_dir.mkdir(parents=True, exist_ok=True)

    standards_path = REFERENCES_DIR / "shared-standards.md"
    standards = ""
    if standards_path.exists():
        standards = standards_path.read_text(encoding="utf-8")

    extra_sections = []
    if extra_instruction:
        extra_sections.append(extra_instruction)
    if _is_deepseek(llm, model):
        extra_sections.append(_deepseek_executor_guidance(detail_level))
    extra_block = "\n\n" + "\n\n".join(extra_sections) if extra_sections else ""

    # Build coroutine list
    coros = []
    for i, page_content in enumerate(pages):
        page_num = i + 1
        if target_pages is not None and page_num not in target_pages:
            continue
        coros.append(
            _generate_single_page(
                page_num=page_num,
                total_pages=len(pages),
                page_content=page_content,
                design_spec=design_spec,
                standards=standards,
                style=style,
                language=language,
                detail_level=detail_level,
                extra_block=extra_block,
                llm=llm,
                model=model,
                svg_output_dir=svg_output_dir,
                critic_config=critic_config,
                on_critic=on_critic,
            )
        )

    # Run with semaphore-controlled concurrency
    semaphore = asyncio.Semaphore(SVG_MAX_CONCURRENCY)

    async def _run_with_sem(coro):
        async with semaphore:
            return await coro

    # Execute concurrently; yield each page as soon as it completes
    tasks = [asyncio.create_task(_run_with_sem(c)) for c in coros]
    for task in asyncio.as_completed(tasks):
        page_num, svg_content = await task
        yield page_num, svg_content
