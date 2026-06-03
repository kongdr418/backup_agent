from __future__ import annotations

from typing import Any


def _normalize_answer(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return sorted([str(v).strip() for v in value if str(v).strip()])
    return sorted([str(value).strip()])


def evaluate_quiz_scene(scene: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    questions = scene.get("content", {}).get("questions", [])
    results: list[dict[str, Any]] = []
    correct = 0
    total = 0
    earned_points = 0
    total_points = 0

    for q in questions:
        qid = q.get("id", "")
        expected = _normalize_answer(q.get("answer", []))
        got = _normalize_answer(answers.get(qid))
        is_correct = got == expected and len(expected) > 0
        points = int(q.get("points", 1) or 1)
        total += 1
        total_points += points
        if is_correct:
            correct += 1
            earned_points += points
        results.append(
            {
                "question_id": qid,
                "correct": is_correct,
                "your_answer": got,
                "correct_answer": expected,
                "analysis": q.get("analysis", ""),
                "points": points,
                "knowledge_point": q.get("knowledge_point", ""),
            }
        )

    ratio = (correct / total) if total else 0
    feedback_text = (
        "这次答题整体不错，继续保持。"
        if ratio >= 0.8
        else "这次有一些关键点需要补强，建议复习后再做一轮同类型练习。"
    )

    return {
        "score": round((earned_points / total_points) * 100) if total_points else 0,
        "correct": correct,
        "total": total,
        "earned_points": earned_points,
        "total_points": total_points,
        "results": results,
        "feedback_text": feedback_text,
    }
