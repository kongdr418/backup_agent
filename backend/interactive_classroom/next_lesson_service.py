from __future__ import annotations

import re
from typing import Any

from .report_service import _compact_text_key


def clean_next_lesson_text(value: Any, max_length: int = 160) -> str:
    return " ".join(str(value or "").split())[:max_length]


def clean_next_lesson_list(values: Any, max_items: int = 6) -> list[str]:
    if isinstance(values, str):
        rows = re.split(r"[，、,;/|]+", values)
    elif isinstance(values, list):
        rows = values
    else:
        rows = []
    result = []
    for row in rows:
        text = clean_next_lesson_text(row, 80)
        if text and text not in result:
            result.append(text)
        if len(result) >= max_items:
            break
    return result


def build_next_lesson_plan(
    classroom: dict,
    report: dict,
    overrides: dict,
    knowledge_context: dict | None = None,
    generation_strategy: dict | None = None,
) -> dict:
    topic = clean_next_lesson_text(classroom.get("topic"), 120) or "本节课程"
    course = clean_next_lesson_text(classroom.get("course"), 120) or topic
    weak_points = clean_next_lesson_list(report.get("weak_points", []), 5)
    strong_points = clean_next_lesson_list(report.get("strong_points", []), 5)
    learned_points = clean_next_lesson_list(report.get("learned_points", []), 6)
    next_recommendation = clean_next_lesson_text(
        report.get("next_recommendation"),
        220,
    )
    assessment_strategy = (
        generation_strategy.get("assessment_strategy", {})
        if isinstance(generation_strategy, dict)
        else {}
    )
    transfer_level = clean_next_lesson_text(
        assessment_strategy.get("transfer_level"),
        60,
    ) or "unobserved"
    error_targets = clean_next_lesson_list(
        assessment_strategy.get("error_targets", []),
        6,
    )

    course_lessons = (knowledge_context or {}).get("lessons", [])
    course_kp_labels = [
        kp.get("label", "")
        for kp in (knowledge_context or {}).get("knowledge_points", [])
        if kp.get("label")
    ]

    next_lesson_from_course = None
    if course_lessons:
        current_topic_norm = _compact_text_key(topic)
        for i, lesson in enumerate(course_lessons):
            lesson_title = clean_next_lesson_text(lesson.get("title", ""), 120)
            if lesson_title and _compact_text_key(lesson_title) == current_topic_norm:
                if i + 1 < len(course_lessons):
                    next_lesson_from_course = course_lessons[i + 1]
                break
        if next_lesson_from_course is None and len(course_lessons) > 1:
            first_title = course_lessons[0].get("title", "")
            next_lesson_from_course = (
                course_lessons[1]
                if _compact_text_key(first_title) == current_topic_norm
                else course_lessons[0]
            )

    default_topic = (
        f"{'、'.join(weak_points[:2])}补强与应用"
        if weak_points
        else (next_lesson_from_course or {}).get("title", "") or f"{topic}进阶应用"
    )
    next_topic = (
        clean_next_lesson_text(overrides.get("topic"), 120)
        or default_topic
    )
    learning_goal = (
        clean_next_lesson_text(overrides.get("learning_goal"), 180)
        or (
            f"巩固{'、'.join(weak_points[:3])}，并能迁移到新的课堂任务中。"
            if weak_points
            else "在已掌握内容基础上进入下一阶段任务，完成更综合的理解和应用。"
        )
    )
    focus_points = (
        clean_next_lesson_list(overrides.get("focus_points"), 6)
        or weak_points[:4]
        or course_kp_labels[:4]
        or clean_next_lesson_list([next_topic], 1)
    )
    review_points = (
        clean_next_lesson_list(overrides.get("review_points"), 6)
        or [
            f"上一课《{topic}》的核心内容",
            *learned_points[:3],
            *strong_points[:2],
        ]
    )
    review_points = clean_next_lesson_list(review_points, 6)

    rationale_parts = []
    if weak_points:
        rationale_parts.append(f"报告显示需要优先补强：{'、'.join(weak_points[:3])}。")
    if strong_points:
        rationale_parts.append(f"可利用已掌握的{'、'.join(strong_points[:2])}做迁移。")
    if next_recommendation:
        rationale_parts.append(next_recommendation)
    if next_lesson_from_course:
        rationale_parts.append(f"课程大纲下一课：{next_lesson_from_course.get('title', '')}。")
    if transfer_level != "unobserved":
        rationale_parts.append(f"当前知识迁移水平：{transfer_level}。")
    if error_targets:
        rationale_parts.append(f"下一课需要继续处理错误模式：{'、'.join(error_targets)}。")
    rationale = " ".join(rationale_parts) or "根据本节课堂表现，建议进入下一阶段学习。"
    source_id = clean_next_lesson_text(classroom.get("id"), 128)
    course_root_id = clean_next_lesson_text(classroom.get("course_root_id"), 128) or source_id
    try:
        lesson_index = int(classroom.get("lesson_index", 1) or 1) + 1
    except (TypeError, ValueError):
        lesson_index = 2
    try:
        lesson_depth = int(classroom.get("lesson_depth", 0) or 0) + 1
    except (TypeError, ValueError):
        lesson_depth = 1

    ppt_notes_lines = [
        "【连续课堂上下文】",
        f"上一课主题：{topic}",
        f"上一课得分：{report.get('score', 0)}%",
        f"上一课回顾：{'；'.join(review_points)}",
        f"薄弱点：{'、'.join(weak_points) or '暂无明显薄弱点'}",
        f"强项：{'、'.join(strong_points) or '暂无稳定强项'}",
        f"知识迁移水平：{transfer_level}",
        f"错误模式：{'、'.join(error_targets) or '暂无稳定错误模式'}",
    ]

    course_summary = (knowledge_context or {}).get("summary", "")
    if course_summary:
        ppt_notes_lines.append(f"课程简介：{course_summary}")
    if course_lessons:
        lesson_titles = [l.get("title", "") for l in course_lessons[:6] if l.get("title")]
        if lesson_titles:
            ppt_notes_lines.append(f"课程大纲相关课次：{'、'.join(lesson_titles)}")

    ppt_notes_lines.extend([
        "",
        "【下一堂课生成要求】",
        f"本课主题：{next_topic}",
        f"本课目标：{learning_goal}",
        f"本课重点：{'、'.join(focus_points)}",
        f"衔接理由：{rationale}",
        "请在 PPT 前 1-2 页简要总结上一堂课讲了什么与学生表现，再进入本节新内容。",
        "新内容需要自然承接薄弱点和已掌握内容，避免直接展示画像字段。",
    ])
    ppt_notes = "\n".join(ppt_notes_lines)

    return {
        "topic": next_topic,
        "course": course,
        "learning_goal": learning_goal,
        "review_points": review_points,
        "focus_points": focus_points,
        "weak_points": weak_points,
        "strong_points": strong_points,
        "rationale": rationale,
        "ppt_notes": ppt_notes,
        "source_classroom_id": classroom.get("id", ""),
        "source_topic": topic,
        "source_ppt_job_id": (classroom.get("source") or {}).get("job_id", ""),
        "course_root_id": course_root_id,
        "parent_classroom_id": source_id,
        "lesson_depth": lesson_depth,
        "lesson_index": lesson_index,
        "lesson_kind": "next_lesson",
        "course_lesson_title": (next_lesson_from_course or {}).get("title", ""),
        "course_knowledge_points": course_kp_labels[:6],
        "transfer_level": transfer_level,
        "error_targets": error_targets,
    }
