from __future__ import annotations

from typing import Any


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

    point_set = set(point_names)
    scene_ids: list[str] = []
    for scene in classroom.get("scenes", []):
        if scene.get("type") != "slide":
            continue
        scene_points = set(scene.get("knowledge_points", []))
        if point_set.intersection(scene_points):
            scene_id = scene.get("id")
            if scene_id:
                scene_ids.append(scene_id)
    return scene_ids


def _build_recommended_tasks(
    classroom: dict[str, Any],
    status: str,
    weak_points: list[str],
    strong_points: list[str],
) -> list[dict[str, Any]]:
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
            }
        ]

    if weak_points:
        focus_points = weak_points[:3]
        target_scene_ids = _find_scene_ids_for_points(classroom, focus_points)
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
            },
            {
                "id": "task_practice_weak_points",
                "type": "practice_weak_points",
                "title": "完成补强练习",
                "description": "围绕薄弱点再做一轮同类题，确认概念、判断依据和应用步骤都能独立完成。",
                "priority": "medium",
                "knowledge_points": focus_points,
                "target_scene_ids": [],
                "action_label": "生成练习",
            },
        ]

    next_points = strong_points[:3]
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
        },
    ]


def build_classroom_report(classroom: dict[str, Any], answers_record: dict[str, Any]) -> dict[str, Any]:
    scenes = answers_record.get("scenes", {})
    quiz_scene_count = sum(1 for scene in classroom.get("scenes", []) if scene.get("type") == "quiz")
    answered_quiz_count = len(scenes)

    total_questions = 0
    correct_questions = 0
    earned_points = 0
    total_points = 0
    knowledge_summary: dict[str, dict[str, int]] = {}

    for answer_payload in scenes.values():
        evaluation = answer_payload.get("evaluation", {})
        for result in evaluation.get("results", []):
            point_name = result.get("knowledge_point") or "综合理解"
            points = int(result.get("points", 1) or 1)
            is_correct = bool(result.get("correct"))

            total_questions += 1
            total_points += points
            if is_correct:
                correct_questions += 1
                earned_points += points

            row = knowledge_summary.setdefault(
                point_name,
                {"correct": 0, "total": 0, "earned_points": 0, "total_points": 0, "mastery": 0},
            )
            row["total"] += 1
            row["total_points"] += points
            if is_correct:
                row["correct"] += 1
                row["earned_points"] += points

    for row in knowledge_summary.values():
        row["mastery"] = round((row["correct"] / row["total"]) * 100) if row["total"] else 0

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
        "learned_points": _collect_scene_knowledge(classroom),
        "knowledge_summary": knowledge_summary,
        "weak_points": weak_points,
        "strong_points": strong_points,
        "next_recommendation": next_recommendation,
        "recommended_tasks": recommended_tasks,
    }
