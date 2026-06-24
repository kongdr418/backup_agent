from __future__ import annotations

import asyncio
import os
import re
import json
from datetime import datetime
from difflib import SequenceMatcher
from html import unescape
from typing import Any, Callable
from uuid import uuid4

from .critic_service import (
    ClassroomCriticService,
    CriticResult,
    build_grounding_context,
    normalize_critic_mode,
)
from .schema import ClassroomAction, ClassroomScene, InteractiveClassroom
from .storage import ClassroomStorage
from .tts_service import (
    DEFAULT_TTS_MAX_CONCURRENCY,
    ClassroomTTSService,
    synthesize_actions_parallel_with_progress,
)

from .generation_progress import (
    CancelCheck,
    DEFAULT_ANIMATION_LAB_MAX_TOKENS,
    _raise_if_cancelled,
)
from .scene_content import (
    _clean_text,
    _is_quiz_source_scene,
    _normalize_student_profile,
    _student_profile_hint,
)

def _repair_animation_js_line_comments(script: str) -> str:
    if "//" not in script:
        return script
    boundary = (
        r"(?=(?:function\s+|const\s+|let\s+|var\s+|if\s*\(|else\b|for\s*\(|"
        r"while\s*\(|return\b|document\.|ctx\.|canvas\.|requestAnimationFrame\s*\(|"
        r"[A-Za-z_$][\w$]*\s*=|//))"
    )

    def repl(match: re.Match) -> str:
        comment = (match.group(1) or "").strip()
        return f"/* {comment} */" if comment else ""

    return re.sub(r"//\s*([^/\n\r]*?)\s*" + boundary, repl, script)

ANIMATION_LAB_EMBED_STYLE = """

<style id="ai-creator-animation-lab-embed">
html,
body {
  width: 100% !important;
  min-height: 100% !important;
  margin: 0 !important;
  overflow: hidden !important;
  background: #ffffff !important;
}
body {
  box-sizing: border-box !important;
  padding: 10px !important;
  color: #0f172a !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}
h1,
h2 {
  margin: 0 0 8px !important;
  color: #2D5016 !important;
  font-size: clamp(18px, 2.3vw, 24px) !important;
  line-height: 1.25 !important;
  text-align: center !important;
}
body > h1:first-child,
body > h2:first-child {
  display: none !important;
}
.container,
main,
.app,
#app {
  width: 100% !important;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
  box-sizing: border-box !important;
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}
canvas,
svg {
  display: block !important;
  width: 100% !important;
  max-width: min(100%, calc(166.67vh - 226px)) !important;
  height: auto !important;
  max-height: calc(100vh - 136px) !important;
  margin: 0 auto !important;
}
.controls,
form {
  margin-top: 8px !important;
  display: flex !important;
  flex-wrap: wrap !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 8px 12px !important;
}
label,
.info,
p {
  margin-block: 4px !important;
  line-height: 1.38 !important;
}
input[type="range"] {
  width: min(520px, 58vw) !important;
}
button {
  min-height: 32px !important;
}
</style>
"""

def _inject_animation_embed_style(html: str) -> str:
    text = str(html or "")
    if "ai-creator-animation-lab-embed" in text:
        return text
    if "</head>" in text.lower():
        return re.sub(
            r"</head>",
            f"{ANIMATION_LAB_EMBED_STYLE}</head>",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    return f"{ANIMATION_LAB_EMBED_STYLE}{text}"

def _upgrade_animation_canvas_resolution(html: str) -> str:
    text = str(html or "")

    def repl(match: re.Match) -> str:
        tag = match.group(0)

        def read_attr(name: str) -> int | None:
            found = re.search(rf'\b{name}\s*=\s*["\']?(\d+)', tag, flags=re.IGNORECASE)
            return int(found.group(1)) if found else None

        width = read_attr("width")
        height = read_attr("height")
        target_w = max(width or 0, 1200)
        target_h = max(height or 0, 720)
        if width and height and width >= 1000 and height >= 620:
            return tag
        if width:
            tag = re.sub(r'\bwidth\s*=\s*["\']?\d+["\']?', f'width="{target_w}"', tag, flags=re.IGNORECASE)
        else:
            tag = tag[:-1] + f' width="{target_w}">'
        if height:
            tag = re.sub(r'\bheight\s*=\s*["\']?\d+["\']?', f'height="{target_h}"', tag, flags=re.IGNORECASE)
        else:
            tag = tag[:-1] + f' height="{target_h}">'
        return tag

    text = re.sub(r"<canvas\b[^>]*>", repl, text, count=3, flags=re.IGNORECASE)
    responsive_rule = (
        "\ncanvas { max-width: 100% !important; height: auto !important; "
        "image-rendering: auto; }\n"
    )
    if "</style>" in text.lower():
        text = re.sub(r"</style>", responsive_rule + "</style>", text, count=1, flags=re.IGNORECASE)
    else:
        text = re.sub(
            r"</head>",
            f"<style>{responsive_rule}</style></head>",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    return text

def _repair_animation_html_for_display(html: str) -> str:
    text = _upgrade_animation_canvas_resolution(str(html or ""))
    text = _inject_animation_embed_style(text)

    def repair_script(match: re.Match) -> str:
        open_tag, script, close_tag = match.group(1), match.group(2), match.group(3)
        return f"{open_tag}{_repair_animation_js_line_comments(script)}{close_tag}"

    return re.sub(
        r"(<script\b[^>]*>)(.*?)(</script>)",
        repair_script,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

def _sanitize_animation_lab_html(html: str) -> str:
    text = str(html or "").strip()
    text = re.sub(r"^```(?:html)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = _repair_animation_html_for_display(text)
    lowered = text.lower()
    if not lowered.lstrip().startswith("<!doctype html") and "<html" not in lowered:
        return ""
    blocked = [
        "<script src=",
        "<iframe",
        "<object",
        "<embed",
        "http://",
        "https://",
        "fetch(",
        "xmlhttprequest",
        "localstorage",
        "sessionstorage",
        "document.cookie",
        "navigator.sendbeacon",
        "websocket",
    ]
    if any(token in lowered for token in blocked):
        return ""
    if len(re.findall(r"<!doctype html", lowered)) > 1 or len(re.findall(r"<html", lowered)) > 1:
        return ""
    if "</html>" not in lowered:
        return ""
    if "<canvas" not in lowered and "<svg" not in lowered:
        return ""
    if "<button" not in lowered and 'type="range"' not in lowered and "type='range'" not in lowered:
        return ""
    return text[:120000]

class EnrichmentSceneBuilderMixin:
    def _build_mindmap_prompt(
        self,
        topic: str,
        slide_summaries: list[dict[str, Any]],
        student_profile: dict[str, str] | None = None,
    ) -> str:
        """为 mindmap 场景生成 LLM prompt。

        关键点：传讲稿正文（speech_excerpt），让 LLM 从语义归纳概念，
        而不是只把 slide 标题换皮。
        """
        lines = [
            f"请基于下面的课堂讲稿内容，为《{topic}》整理出一份**真正的知识结构图**（markmap 风格 Markdown）。",
            "",
            "## 课堂页面（含讲稿摘录）",
        ]
        for idx, slide in enumerate(slide_summaries, start=1):
            title = str(slide.get("title") or "").strip() or f"第 {idx} 页"
            points = [
                str(p).strip() for p in (slide.get("knowledge_points") or []) if str(p).strip()
            ][:6]
            excerpt = str(slide.get("speech_excerpt") or "").strip()
            lines.append(f"\n### 第 {idx} 页：{title}")
            if points:
                lines.append(f"- 关键点：{'；'.join(points)}")
            if excerpt:
                lines.append(f"- 讲稿：{excerpt}")

        profile_hint = _student_profile_hint(_normalize_student_profile(student_profile))
        if profile_hint:
            lines.append(f"\n## 学生画像\n{profile_hint}\n")

        lines.extend(
            [
                "\n## 输出要求（务必遵循）",
                "1. **从讲稿里归纳真正的概念**，不要简单把页面标题当成分支名",
                "2. 根节点 = 课堂主题（一级标题 #）",
                "3. 一级分支 3-6 个，**按主题分类**（不是按页面顺序）",
                "4. 二级分支 2-5 个，挂在最合适的一级下；最多两级",
                "5. 每个节点 2-8 字，简洁直白",
                "6. **只返回 Markdown 本身**，不要用 ``` 包裹，不要任何解释、前言、后语",
                "7. 实在归纳不出时，输出：根节点 + 一级分支 = 主要概念（≤5 个），二级分支 = 讲到的关键名词",
            ]
        )
        return "\n".join(lines)

    def _build_fallback_markmap_md(
        self,
        topic: str,
        slide_summaries: list[dict[str, Any]],
    ) -> str:
        """LLM 失败时的兜底：根节点 + 每页标题作一级分支。"""
        lines = [f"# {topic}"]
        for idx, slide in enumerate(slide_summaries, start=1):
            title = str(slide.get("title") or "").strip() or f"第 {idx} 页"
            lines.append(f"- {title}")
        return "\n".join(lines)

    def _call_content_llm_markmap(self, prompt: str) -> str:
        """走 content LLM 通道（与 quiz 共享），不依赖外部资源。"""
        from generators.shared_config import content_llm_call

        return content_llm_call(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一位知识结构整理专家，擅长把课堂内容组织成层级清晰、"
                        "用词简洁的思维导图。只输出 Markdown 大纲本身。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )

    def _build_mindmap_scene(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> ClassroomScene | None:
        """构造一个 mindmap 场景。

        输入是已经排好的 [slide scenes] + [quiz scenes] 列表。
        从 slide scenes 抽 title + knowledge_points，让 LLM 重组为 markmap markdown。
        LLM 失败时回退到 flat fallback（根节点 + 每页标题）。
        """
        _raise_if_cancelled(cancel_check)

        slide_scenes = [s for s in scenes if s.type == "slide"]
        if not slide_scenes:
            return None

        slide_summaries = self._build_slide_summaries(slide_scenes)
        markmap_md = ""
        try:
            prompt = self._build_mindmap_prompt(topic, slide_summaries, student_profile)
            raw = self._call_content_llm_markmap(prompt)
            _raise_if_cancelled(cancel_check)
            # 防御：剥掉 ``` 围栏（即使 prompt 说了不要）
            cleaned = re.sub(r"^```(?:markdown|md)?\s*\n?", "", (raw or "").strip())
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
            cleaned = cleaned.strip()
            # 防御：必须包含至少一个 # 标题
            if cleaned and re.search(r"^#\s+\S", cleaned, flags=re.M):
                markmap_md = cleaned
        except Exception:
            markmap_md = ""

        if not markmap_md:
            markmap_md = self._build_fallback_markmap_md(topic, slide_summaries)

        # 收集所有 slide 知识点到场景 knowledge_points
        merged_points: list[str] = []
        for s in slide_scenes:
            for p in [s.title, *s.knowledge_points]:
                if p and p not in merged_points:
                    merged_points.append(p)

        speech_text = (
            f"接下来我们用一张知识结构图，回顾《{topic}》这堂课讲了什么。"
            f"你可以在图中看到主要的概念和它们之间的层级关系。"
        )

        scene_ts = int(datetime.now().timestamp() * 1000)
        return ClassroomScene(
            id=f"scene_mindmap_{scene_ts}",
            type="mindmap",
            title=f"知识结构：{topic}",
            order=0,  # 后续 _renumber 会重排
            knowledge_points=merged_points[:8] or [topic],
            content={
                "format": "markmap",
                "markmap_md": markmap_md,
                "source": "llm" if markmap_md and len(markmap_md) > 30 else "fallback",
            },
            actions=[
                ClassroomAction(
                    id=f"act_mindmap_{scene_ts}",
                    type="speech",
                    text=speech_text,
                )
            ],
        )

    def _call_content_llm_animation_lab(self, prompt: str) -> str:
        """Ask the content LLM whether a classroom animation lab is useful, and generate it."""
        from generators.shared_config import content_llm_call

        return content_llm_call(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是智创空间的互动课堂动画实验设计 agent。"
                        "你的任务不是每次都生成动画，而是判断课堂内容是否真的需要一个可交互动画实验。"
                        "只输出 JSON 对象，不要 markdown，不要代码围栏，不要解释。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=DEFAULT_ANIMATION_LAB_MAX_TOKENS,
        )

    def _build_animation_lab_prompt(
        self,
        *,
        topic: str,
        course: str,
        slide_summaries: list[dict[str, Any]],
        student_profile: dict[str, str] | None = None,
    ) -> str:
        context_lines: list[str] = []
        for idx, slide in enumerate(slide_summaries, start=1):
            title = _clean_text(str(slide.get("title") or ""))
            points = [
                _clean_text(str(p))
                for p in slide.get("knowledge_points", [])
                if _clean_text(str(p))
            ][:6]
            texts = [
                _clean_text(str(t))
                for t in slide.get("extracted_text", [])
                if _clean_text(str(t))
            ][:10]
            speech = _clean_text(str(slide.get("speech_excerpt") or ""))[:220]
            context_lines.append(
                f"{idx}. scene_id={slide.get('scene_id')}\n"
                f"   标题：{title or '无'}\n"
                f"   关键点：{'；'.join(points) or '无'}\n"
                f"   页面文本：{'；'.join(texts) or '无'}\n"
                f"   讲稿摘录：{speech or '无'}"
            )
        profile_hint = _student_profile_hint(_normalize_student_profile(student_profile))
        profile_section = f"\n## 学生画像\n{profile_hint}\n" if profile_hint else ""
        return f"""请判断《{course or '通用课程'}》中《{topic}》这节互动课堂是否需要插入一个“动画实验”场景。

## 已生成课堂页面
{chr(10).join(context_lines)}
{profile_section}

## 生成判断
只有当课堂里存在以下内容之一时才生成动画：
- 几何、空间关系、物理过程、光路、电路、力学、化学变化、数据结构、算法过程、系统流程、概率/函数变化等可视化对象；
- 学生仅靠文字/静态页容易误解，需要通过拖动参数或逐步播放观察规律；
- 动画能明确服务某个页面里的关键知识点，而不是装饰。

如果只是概念定义、历史背景、课程介绍、纯文本总结、学习建议，返回 should_generate=false。

## JSON 输出格式
必须返回 JSON 对象：
{{
  "should_generate": boolean,
  "reason": "为什么生成或不生成，20-80字",
  "placement_after_scene_id": "若生成，填最适合插入其后的 scene_id；若不生成可为空",
  "title": "若生成，动画场景标题",
  "summary": "若生成，动画实验摘要",
  "knowledge_points": ["若生成，1-5个知识点"],
  "video_prompt": "若生成，可用于视频生成的提示词",
  "html": "若生成，完整 <!doctype html> 离线 HTML 文档"
}}

## HTML 硬性要求（should_generate=true 时）
1. 完整 <!doctype html> 文档，只用内联 CSS/JS，不得引用外部 URL。
2. 必须包含 canvas 或 SVG 动画，且至少一个 slider/button 交互控件。
3. 动画逻辑必须贴合课堂页面内容，不要生成通用波形、通用粒子或无关占位。
4. canvas width/height 内部缓冲不低于 1200x720，CSS 响应式适配容器。
5. JavaScript 不得使用 // 行注释；注释必须使用 /* ... */。
6. 页面会嵌入课堂 iframe，画布、标题和控件必须在 16:9 视口内完整展示，不依赖滚动；控件紧凑排列，避免大段说明。
7. 不要给 body、主容器或 .container 添加卡片式边框、阴影、厚 padding；课堂播放器外层已提供承载区域。
8. 浅色专业风格，主色 #0f172a 和 #2D5016。
"""

    def _maybe_build_animation_lab_scene(
        self,
        *,
        topic: str,
        course: str,
        scenes: list[ClassroomScene],
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> ClassroomScene | None:
        _raise_if_cancelled(cancel_check)
        if not self.llm_quiz_enabled:
            return None
        slide_scenes = [s for s in scenes if s.type == "slide"]
        if not slide_scenes:
            return None

        slide_summaries = self._build_slide_summaries(slide_scenes)
        try:
            prompt = self._build_animation_lab_prompt(
                topic=topic,
                course=course,
                slide_summaries=slide_summaries,
                student_profile=student_profile,
            )
            raw = self._call_content_llm_animation_lab(prompt)
            _raise_if_cancelled(cancel_check)
            data = json.loads(self._clean_llm_json(raw))
        except Exception:
            return None

        if not isinstance(data, dict) or not bool(data.get("should_generate")):
            return None
        html = _sanitize_animation_lab_html(str(data.get("html") or ""))
        if not html:
            return None

        title = _clean_text(str(data.get("title") or ""))[:80] or f"{topic} 动画实验"
        summary = _clean_text(str(data.get("summary") or ""))[:300] or (
            f"通过交互动画观察《{topic}》中的关键变化。"
        )
        reason = _clean_text(str(data.get("reason") or ""))[:300]
        placement_after_scene_id = _clean_text(str(data.get("placement_after_scene_id") or ""))[:128]
        points = [
            _clean_text(str(item))[:60]
            for item in data.get("knowledge_points", [])
            if _clean_text(str(item))
        ][:5] if isinstance(data.get("knowledge_points"), list) else []
        if not points:
            points = [topic]
        video_prompt = _clean_text(str(data.get("video_prompt") or ""))[:1000]

        scene_ts = int(datetime.now().timestamp() * 1000)
        speech_text = (
            f"这里插入一个互动动画实验：{title}。"
            f"{summary}"
            f"{' 生成原因是：' + reason if reason else ''}"
            "你可以拖动控件观察变量变化，再回到后面的测验验证理解。"
        )
        return ClassroomScene(
            id=f"scene_animation_{scene_ts}",
            type="animation_lab",
            title=title,
            order=0,
            knowledge_points=points,
            content={
                "format": "html",
                "html": html,
                "summary": summary,
                "video_prompt": video_prompt,
                "decision_reason": reason,
                "placement_after_scene_id": placement_after_scene_id,
                "source": "llm_decision",
                "asset_kind": "interactive_animation",
            },
            actions=[
                ClassroomAction(
                    id=f"act_animation_{scene_ts}",
                    type="speech",
                    text=speech_text,
                )
            ],
        )

    def _insert_animation_lab_scene(
        self,
        scenes: list[ClassroomScene],
        animation_scene: ClassroomScene,
    ) -> list[ClassroomScene]:
        placement_after_scene_id = str(
            (animation_scene.content or {}).get("placement_after_scene_id") or ""
        ).strip()
        for idx, scene in enumerate(scenes):
            if placement_after_scene_id and scene.id == placement_after_scene_id:
                return [*scenes[:idx + 1], animation_scene, *scenes[idx + 1:]]
        slide_seen = 0
        for idx, scene in enumerate(scenes):
            if scene.type != "slide":
                continue
            slide_seen += 1
            if _is_quiz_source_scene(scene, is_first_slide=(slide_seen == 1)):
                return [*scenes[:idx + 1], animation_scene, *scenes[idx + 1:]]
        for idx, scene in enumerate(scenes):
            if scene.type == "slide":
                return [*scenes[:idx + 1], animation_scene, *scenes[idx + 1:]]
        return [animation_scene, *scenes]

