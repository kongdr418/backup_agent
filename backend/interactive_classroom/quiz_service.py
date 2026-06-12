from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from generators.shared_config import content_llm_call
from .critic_service import (
    ClassroomCriticService,
    build_content_llm_semantic_reviewer,
    normalize_critic_mode,
)


def _normalize_answer(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return sorted([str(v).strip() for v in value if str(v).strip()])
    return sorted([str(value).strip()])


def _short_answer_text(answers: dict[str, Any], qid: str) -> str:
    """从 answers 字典里取简答题的学生作答文本（单元素数组 → 字符串）。"""
    raw = answers.get(qid)
    if isinstance(raw, list):
        return " ".join(str(item).strip() for item in raw if str(item).strip()).strip()
    if raw is None:
        return ""
    return str(raw).strip()


def _clean_llm_json(value: str) -> str:
    """剥掉 LLM 输出可能带的 ```json 围栏。"""
    text = (value or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _parse_short_answer_score(raw: str) -> dict[str, Any]:
    """从 LLM 输出解析 {score, feedback, covered_points}。失败时给保守默认。"""
    default = {"score": 0, "feedback": "暂未拿到评分结果，请老师稍后复核。", "covered_points": []}
    if not raw or not raw.strip():
        return default
    try:
        data = json.loads(_clean_llm_json(raw))
    except json.JSONDecodeError:
        # 兜底：尝试从正文里抠出 0-100 的数字作为分数
        m = re.search(r"\b(\d{1,3})\s*分?\b", raw)
        score = int(m.group(1)) if m else 0
        return {**default, "score": max(0, min(100, score)), "feedback": raw.strip()[:200]}

    try:
        score = int(round(float(data.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    feedback = str(data.get("feedback", "")).strip() or default["feedback"]
    covered = data.get("covered_points", [])
    if not isinstance(covered, list):
        covered = []
    covered = [str(p).strip() for p in covered if str(p).strip()]
    return {"score": score, "feedback": feedback[:500], "covered_points": covered[:8]}


async def llm_grade_short_answer(
    question: dict[str, Any],
    student_answer: str,
    llm_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """用 LLM 评一道简答题。

    返回：
        {
          "score": 0-100,         # 整数
          "feedback": str,        # 1-2 句反馈
          "covered_points": [str] # 学生覆盖到的要点
        }
    失败时返回 score=0 + 兜底 feedback，但调用方不应据此判错——业务层应结合
    `analysis` 字段（参考答案要点）做兜底展示。
    """
    reference = str(question.get("reference_answer") or question.get("analysis") or "").strip()
    rubric = question.get("rubric") or []
    if not isinstance(rubric, list):
        rubric = []
    rubric = [str(r).strip() for r in rubric if str(r).strip()]
    if not rubric:
        rubric = ["准确性", "完整性", "表达"]
    knowledge_point = str(question.get("knowledge_point") or "").strip()
    question_text = str(question.get("question") or "").strip()

    system = (
        "你是一位严格的老师，正在批改学生的简答题。"
        "请根据题目、参考答案和评分维度，对学生作答打分并给出一句话反馈。"
        "分数是 0-100 的整数（80 及以上视为掌握）。"
        "必须以 JSON 格式返回，不要包含其他文字。"
    )
    user = (
        f"## 题目\n{question_text}\n\n"
        f"## 参考答案\n{reference or '（无明确参考答案，按知识要点给分）'}\n\n"
        f"## 评分维度\n{'、'.join(rubric)}\n\n"
        f"## 关联知识点\n{knowledge_point or '（未指定）'}\n\n"
        f"## 学生作答\n{student_answer.strip() or '（学生未作答）'}\n\n"
        "## 输出 JSON 格式\n"
        '{"score": 0-100, "feedback": "一句话反馈", "covered_points": ["学生答到的要点1", "要点2"]}\n'
    )
    cfg = llm_config or {}
    mode = normalize_critic_mode(cfg.get("critic_mode"))
    critic = ClassroomCriticService(
        mode=mode,
        semantic_reviewer=(
            build_content_llm_semantic_reviewer(
                cfg,
                llm_call=content_llm_call,
            )
            if mode == "strict"
            else None
        ),
    )
    last_critic: dict[str, Any] = {}
    for attempt in range(2):
        try:
            raw = await asyncio.to_thread(
                content_llm_call,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                # reasoning 模型（如 mimo-v2.5）会用掉绝大部分 token 预算
                # 在"思考"上。600 token 不够（实测 reasoning_tokens=599 时
                # content 被截断为空）。提到 1500 留余量给 JSON 输出。
                max_tokens=1500,
                model=cfg.get("content_model", ""),
                api_key=cfg.get("content_api_key", ""),
                base_url=cfg.get("content_base_url", ""),
                provider_type=cfg.get("content_provider_type", ""),
            )
        except Exception:
            break
        grade = _parse_short_answer_score(raw or "")
        review = critic.review_short_answer_grade(
            grade=grade,
            reference_answer=reference,
            student_answer=student_answer,
        )
        last_critic = review.to_dict()
        if review.passed:
            grade["review_required"] = False
            grade["critic"] = {
                **last_critic,
                "retried": attempt > 0,
                "fallback": False,
            }
            return grade

    return {
        "score": None,
        "feedback": "评分依据不足，本题暂不计分。",
        "covered_points": [],
        "review_required": True,
        "critic": {
            **last_critic,
            "retried": bool(last_critic),
            "fallback": True,
        },
    }


def _result_for_short_answer(
    question: dict[str, Any],
    qid: str,
    student_answer: str,
    grade: dict[str, Any],
) -> dict[str, Any]:
    """把 LLM 评分结果组装成与单选/多选一致的 result 形状。"""
    points = int(question.get("points", 1) or 1)
    review_required = bool(grade.get("review_required"))
    raw_score = grade.get("score")
    score = None if review_required or raw_score is None else int(raw_score or 0)
    if score is not None:
        score = max(0, min(100, score))
    earned_points = 0 if score is None else round((score / 100) * points, 2)
    return {
        "question_id": qid,
        "correct": None if score is None else score >= 80,
        "your_answer": [student_answer] if student_answer else [],
        "correct_answer": [
            str(question.get("reference_answer") or question.get("analysis") or "").strip()
        ],
        "analysis": str(question.get("analysis") or "").strip(),
        "points": points,
        "knowledge_point": str(question.get("knowledge_point") or ""),
        # short_answer 专属字段
        "score": score,
        "feedback": str(grade.get("feedback") or "").strip(),
        "earned_points": earned_points,
        "covered_points": grade.get("covered_points") or [],
        "review_required": review_required,
        "critic": grade.get("critic") or {},
    }


def evaluate_quiz_scene(scene: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    """同步评分器：仅处理单选 / 多选。简答题用 `evaluate_quiz_scene_async` 走 LLM 评分。

    保留此函数（同步 + 仅确定性题型）以：
    - 保持历史测试 `test_interactive_classroom_p3.py` 的契约
    - 让 schema 中 type != "short_answer" 的题在不需要 LLM 时仍走快速路径
    """
    questions = scene.get("content", {}).get("questions", [])
    results: list[dict[str, Any]] = []
    correct = 0
    total = 0
    earned_points = 0.0
    total_points = 0

    for q in questions:
        qid = q.get("id", "")
        qtype = str(q.get("type", "single"))
        if qtype == "short_answer":
            # 同步评估器无法评分简答题；占位 result 由 async 评估器补齐
            continue
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


async def evaluate_quiz_scene_async(
    scene: dict[str, Any],
    answers: dict[str, Any],
    llm_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """异步评分器：单选 / 多选 / 简答题都处理。简答题走 LLM 评分。

    与同步版本返回的 shape 一致（score / correct / total / earned_points /
    total_points / results / feedback_text），方便调用方无差别处理。
    """
    questions = scene.get("content", {}).get("questions", [])
    sync_result = evaluate_quiz_scene(scene, answers)
    results: list[dict[str, Any]] = list(sync_result["results"])
    correct = int(sync_result["correct"])
    total = int(sync_result["total"])
    earned_points = float(sync_result["earned_points"])
    total_points = int(sync_result["total_points"])

    # 简答题：逐题并发评分（asyncio.gather）
    short_answer_questions = [q for q in questions if str(q.get("type", "")) == "short_answer"]
    if short_answer_questions:
        coros = []
        for q in short_answer_questions:
            qid = str(q.get("id", ""))
            student_answer = _short_answer_text(answers, qid)
            coros.append(llm_grade_short_answer(q, student_answer, llm_config))
        grades = await asyncio.gather(*coros, return_exceptions=True)

        for q, grade in zip(short_answer_questions, grades):
            qid = str(q.get("id", ""))
            student_answer = _short_answer_text(answers, qid)
            points = int(q.get("points", 1) or 1)
            if isinstance(grade, Exception) or not isinstance(grade, dict):
                # LLM 评分失败：用 0 分占位，让前端能看到错误反馈
                result = _result_for_short_answer(
                    q,
                    qid,
                    student_answer,
                    {"score": 0, "feedback": "评分服务暂时不可用，请稍后复核。", "covered_points": []},
                )
            else:
                result = _result_for_short_answer(q, qid, student_answer, grade)
            results.append(result)
            if not result["review_required"]:
                total += 1
                total_points += points
                earned_points += result["earned_points"]
                if result["correct"]:
                    correct += 1

    # 按 question_id 稳定排序（前端 resultByQuestion 映射依赖 id）
    results.sort(key=lambda r: str(r.get("question_id", "")))

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
        "earned_points": round(earned_points, 2),
        "total_points": total_points,
        "results": results,
        "feedback_text": feedback_text,
    }
