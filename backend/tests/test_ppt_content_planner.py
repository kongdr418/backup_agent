from __future__ import annotations

import os
import sys


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ppt_engine.agents.content_planner import (  # noqa: E402
    _coerce_manuscript_page_count,
    _split_manuscript_pages,
)


def test_coerces_paragraph_manuscript_to_requested_slide_count():
    manuscript = "\n\n".join(
        [
            "第一页：导入中国地理主题。",
            "第二页：介绍学习路线。",
            "第三页：讲解地形地貌。",
            "第四页：讲解气候河流。",
            "第五页：讲解人口经济。",
            "第六页：总结关键知识。",
            "第七页：提问与结束。",
        ]
    )

    coerced = _coerce_manuscript_page_count(manuscript, 6)
    pages = _split_manuscript_pages(coerced)

    assert len(pages) == 6
    assert "第六页：总结关键知识。" in pages[-1]
    assert "第七页：提问与结束。" in pages[-1]
