from __future__ import annotations

import os
import sys


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ppt_engine.critic import check_svg  # noqa: E402


def test_card_text_overflow_repair_prompt_is_actionable():
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
      <rect x="100" y="120" width="260" height="180" rx="10" fill="#ffffff" stroke="#d9e2ec"/>
      <text x="124" y="190" font-size="18" fill="#0f172a">这是一段非常长的卡片正文没有换行会直接冲出右侧边界</text>
    </svg>
    """

    report = check_svg(svg)
    overflow = [v for v in report.violations if v.rule == "text_overflow_in_container"]

    assert overflow
    prompt = report.to_prompt_block()
    assert "hard failure for card layouts" in prompt
    assert "multiple shorter <text> lines" in prompt


def test_card_bottom_badge_outside_container_is_reported():
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
      <rect x="100" y="140" width="460" height="480" rx="10" fill="#ffffff" stroke="#d9e2ec"/>
      <rect x="128" y="646" width="120" height="28" rx="14" fill="#e8f2ff"/>
      <text x="154" y="665" font-size="14" fill="#0f172a">PROTECTED</text>
    </svg>
    """

    report = check_svg(svg)
    rules = {v.rule for v in report.violations}

    assert "container_content_outside" in rules


def test_visual_layout_suggestions_do_not_block_repair_by_default():
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
      <rect x="100" y="140" width="460" height="480" rx="10" fill="#ffffff" stroke="#d9e2ec"/>
      <rect x="128" y="646" width="120" height="28" rx="14" fill="#e8f2ff"/>
      <text x="154" y="665" font-size="14" fill="#0f172a">PROTECTED</text>
    </svg>
    """

    report = check_svg(svg)
    rules = {v.rule for v in report.violations}

    assert "container_content_outside" in rules
    assert report.passed


def test_export_risk_violations_still_block_repair():
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
      <foreignObject x="100" y="100" width="200" height="100"></foreignObject>
    </svg>
    """

    report = check_svg(svg)
    rules = {v.rule for v in report.violations}

    assert "forbidden_element" in rules
    assert not report.passed


def test_decorative_cover_nodes_are_not_empty_bullets():
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
      <rect width="1280" height="720" fill="#1A1A2E"/>
      <g stroke="#4A90D9" stroke-opacity="0.4" stroke-width="1" fill="none">
        <path d="M100,200 Q250,150 350,220"/>
        <path d="M350,220 Q450,280 500,200"/>
      </g>
      <g fill="#4A90D9" fill-opacity="0.6">
        <circle cx="100" cy="200" r="4"/>
        <circle cx="350" cy="220" r="6"/>
        <circle cx="500" cy="200" r="4"/>
      </g>
      <text x="640" y="280" font-size="56" fill="#FFFFFF" text-anchor="middle">机器学习基础</text>
    </svg>
    """

    report = check_svg(svg)
    rules = {v.rule for v in report.violations}

    assert "empty_bullet" not in rules


def test_real_empty_bullet_is_still_reported():
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
      <rect width="1280" height="720" fill="#ffffff"/>
      <circle cx="90" cy="200" r="5" fill="#D97757"/>
      <text x="130" y="260" font-size="18" fill="#0f172a">下一行文字不属于这个项目符号</text>
    </svg>
    """

    report = check_svg(svg)
    rules = {v.rule for v in report.violations}

    assert "empty_bullet" in rules
    assert not report.passed


def test_card_content_inside_container_passes_overflow_checks():
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
      <rect x="100" y="140" width="460" height="480" rx="10" fill="#ffffff" stroke="#d9e2ec"/>
      <text x="128" y="210" font-size="22" fill="#0f172a">元组定义与特性</text>
      <text x="128" y="250" font-size="16" fill="#64748b">不可变序列类型</text>
      <rect x="128" y="570" width="120" height="28" rx="14" fill="#e8f2ff"/>
      <text x="154" y="589" font-size="14" fill="#0f172a">IMMUTABLE</text>
    </svg>
    """

    report = check_svg(svg)
    rules = {v.rule for v in report.violations}

    assert "text_overflow_in_container" not in rules
    assert "container_content_outside" not in rules
