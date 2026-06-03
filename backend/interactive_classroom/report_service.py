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
    }
