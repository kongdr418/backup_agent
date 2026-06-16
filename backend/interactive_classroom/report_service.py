from __future__ import annotations

import re
from typing import Any


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


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
                "description": "完成随堂测验，生成后续建议。",
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
                "description": f"回看 {'、'.join(focus_points)} 相关讲解页。",
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
                "description": "围绕薄弱点做一轮同类题。",
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
            "description": "继续学习下一阶段内容。",
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
            "description": "用综合题检查迁移应用能力。",
            "priority": "low",
            "knowledge_points": next_points,
            "target_scene_ids": [],
            "action_label": "挑战练习",
            "reason": history_reason,
            "evidence_ids": history_evidence_ids,
        },
    ]


def _build_learning_path(
    status: str,
    score: int,
    weak_points: list[str],
    strong_points: list[str],
    recommended_tasks: list[dict[str, Any]],
    events: list[dict[str, Any]] | None = None,
    storage: Any | None = None,
    user_id: str = "",
) -> list[dict[str, Any]]:
    task_by_type = {
        str(task.get("type")): task
        for task in recommended_tasks
        if isinstance(task, dict)
    }
    weak_summary = "、".join(weak_points[:3])
    strong_summary = "、".join(strong_points[:3])

    def task_ref(task_type: str) -> dict[str, Any]:
        task = task_by_type.get(task_type) or {}
        return {
            "task_id": task.get("id", ""),
            "action_label": task.get("action_label", ""),
            "knowledge_points": task.get("knowledge_points", []),
            "target_scene_ids": task.get("target_scene_ids", []),
        }

    task_events: dict[str, dict[str, Any]] = {}
    for event in events or []:
        if not isinstance(event, dict):
            continue
        if event.get("type") != "recommended_task_completed":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        task_id = str(payload.get("task_id") or "")
        if task_id:
            task_events[task_id] = payload

    def _classroom_exists(classroom_id: str) -> bool:
        """检查 classroom 是否还存在（未被删除）。"""
        if not classroom_id or not storage or not user_id:
            return False
        try:
            return storage.load_classroom(user_id, classroom_id) is not None
        except Exception:
            return False

    def task_state(
        task_id: str,
        default_status: str,
        default_metric: str,
        default_action_label: str = "",
    ) -> dict[str, str]:
        payload = task_events.get(task_id)
        if not payload:
            return {
                "status": default_status,
                "metric": default_metric,
                "generated_classroom_id": "",
                "action_label": default_action_label,
            }
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        generated_classroom_id = str(result.get("practice_classroom_id") or "")
        # 检查生成的 classroom 是否还存在（可能已被删除）
        classroom_still_exists = _classroom_exists(generated_classroom_id)
        if result.get("status") == "practice_created":
            return {
                "status": "completed" if classroom_still_exists else default_status,
                "metric": "已生成" if classroom_still_exists else default_metric,
                "generated_classroom_id": generated_classroom_id if classroom_still_exists else "",
                "action_label": "查看练习" if classroom_still_exists else default_action_label,
            }
        return {
            "status": "completed" if classroom_still_exists else default_status,
            "metric": "已完成" if classroom_still_exists else default_metric,
            "generated_classroom_id": generated_classroom_id if classroom_still_exists else "",
            "action_label": "查看练习" if classroom_still_exists else default_action_label,
        }

    if status == "not_started":
        complete_task = task_ref("complete_quizzes")
        return [
            {
                "id": "path_diagnose",
                "type": "diagnose",
                "agent_name": "诊断 Agent",
                "title": "完成课堂诊断",
                "description": "先完成随堂测验，系统会用真实答题记录识别薄弱点并生成后续路径。",
                "status": "active",
                "metric": "待诊断",
                **complete_task,
            },
            {
                "id": "path_plan",
                "type": "plan",
                "agent_name": "路径规划 Agent",
                "title": "生成个性化学习路径",
                "description": "诊断完成后会自动给出复习、练习和下一课衔接任务。",
                "status": "locked",
                "metric": "",
                "task_id": "",
                "action_label": "",
                "knowledge_points": [],
                "target_scene_ids": [],
            },
        ]

    diagnose_status = "completed"
    review_task = task_ref("review_weak_points")
    practice_task = task_ref("practice_weak_points")
    next_task = task_ref("next_lesson")
    challenge_task = task_ref("challenge_practice")
    review_state = task_state(
        str(review_task.get("task_id", "")),
        "active" if weak_points else "completed",
        "补弱",
        str(review_task.get("action_label") or ""),
    )
    practice_state = task_state(
        str(practice_task.get("task_id", "")),
        "pending" if weak_points else "active",
        "练习",
        str(practice_task.get("action_label") or ""),
    )
    if practice_state["status"] == "completed" and review_state["status"] == "active":
        review_state = {
            **review_state,
            "status": "completed",
            "metric": "已完成",
        }
    next_status = "pending" if weak_points else "active"
    if practice_state["status"] == "completed":
        next_status = "active"

    if not weak_points:
        review_task = {
            "task_id": "",
            "action_label": "",
            "knowledge_points": strong_points[:3],
            "target_scene_ids": [],
        }
        practice_task = challenge_task

    return [
        {
            "id": "path_diagnose",
            "type": "diagnose",
            "agent_name": "评估 Agent",
            "title": "诊断本节掌握度",
            "description": (
                f"综合得分 {score}%，识别到薄弱点：{weak_summary}。"
                if weak_points
                else f"综合得分 {score}%，本节暂无明显薄弱点。"
            ),
            "status": diagnose_status,
            "metric": f"{score}%",
            "task_id": "",
            "action_label": "",
            "knowledge_points": weak_points[:3] or strong_points[:3],
            "target_scene_ids": [],
        },
        {
            "id": "path_review",
            "type": "review",
            "agent_name": "路径规划 Agent",
            "title": "复听关键讲解",
            "description": (
                f"优先回到 {weak_summary} 的讲解页，把理解断点补齐。"
                if weak_points
                else f"保持 {strong_summary or '本节核心知识'} 的稳定掌握。"
            ),
            "status": review_state["status"],
            "metric": review_state["metric"],
            **review_task,
        },
        {
            "id": "path_practice",
            "type": "practice",
            "agent_name": "资源生成 Agent",
            "title": "生成补强练习",
            "description": (
                "围绕薄弱点生成同类练习，用新的题目验证是否真正掌握。"
                if weak_points
                else "尝试综合挑战题，检查迁移应用能力。"
            ),
            "status": practice_state["status"],
            "metric": practice_state["metric"],
            **practice_task,
            "generated_classroom_id": practice_state["generated_classroom_id"],
            "action_label": practice_state["action_label"] or practice_task.get("action_label", ""),
        },
        {
            "id": "path_next_lesson",
            "type": "next_lesson",
            "agent_name": "课程衔接 Agent",
            "title": "规划下一堂课",
            "description": "根据本节表现自动生成下一课主题、目标和 PPT 生成备注，形成连续学习链路。",
            "status": next_status,
            "metric": "再规划",
            **next_task,
        },
    ]


def build_classroom_report(
    classroom: dict[str, Any],
    answers_record: dict[str, Any],
    events: list[dict[str, Any]] | None = None,
    course_profile: dict[str, Any] | None = None,
    storage: Any | None = None,
    user_id: str = "",
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
    learning_path = _build_learning_path(
        status,
        score,
        weak_points,
        strong_points,
        recommended_tasks,
        events,
        storage,
        user_id,
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
        "learning_path": learning_path,
        "event_count": len(events or []),
        "course_trend": (course_profile or {}).get("recent_trend", "stable"),
    }


def refresh_report_learning_path(
    report: dict[str, Any],
    events: list[dict[str, Any]] | None = None,
    storage: Any | None = None,
    user_id: str = "",
) -> dict[str, Any]:
    refreshed = dict(report)
    refreshed["learning_path"] = _build_learning_path(
        str(refreshed.get("status") or ""),
        int(round(float(refreshed.get("score", 0) or 0))),
        [
            str(value).strip()
            for value in refreshed.get("weak_points", [])
            if str(value).strip()
        ],
        [
            str(value).strip()
            for value in refreshed.get("strong_points", [])
            if str(value).strip()
        ],
        [
            task
            for task in refreshed.get("recommended_tasks", [])
            if isinstance(task, dict)
        ],
        events,
        storage,
        user_id,
    )
    return refreshed


def resolve_knowledge_evidence(
    knowledge_summary: dict[str, Any],
    knowledge_context: dict[str, Any] | None,
    classroom: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not knowledge_context:
        return []

    std_points = knowledge_context.get("knowledge_points", [])
    evidence_chunks = knowledge_context.get("evidence", [])
    if not std_points and not evidence_chunks:
        return []

    point_scene_ids: dict[str, list[str]] = {}
    if classroom:
        for point_name in knowledge_summary:
            scene_ids = _find_scene_ids_for_points(classroom, [point_name])
            if scene_ids:
                point_scene_ids[point_name] = scene_ids

    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for raw_name in knowledge_summary:
        raw_norm = _normalize_text(raw_name)
        best_kp: dict[str, Any] | None = None
        best_score = 0.0
        for kp in std_points:
            label = kp.get("label", "")
            if not label:
                continue
            label_norm = _normalize_text(label)
            if raw_norm == label_norm:
                best_kp = kp
                best_score = 1.0
                break
            if raw_norm in label_norm or label_norm in raw_norm:
                score = min(len(raw_norm), len(label_norm)) / max(len(raw_norm), len(label_norm), 1)
                if score > best_score:
                    best_score = score
                    best_kp = kp

        kp_id = (best_kp or {}).get("knowledge_point_id", "")
        if kp_id in seen_ids:
            continue

        # 置信度过低说明是误匹配（如短词子串命中），跳过
        if best_score < 0.25:
            continue

        matching_evidence: list[dict[str, Any]] = []
        for chunk in evidence_chunks:
            # 跳过课程结构条目（大纲/课次），只匹配实际内容 chunk
            chunk_type = chunk.get("chunk_type", "")
            if chunk_type in ("lesson_outline", "module_outline"):
                continue
            chunk_text = _normalize_text(chunk.get("text", "") + " " + chunk.get("section", ""))
            # 短知识点名（<4字符）不做子串匹配，避免"项目"误命中"课程项目整合与展示答辩"
            text_match = len(raw_norm) >= 4 and raw_norm in chunk_text
            keyword_match = any(
                _normalize_text(kw) in raw_norm
                for kw in chunk.get("keywords", [])
                if len(kw) >= 2
            )
            if text_match or keyword_match:
                matching_evidence.append({
                    "chunk_id": chunk.get("chunk_id", ""),
                    "evidence_label": chunk.get("evidence_label", ""),
                    "source_name": chunk.get("source_name", ""),
                    "section": chunk.get("section", ""),
                    "text_excerpt": (chunk.get("text", "") or "")[:200],
                })

        row: dict[str, Any] = {
            "knowledge_point_id": kp_id,
            "raw_name": raw_name,
            "standard_label": (best_kp or {}).get("label", ""),
            "match_confidence": round(best_score, 2),
            "evidence": matching_evidence[:3],
            "scene_ids": point_scene_ids.get(raw_name, []),
        }
        results.append(row)
        if kp_id:
            seen_ids.add(kp_id)

    return results
