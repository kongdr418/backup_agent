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
