from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ppt_engine.agents.svg_executor import (  # noqa: E402
    _select_retry_template_key,
    generate_svg_pages,
)
from ppt_engine.llm.base import LLMProvider  # noqa: E402
from ppt_engine.llm.types import LLMMessage, LLMResponse, ModelInfo, ProviderInfo  # noqa: E402


class FakeRepairLLM(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format=None,
    ) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="""
                ```svg
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
                  <foreignObject x="100" y="100" width="120" height="80"></foreignObject>
                  <text x="160" y="180" font-size="24" fill="#0f172a">bad svg</text>
                </svg>
                ```
                """,
                usage=None,
                raw=None,
            )
        return LLMResponse(
            content="""
            ```svg
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
              <text x="160" y="180" font-size="24" fill="#0f172a">fixed svg</text>
            </svg>
            ```
            """,
            usage=None,
            raw=None,
        )

    async def chat_stream(self, messages, model, *, temperature=0.7, max_tokens=None):
        raise NotImplementedError

    async def validate(self) -> bool:
        return True

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(name="fake", display_name="Fake", models=[])


class FakeExtractionRetryLLM(LLMProvider):
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format=None,
    ) -> LLMResponse:
        self.calls.append(messages)
        if len(self.calls) == 1:
            return LLMResponse(
                content="I will explain the slide, but I forgot to return SVG.",
                usage=None,
                raw=None,
            )
        return LLMResponse(
            content="""
            ```svg
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
              <text x="120" y="160" font-size="28" fill="#0f172a">retry svg</text>
            </svg>
            ```
            """,
            usage=None,
            raw=None,
        )

    async def chat_stream(self, messages, model, *, temperature=0.7, max_tokens=None):
        raise NotImplementedError

    async def validate(self) -> bool:
        return True

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(name="fake", display_name="Fake", models=[])


def _run_svg_generation(tmp_path: Path, *, repair_enabled: bool | None) -> tuple[FakeRepairLLM, str]:
    llm = FakeRepairLLM()

    async def run() -> str:
        pages = []
        kwargs = {}
        if repair_enabled is not None:
            kwargs["repair_enabled"] = repair_enabled
        async for _page_num, svg in generate_svg_pages(
            "design spec",
            "one page",
            tmp_path,
            llm,
            "fake-model",
            **kwargs,
        ):
            pages.append(svg)
        return pages[0]

    return llm, asyncio.run(run())


def test_svg_repair_disabled_skips_repair_llm_call(tmp_path: Path):
    llm, svg = _run_svg_generation(tmp_path, repair_enabled=False)

    assert llm.calls == 1
    assert "<foreignObject" in svg


def test_svg_repair_defaults_to_disabled(tmp_path: Path):
    llm, svg = _run_svg_generation(tmp_path, repair_enabled=None)

    assert llm.calls == 1
    assert "<foreignObject" in svg


def test_svg_repair_enabled_keeps_repairing_blocking_errors(tmp_path: Path):
    llm, svg = _run_svg_generation(tmp_path, repair_enabled=True)

    assert llm.calls == 2
    assert "fixed svg" in svg


def test_extraction_retry_uses_compact_context_without_full_template_refs(tmp_path: Path):
    llm = FakeExtractionRetryLLM()
    content_template = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
        '<rect width="1280" height="720" fill="#f8fafc"/>'
        '<text x="80" y="80">CONTENT_STYLE_ANCHOR</text>'
        + ("<g><text>template filler</text></g>" * 300)
        + "</svg>"
    )

    async def run() -> str:
        pages = []
        async for _page_num, svg in generate_svg_pages(
            "DESIGN_DETAIL " * 1000,
            "page content about inheritance and polymorphism",
            tmp_path,
            llm,
            "fake-model",
            template_svgs={"content": content_template},
            template_context="Anthropic style with restrained orange accents.",
        ):
            pages.append(svg)
        return pages[0]

    svg = asyncio.run(run())

    assert "retry svg" in svg
    assert len(llm.calls) == 2
    retry_text = "\n".join(message.content for message in llm.calls[1])
    assert "CONTENT_STYLE_ANCHOR" in retry_text
    assert "Reference Layout Templates" not in retry_text
    assert len(retry_text) < 8000


def test_extraction_retry_selects_content_template_for_middle_pages():
    template_svgs = {
        "cover": "<svg>cover</svg>",
        "content": "<svg>content</svg>",
        "ending": "<svg>ending</svg>",
    }

    selected = _select_retry_template_key(
        page_num=3,
        total_pages=11,
        page_content="类与对象的核心概念",
        template_svgs=template_svgs,
    )

    assert selected == "content"
