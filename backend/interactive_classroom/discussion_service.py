from __future__ import annotations

from typing import Any

from generators.shared_config import content_llm_call


QUICK_ACTION_PROMPTS = {
    "换个例子": "请换一个更贴近课堂语境的例子来引导学生理解，不要直接给标准答案。",
    "再提示一点": "请只多给一点提示，继续引导学生思考，不要直接公布答案。",
    "总结一下": "请用简洁课堂语言总结当前问题涉及的关键点，保持启发式语气。",
}


def _normalize_text(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        rows: list[str] = []
        for item in value:
            rows.extend(_normalize_text(item))
        return rows
    return []


def _scene_text_lines(scene: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    title = (scene.get("title") or "").strip()
    if title:
        lines.append(f"场景标题：{title}")

    knowledge_points = scene.get("knowledge_points") or []
    if knowledge_points:
        lines.append("知识点：" + "、".join(str(point).strip() for point in knowledge_points if str(point).strip()))

    content = scene.get("content") or {}
    extracted_text = _normalize_text(content.get("extracted_text"))
    if extracted_text:
        lines.append("页面文本：" + "；".join(extracted_text[:8]))

    markdown = _normalize_text(content.get("markdown"))
    if markdown:
        lines.append("页面摘要：" + " ".join(markdown[:2]))

    questions = content.get("questions") or []
    for idx, question in enumerate(questions, start=1):
        title = (question.get("question") or "").strip()
        if title:
            lines.append(f"题目{idx}：{title}")
        options = question.get("options") or []
        option_labels = [str(opt.get("label") or "").strip() for opt in options if str(opt.get("label") or "").strip()]
        if option_labels:
            lines.append(f"选项{idx}：" + " / ".join(option_labels[:4]))
        analysis = (question.get("analysis") or "").strip()
        if analysis:
            lines.append(f"解析{idx}：{analysis}")

    actions = scene.get("actions") or []
    for action in actions:
        action_type = action.get("type")
        if action_type not in {"speech", "quiz_feedback"}:
            continue
        text = (action.get("text") or "").strip()
        if text:
            lines.append(f"讲解：{text}")

    return lines


def _find_scene(classroom: dict[str, Any], scene_id: str) -> dict[str, Any] | None:
    if not scene_id:
        return None
    for scene in classroom.get("scenes") or []:
        if scene.get("id") == scene_id:
            return scene
    return None


def _scene_speech_text(scene: dict[str, Any]) -> str:
    for action in scene.get("actions") or []:
        if action.get("type") in {"speech", "quiz_feedback"}:
            text = (action.get("text") or "").strip()
            if text:
                return text
    return ""


def _scene_primary_text(scene: dict[str, Any]) -> str:
    speech = _scene_speech_text(scene)
    if speech:
        return speech
    for line in _scene_text_lines(scene):
        if line.startswith("页面文本：") or line.startswith("页面摘要：") or line.startswith("解析1："):
            _, text = line.split("：", 1)
            text = text.strip()
            if text:
                return text
    return ""


def build_discussion_context(classroom: dict[str, Any], played_scene_ids: list[str]) -> str:
    scenes = classroom.get("scenes") or []
    played_set = {scene_id for scene_id in played_scene_ids if scene_id}
    selected = [scene for scene in scenes if scene.get("id") in played_set] if played_set else scenes

    lines = [
        f"课堂主题：{(classroom.get('topic') or '').strip()}",
        f"课堂标题：{(classroom.get('title') or '').strip()}",
    ]
    for scene in selected:
        lines.append(f"--- 场景 {scene.get('order') or ''} / {scene.get('type') or 'unknown'} ---")
        lines.extend(_scene_text_lines(scene))

    text = "\n".join(line for line in lines if line.strip())
    return text[:6000]


def build_focus_scene_context(classroom: dict[str, Any], current_scene_id: str = "") -> str:
    scene = _find_scene(classroom, current_scene_id)
    if not scene:
        return ""
    lines = [f"当前页面：{(scene.get('title') or '').strip()}"]
    lines.extend(_scene_text_lines(scene))
    return "\n".join(line for line in lines if line.strip())[:2500]


def build_course_outline_context(classroom: dict[str, Any]) -> str:
    scenes = sorted(classroom.get("scenes") or [], key=lambda item: item.get("order") or 0)
    total = len(scenes)
    lines = [f"整堂课共 {total} 页，下面是页码与讲稿摘要："]
    for scene in scenes:
        order = scene.get("order") or 0
        scene_type = scene.get("type") or "unknown"
        title = (scene.get("title") or "").strip() or "未命名页面"
        summary = _scene_primary_text(scene)
        if len(summary) > 120:
            summary = summary[:120] + "..."
        line = f"第{order}页｜{scene_type}｜{title}"
        if summary:
            line += f"｜讲稿：{summary}"
        lines.append(line)
    return "\n".join(lines)[:7000]


def build_current_position_context(classroom: dict[str, Any], current_scene_id: str = "") -> str:
    scenes = sorted(classroom.get("scenes") or [], key=lambda item: item.get("order") or 0)
    total = len(scenes)
    scene = _find_scene(classroom, current_scene_id)
    if not scene:
        return ""
    order = scene.get("order") or next((idx + 1 for idx, item in enumerate(scenes) if item.get("id") == current_scene_id), 0)
    title = (scene.get("title") or "").strip() or "未命名页面"
    summary = _scene_primary_text(scene)
    lines = [
        f"当前位于第 {order} / {total} 页",
        f"当前页面标题：{title}",
        f"当前页面类型：{scene.get('type') or 'unknown'}",
    ]
    if summary:
        lines.append(f"当前页讲稿：{summary}")
    return "\n".join(lines)


def build_discussion_messages(
    classroom: dict[str, Any],
    played_scene_ids: list[str],
    conversation: list[dict[str, str]],
    trigger: str,
    quick_action: str = "",
    current_scene_id: str = "",
) -> list[dict[str, str]]:
    context = build_discussion_context(classroom, played_scene_ids)
    focus_context = build_focus_scene_context(classroom, current_scene_id)
    course_outline = build_course_outline_context(classroom)
    current_position = build_current_position_context(classroom, current_scene_id)
    trigger_text = {
        "manual": "学生主动提问",
        "wrong_answer": "学生答错题后追问",
        "key_scene": "进入重点讲解页后的引导",
        "long_dwell": "学生停留较久后的轻提醒",
    }.get(trigger, "课堂讨论")

    quick_action_prompt = QUICK_ACTION_PROMPTS.get(quick_action, "")
    system_prompt = (
        "你是课堂中的 AI 教师助手。"
        "回答风格：亲切、简洁、专业，像一位认真负责的教师。"
        "单条回答控制在 3 到 6 句之间：第一句点明当前页在讲什么（复用页标题/术语），后面几句给出基于课堂内容的具体解释。"
        "针对不同意图的回复策略："
        "- 学生说『能再详细讲讲吗』『详细解释』『展开说』等 → 直接给出基于当前页内容的具体解释，2 到 4 句讲清楚是什么、为什么。"
        "- 学生答错题后追问 → 简短指出错因（直接说『正确答案是 X，因为 Y』），必要时再追问引导。"
        "- 学生问『这页什么意思』等模糊问题 → 默认就是在问当前页，直接讲解，不要先反问。"
        "- 学生请求判断/总结 → 直接给答案 + 简短理由。"
        "硬性约束：必须先给出一句贴着当前页内容的解释，禁止只用反问收尾。优先引用页面文本/讲解词/题目原文。"
    )
    user_prompt = (
        f"当前讨论触发方式：{trigger_text}\n"
        f"{f'{current_position}\\n' if current_position else ''}"
        f"{f'快捷动作：{quick_action}\\n' if quick_action else ''}"
        f"{f'请优先围绕当前页面内容回答：\\n{focus_context}\\n' if focus_context else ''}"
        f"整堂课页码与讲稿摘要：\n{course_outline}\n"
        f"以下是本堂课已经播放过的课堂文本上下文，请只基于这些内容回答，不要编造课堂里没有讲过的知识：\n"
        f"{context}\n"
        "回答约束：\n"
        "1. 如果学生提到“这页”“这一页”“当前这部分”，一律解释当前页，不要让学生再澄清。\n"
        "2. 先用 1 句概括当前页核心内容，再进行解释或举例。\n"
        "3. 解释时优先引用当前页里的标题、页面文本、讲解词、题目或知识点。\n"
        "4. 不要输出“你是想问概念还是顺序吗”这种脱离页面的泛化追问，除非当前页上下文本身不足。\n"
        f"{quick_action_prompt}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    for item in conversation[-8:]:
        role = item.get("role", "")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    return messages


def _fallback_reply(
    classroom: dict[str, Any],
    conversation: list[dict[str, str]],
    quick_action: str = "",
    current_scene_id: str = "",
) -> str:
    last_user_message = ""
    for item in reversed(conversation):
        if item.get("role") == "user" and (item.get("content") or "").strip():
            last_user_message = item["content"].strip()
            break

    scene = _find_scene(classroom, current_scene_id)
    focus_lines = _scene_text_lines(scene) if scene else []
    focus_title = (scene.get("title") or "").strip() if scene else ""
    focus_excerpt = ""
    preferred_prefixes = ("页面文本：", "页面摘要：", "讲解：", "知识点：")
    for prefix in preferred_prefixes:
        for line in focus_lines:
            if line.startswith(prefix):
                _, text = line.split("：", 1)
                text = text.strip()
                if text:
                    focus_excerpt = text
                    break
        if focus_excerpt:
            break
    for line in focus_lines:
        if line.startswith("场景标题："):
            continue
        if "：" in line:
            _, text = line.split("：", 1)
            text = text.strip()
            if text:
                focus_excerpt = text
                break

    if quick_action == "换个例子":
        if focus_excerpt:
            return f"我们先换个贴近这页内容的例子想。围绕“{focus_excerpt[:32]}”，你能先说说这里谁先发起、谁后响应吗？"
        if focus_title:
            return f"我们先换个贴近“{focus_title}”的例子想。你能先说说这里最先发生的动作是哪一步吗？"
        return "我们先换个更贴近这一页内容的例子想。你先找一找，哪个角色是先发起动作的？"

    if quick_action == "再提示一点":
        if focus_excerpt:
            return f"我先只多给一点提示：先别急着看结果，先盯住“{focus_excerpt[:28]}”这部分，想想它决定了后面的哪一步。"
        return "我先只多给一点提示：先不要急着看结果，先找一找这一页里哪一步决定了后面的流程。"
    if quick_action == "总结一下":
        if focus_title:
            return f"先抓一句最核心的话：这一页讲的是“{focus_title}”里的关键流程。你再回头看一眼，哪一步最能代表它的核心逻辑？"
        return "先抓一句最核心的话：你先回头看一眼这一页，哪一步最像它的核心逻辑？"
    if last_user_message:
        return f"你先别急着下结论。围绕“{last_user_message[:24]}”，你能先说说你现在最不确定的是概念本身，还是执行顺序吗？"
    if focus_title:
        return f"你先别急着找答案。先说说在“{focus_title}”这一页里，你觉得最关键的一步或概念是哪一个？"
    return "你先别急着找答案。先说说你觉得这一页里最关键的一步或概念是哪一个？"


def generate_discussion_reply(
    classroom: dict[str, Any],
    played_scene_ids: list[str],
    conversation: list[dict[str, str]],
    trigger: str,
    quick_action: str = "",
    current_scene_id: str = "",
    llm_config: dict[str, str] | None = None,
) -> str:
    messages = build_discussion_messages(classroom, played_scene_ids, conversation, trigger, quick_action, current_scene_id)
    llm_config = llm_config or {}
    try:
        reply = (
            content_llm_call(
                messages=messages,
                temperature=0.6,
                max_tokens=600,
                model=llm_config.get("content_model", ""),
                api_key=llm_config.get("content_api_key", ""),
                base_url=llm_config.get("content_base_url", ""),
                provider_type=llm_config.get("content_provider_type", ""),
            )
            or ""
        ).strip()
        if reply:
            return reply
    except Exception:
        pass
    return _fallback_reply(classroom, conversation, quick_action, current_scene_id)
