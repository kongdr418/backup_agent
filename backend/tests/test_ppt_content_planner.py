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


def test_expands_under_count_paragraph_manuscript_to_requested_slide_count():
    manuscript = "\n\n".join(
        [
            "欢迎来到云计算第一课。今天我们先建立整体认识。",
            "本课程会从基本概念延伸到大数据技术。后续还会进入Linux和Docker实验。",
            "云计算是通过互联网按需提供计算资源的服务模式。它降低了硬件采购和维护成本。",
            "云计算具备按需自助和广泛网络访问。资源池化让服务商集中管理计算能力。",
            "快速弹性伸缩是云平台的重要特征。应用负载变化时，资源可以动态增减。",
            "IaaS提供虚拟机、存储和网络等基础能力。PaaS让开发者更专注代码部署。",
            "SaaS是面向最终用户的软件服务。在线邮箱和协作文档都是典型例子。",
            "公有云、私有云和混合云适合不同场景。选择模型要看安全、成本和弹性需求。",
            "今天的重点是理解云计算的概念地图。下一步我们会把概念放到实验中验证。",
        ]
    )

    coerced = _coerce_manuscript_page_count(manuscript, 10)
    pages = _split_manuscript_pages(coerced)

    assert len(pages) == 10
    assert all(page.strip() for page in pages)
    assert "云计算第一课" in pages[0]
