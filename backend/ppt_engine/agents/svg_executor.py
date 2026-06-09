"""SVG Executor agent: generates SVG page code from design spec.

Each page is checked by the static critic. If violations are found,
a targeted repair prompt is fed back to the LLM (bounded retries).
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

from ppt_engine.config import REFERENCES_DIR, SVG_MAX_CONCURRENCY
from ppt_engine.critic import CriticConfig, CriticReport, check_svg
from ppt_engine.llm import LLMMessage, LLMProvider, LLMResponse
from ppt_engine.agents.provider_guidance import is_deepseek_provider, deepseek_executor_guidance
from ppt_engine.logger import get_logger

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "svg_executor.md"
logger = get_logger(__name__)

MAX_REPAIR_ATTEMPTS = 2
MAX_SVG_EXTRACTION_ATTEMPTS = 2

_SLIDE_DELIMITER_RE = re.compile(r"(?m)^\s*---\s*$")

CriticCallback = Callable[[int, int, CriticReport], Awaitable[None]]




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
    repair_enabled: bool,
    template_svgs: dict[str, str] | None = None,
    template_context: str | None = None,
) -> tuple[int, str]:
    """Generate one SVG page independently (no cross-page context)."""
    page_start = time.monotonic()
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    page_name = _make_page_name(page_num, page_content)
    logger.info(
        "[PPT-PERF] stage=svg_generation page=%s/%s status=started name=%s",
        page_num,
        total_pages,
        page_name,
    )

    # Build template reference block if template SVGs are available
    template_ref_block = ""
    if template_svgs:
        ref_parts = ["\n\n## Reference Layout Templates\n\n"]
        ref_parts.append(
            "The following SVG templates define the visual language you MUST follow. "
            "Match their color palette, typography style, spacing patterns, "
            "decorative elements, and overall aesthetic. Adapt the content to the "
            "page you are generating while preserving the design DNA.\n\n"
        )
        for page_type, svg_text in template_svgs.items():
            truncated = svg_text[:4000]
            if len(svg_text) > 4000:
                truncated += "\n<!-- ... truncated for brevity ... -->"
            ref_parts.append(f"### Template: {page_type}\n```svg\n{truncated}\n```\n\n")
        template_ref_block = "".join(ref_parts)

    template_ctx_block = ""
    if template_context:
        template_ctx_block = f"\n\n## Template Design Context\n\n{template_context}\n"

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
            f"{template_ctx_block}"
            f"{template_ref_block}"
            f"{extra_block}"
        ),
    ]

    llm_start = time.monotonic()
    response: LLMResponse = await llm.chat(
        conversation, model, temperature=0.3, max_tokens=16384
    )
    logger.info(
        "[PPT-PERF] stage=svg_generation page=%s/%s step=initial_llm elapsed=%.2fs chars=%s",
        page_num,
        total_pages,
        time.monotonic() - llm_start,
        len(response.content),
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
        llm_start = time.monotonic()
        response = await llm.chat(
            conversation, model, temperature=0.2, max_tokens=16384
        )
        logger.info(
            "[PPT-PERF] stage=svg_generation page=%s/%s step=extraction_retry attempt=%s elapsed=%.2fs chars=%s",
            page_num,
            total_pages,
            extraction_attempt,
            time.monotonic() - llm_start,
            len(response.content),
        )
        svg_content = _extract_svg(response.content)

    if not svg_content:
        raise RuntimeError(
            f"Failed to generate parseable SVG for page {page_num}/{total_pages} "
            f"({page_name}) after {MAX_SVG_EXTRACTION_ATTEMPTS} attempts"
        )

    best_svg = svg_content
    for attempt in range(2, MAX_REPAIR_ATTEMPTS + 2):
        critic_start = time.monotonic()
        report = check_svg(svg_content, critic_config)
        logger.info(
            "[PPT-PERF] stage=svg_generation page=%s/%s step=critic attempt=%s elapsed=%.2fs passed=%s errors=%s warnings=%s",
            page_num,
            total_pages,
            attempt - 1,
            time.monotonic() - critic_start,
            report.passed,
            report.error_count,
            report.warning_count,
        )
        if on_critic is not None:
            await on_critic(page_num, attempt - 1, report)

        if report.passed:
            best_svg = svg_content
            break
        if not repair_enabled:
            logger.info(
                "[PPT-PERF] stage=svg_generation page=%s/%s step=repair_llm skipped=true reason=disabled",
                page_num,
                total_pages,
            )
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
        repair_start = time.monotonic()
        response = await llm.chat(
            repair_conversation, model, temperature=repair_temp, max_tokens=16384
        )
        logger.info(
            "[PPT-PERF] stage=svg_generation page=%s/%s step=repair_llm attempt=%s elapsed=%.2fs chars=%s",
            page_num,
            total_pages,
            attempt - 1,
            time.monotonic() - repair_start,
            len(response.content),
        )

        repaired = _extract_svg(response.content)
        if repaired:
            svg_content = repaired
            best_svg = repaired
        else:
            break

    svg_path = svg_output_dir / f"{page_num:02d}_{page_name}.svg"
    svg_path.write_text(best_svg, encoding="utf-8")
    logger.info(
        "[PPT-PERF] stage=svg_generation page=%s/%s status=complete elapsed=%.2fs path=%s",
        page_num,
        total_pages,
        time.monotonic() - page_start,
        svg_path,
    )
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
    repair_enabled: bool = False,
    template_svgs: dict[str, str] | None = None,
    template_context: str | None = None,
) -> AsyncIterator[tuple[int, str]]:
    """Generate SVG code for each slide page concurrently.

    Yields (page_num, svg_content) tuples sorted by page number.
    """
    pages = _split_manuscript_pages(manuscript)
    svg_output_dir = project_dir / "svg_output"
    svg_output_dir.mkdir(parents=True, exist_ok=True)
    dispatched_page_count = (
        len(pages)
        if target_pages is None
        else sum(1 for i, _page in enumerate(pages, start=1) if i in target_pages)
    )
    logger.info(
        "[PPT-PERF] stage=svg_generation status=dispatch pages=%s concurrency=%s",
        dispatched_page_count,
        SVG_MAX_CONCURRENCY,
    )

    standards_path = REFERENCES_DIR / "shared-standards.md"
    standards = ""
    if standards_path.exists():
        standards = standards_path.read_text(encoding="utf-8")

    extra_sections = []
    if extra_instruction:
        extra_sections.append(extra_instruction)
    if is_deepseek_provider(llm, model):
        extra_sections.append(deepseek_executor_guidance(detail_level))
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
                repair_enabled=repair_enabled,
                template_svgs=template_svgs,
                template_context=template_context,
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
