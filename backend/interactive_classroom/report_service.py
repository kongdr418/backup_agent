from __future__ import annotations

import re
from typing import Any


def _compact_text_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _collect_scene_knowledge(classroom: dict[str, Any]) -> list[str]:
    points: list[str] = []
    seen: set[str] = set()

    for point in classroom.get("knowledge_points", []):
        if point and point not in seen:
            seen.add(point)
            points.append(point)

    for scene in classroom.get("scenes", []):
        for point in scene.get("knowledge_points", []):
            if point and point not in seen:
                seen.add(point)
                points.append(point)

    return points


def _find_scene_ids_for_points(classroom: dict[str, Any], point_names: list[str]) -> list[str]:
    if not point_names:
        return []

    point_keys = [_compact_text_key(point) for point in point_names]
    scene_ids: list[str] = []
    for scene in classroom.get("scenes", []):
        if scene.get("type") != "slide":
            continue
        content = scene.get("content", {})
        text_parts = [
            scene.get("title", ""),
            *scene.get("knowledge_points", []),
            *content.get("extracted_text", []),
            content.get("markdown", ""),
        ]
        scene_key = _compact_text_key(" ".join(str(part) for part in text_parts if part))
        if any(point_key and point_key in scene_key for point_key in point_keys):
            scene_id = scene.get("id")
            if scene_id:
                scene_ids.append(scene_id)
    return scene_ids


def _build_recommended_tasks(
    classroom: dict[str, Any],
    status: str,
    weak_points: list[str],
    strong_points: list[str],
    point_scene_ids: dict[str, list[str]] | None = None,
    course_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    course_profile = course_profile or {}
    mastery = (
        course_profile.get("mastery")
        if isinstance(course_profile.get("mastery"), dict)
        else {}
    )

    def history_for(point_names: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
        rows = [
            row
            for row in mastery.values()
            if isinstance(row, dict) and row.get("name") in point_names
        ]
        evidence_ids: list[str] = []
        for row in rows:
            for event_id in row.get("evidence_ids", []):
                if event_id and event_id not in evidence_ids:
                    evidence_ids.append(event_id)
        return rows, evidence_ids

    if status == "not_started":
        return [
            {
                "id": "task_complete_quizzes",
                "type": "complete_quizzes",
                "title": "先完成课堂测验",
                "description": "完成课堂中的随堂测验后，系统会根据真实答题记录生成薄弱点和后续学习建议。",
                "priority": "high",
                "knowledge_points": [],
                "target_scene_ids": [],
                "action_label": "回到测验",
                "reason": "当前课堂尚无答题证据。",
                "evidence_ids": [],
            }
        ]

    if weak_points:
        focus_points = weak_points[:3]
        target_scene_ids = _find_scene_ids_for_points(classroom, focus_points)
        for point in focus_points:
            for scene_id in (point_scene_ids or {}).get(point, []):
                if scene_id not in target_scene_ids:
                    target_scene_ids.append(scene_id)
        history_rows, history_evidence_ids = history_for(focus_points)
        historical_scores = [
            int(round(float(row.get("score", 0) or 0)))
            for row in history_rows
        ]
        historical_reason = (
            f"历史课程画像中相关掌握度最低为 {min(historical_scores)}%，"
            f"近期趋势为 {course_profile.get('recent_trend', 'stable')}。"
            if historical_scores
            else "本次课堂报告首次识别到这些薄弱点。"
        )
        return [
            {
                "id": "task_review_weak_points",
                "type": "review_weak_points",
                "title": "复听薄弱知识点",
                "description": f"优先回看 {'、'.join(focus_points)} 相关讲解页，补齐本节理解断点。",
                "priority": "high",
                "knowledge_points": focus_points,
                "target_scene_ids": target_scene_ids,
                "action_label": "复听讲解",
                "reason": historical_reason,
                "evidence_ids": history_evidence_ids,
            },
            {
                "id": "task_practice_weak_points",
                "type": "practice_weak_points",
                "title": "完成补强练习",
                "description": "围绕薄弱点再做一轮同类题，确认概念、判断依据和应用步骤都能独立完成。",
                "priority": "high" if historical_scores and min(historical_scores) < 65 else "medium",
                "knowledge_points": focus_points,
                "target_scene_ids": [],
                "action_label": "生成练习",
                "reason": historical_reason,
                "evidence_ids": history_evidence_ids,
            },
        ]

    next_points = strong_points[:3]
    history_rows, history_evidence_ids = history_for(next_points)
    historical_scores = [
        int(round(float(row.get("score", 0) or 0)))
        for row in history_rows
    ]
    history_reason = (
        f"历史课程画像中相关掌握度达到 {max(historical_scores)}%，"
        "可以进入迁移应用。"
        if historical_scores
        else "本次课堂未发现明显薄弱点。"
    )
    return [
        {
            "id": "task_next_lesson",
            "type": "next_lesson",
            "title": "进入下一节课",
            "description": "本节掌握情况较稳定，可以继续学习下一阶段内容，保持知识链条连续。",
            "priority": "medium",
            "knowledge_points": next_points,
            "target_scene_ids": [],
            "action_label": "规划下一课",
            "reason": history_reason,
            "evidence_ids": history_evidence_ids,
        },
        {
            "id": "task_challenge_practice",
            "type": "challenge_practice",
            "title": "尝试综合挑战题",
            "description": "用更高综合度的问题检查迁移应用能力，避免只停留在课堂记忆层面。",
            "priority": "low",
            "knowledge_points": next_points,
            "target_scene_ids": [],
            "action_label": "挑战练习",
            "reason": history_reason,
            "evidence_ids": history_evidence_ids,
        },
    ]


def build_classroom_report(
    classroom: dict[str, Any],
    answers_record: dict[str, Any],
    events: list[dict[str, Any]] | None = None,
    course_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenes = answers_record.get("scenes", {})
    quiz_scene_count = sum(1 for scene in classroom.get("scenes", []) if scene.get("type") == "quiz")
    answered_quiz_count = len(scenes)
    answered_scene_ids = list(scenes.keys())

    total_questions = 0
    correct_questions = 0
    earned_points = 0
    total_points = 0
    knowledge_summary: dict[str, dict[str, Any]] = {}
    quiz_scene_map = {
        scene.get("id"): scene
        for scene in classroom.get("scenes", [])
        if scene.get("type") == "quiz"
    }
    point_scene_ids: dict[str, list[str]] = {}

    # P7: 构建知识点→事件ID映射
    kp_event_ids: dict[str, list[str]] = {}
    for ev in (events or []):
        for kp in ev.get("knowledge_points", []):
            if kp:
                kp_event_ids.setdefault(kp, []).append(ev.get("id", ""))

    for scene_id, answer_payload in scenes.items():
        evaluation = answer_payload.get("evaluation", {})
        quiz_scene = quiz_scene_map.get(scene_id, {})
        covered_scene_ids = quiz_scene.get("content", {}).get("covered_scene_ids", [])
        for result in evaluation.get("results", []):
            raw_point = (result.get("knowledge_point") or "").strip()
            # 剥离内部 scene ID（兼容旧数据中残留的 scene_slide_002 等）
            raw_point = re.sub(r"\bscene_(?:slide|quiz|mindmap)_\d+\b", "", raw_point).strip()
            point_name = raw_point or "综合理解"
            points = int(result.get("points", 1) or 1)
            is_correct = bool(result.get("correct"))
            # 简答题（short_answer）走 0-100 分数，earned_points 是小数；
            # 单选/多选走 0/1 全额，earned_points 缺省按整 points 计。
            raw_earned = result.get("earned_points")
            if raw_earned is not None:
                earned_for_this = float(raw_earned)
            elif is_correct:
                earned_for_this = float(points)
            else:
                earned_for_this = 0.0

            total_questions += 1
            total_points += points
            earned_points += earned_for_this
            if is_correct:
                correct_questions += 1

            row = knowledge_summary.setdefault(
                point_name,
                {"correct": 0, "total": 0, "earned_points": 0, "total_points": 0, "mastery": 0, "event_ids": []},
            )
            row["total"] += 1
            row["total_points"] += points
            row["earned_points"] += earned_for_this
            if is_correct:
                row["correct"] += 1
            else:
                rows = point_scene_ids.setdefault(point_name, [])
                for covered_scene_id in covered_scene_ids:
                    if covered_scene_id and covered_scene_id not in rows:
                        rows.append(covered_scene_id)

    # P7: 回填 event_ids 到每个知识点
    for point_name, row in knowledge_summary.items():
        row["mastery"] = round((row["correct"] / row["total"]) * 100) if row["total"] else 0
        row["event_ids"] = list(set(kp_event_ids.get(point_name, [])))

    score = round((earned_points / total_points) * 100) if total_points else 0
    weak_points = [name for name, row in knowledge_summary.items() if row["mastery"] < 80]
    strong_points = [name for name, row in knowledge_summary.items() if row["mastery"] >= 80]

    if not total_questions:
        status = "not_started"
        next_recommendation = "建议先完成课堂中的随堂测验，系统会根据答题结果生成薄弱点和下一步建议。"
    elif weak_points:
        status = "needs_review"
        next_recommendation = f"建议优先复习：{'、'.join(weak_points[:3])}，再完成一轮同类练习。"
    else:
        status = "completed"
        next_recommendation = "本节掌握情况较好，可以进入下一节内容，或尝试更高难度的综合练习。"

    recommended_tasks = _build_recommended_tasks(
        classroom,
        status,
        weak_points,
        strong_points,
        point_scene_ids,
        course_profile,
    )

    return {
        "classroom_id": classroom.get("id", ""),
        "title": classroom.get("title", ""),
        "topic": classroom.get("topic", ""),
        "status": status,
        "score": score,
        "correct": correct_questions,
        "total": total_questions,
        "earned_points": earned_points,
        "total_points": total_points,
        "quiz_scene_count": quiz_scene_count,
        "answered_quiz_count": answered_quiz_count,
        "answered_scene_ids": answered_scene_ids,
        "learned_points": _collect_scene_knowledge(classroom),
        "knowledge_summary": knowledge_summary,
        "weak_points": weak_points,
        "strong_points": strong_points,
        "next_recommendation": next_recommendation,
        "recommended_tasks": recommended_tasks,
        "event_count": len(events or []),
        "course_trend": (course_profile or {}).get("recent_trend", "stable"),
    }
