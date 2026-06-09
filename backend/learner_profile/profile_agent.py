from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Callable


LlmCall = Callable[..., str]
_DEFAULT_LLM = object()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean_text(value: Any, max_length: int = 200) -> str:
    return " ".join(str(value or "").split())[:max_length]


def _compact_key(value: Any) -> str:
    return "".join(
        ch.lower()
        for ch in _clean_text(value, 120)
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff"
    )


def _stable_id(prefix: str, *parts: Any, length: int = 16) -> str:
    raw = "|".join(_compact_key(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def build_course_id(course_name: str) -> str:
    return _stable_id("course", course_name or "通用课程", length=12)


def build_knowledge_point_id(name: str, parent_name: str = "") -> str:
    return _stable_id("kp", parent_name, name, length=12)


def _extract_json(value: str) -> Any:
    text = (value or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start_candidates = [pos for pos in (text.find("{"), text.find("[")) if pos >= 0]
    if start_candidates:
        text = text[min(start_candidates):]
    for end_char in ("}", "]"):
        end = text.rfind(end_char)
        if end >= 0:
            candidate = text[: end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return json.loads(text)


def _content_style_tokens(values: list[Any]) -> list[str]:
    mapping = {
        "图解": "diagram",
        "案例": "example",
        "步骤推导": "step_by_step",
        "分步": "step_by_step",
        "代码实操": "code_practice",
        "代码": "code_practice",
        "对比辨析": "comparison",
        "对比": "comparison",
        "精简总结": "concise_summary",
    }
    result: list[str] = []
    for value in values:
        text = _clean_text(value, 40)
        token = next((target for source, target in mapping.items() if source in text), "")
        if token and token not in result:
            result.append(token)
    return result or ["diagram", "example"]


class ProfileAgent:
    def __init__(
        self,
        llm_call: LlmCall | None | object = _DEFAULT_LLM,
        now_provider: Callable[[], str] | None = None,
    ) -> None:
        if llm_call is _DEFAULT_LLM:
            try:
                from generators.shared_config import content_llm_call

                self.llm_call: LlmCall | None = content_llm_call
            except ImportError:
                self.llm_call = None
        else:
            self.llm_call = llm_call if callable(llm_call) else None
        self.now_provider = now_provider or _now_iso

    def build_generation_strategy(
        self,
        profile: dict[str, Any],
        course_name: str,
    ) -> dict[str, Any]:
        basic = profile.get("basic") if isinstance(profile.get("basic"), dict) else {}
        preferences = (
            profile.get("preferences")
            if isinstance(profile.get("preferences"), dict)
            else {}
        )
        course_id = build_course_id(course_name)
        course = (
            profile.get("courses", {}).get(course_id, {})
            if isinstance(profile.get("courses"), dict)
            else {}
        )
        basis = _clean_text(basic.get("learning_basis"), 80) or "零基础"
        preferred_difficulty = (
            _clean_text(preferences.get("preferred_difficulty"), 40) or "基础"
        )
        if "进阶" in basis or "挑战" in preferred_difficulty:
            explanation_depth = "advanced"
            quiz_difficulty = "advanced"
        elif "有基础" in basis or "中等" in preferred_difficulty:
            explanation_depth = "intermediate"
            quiz_difficulty = "intermediate"
        else:
            explanation_depth = "basic_to_intermediate"
            quiz_difficulty = "basic"

        tutoring_style = _clean_text(preferences.get("tutoring_style"), 80)
        if "直接" in tutoring_style:
            feedback_style = "direct"
        elif "启发" in tutoring_style:
            feedback_style = "socratic"
        else:
            feedback_style = "guided"

        mastery = course.get("mastery") if isinstance(course.get("mastery"), dict) else {}
        weak_rows = sorted(
            (
                row
                for row in mastery.values()
                if isinstance(row, dict) and float(row.get("score", 0) or 0) < 65
            ),
            key=lambda row: float(row.get("score", 0) or 0),
        )
        focus_points = [
            _clean_text(row.get("name"), 80)
            for row in weak_rows[:3]
            if _clean_text(row.get("name"), 80)
        ]
        if not focus_points:
            focus_points = [
                _clean_text(value, 80)
                for value in course.get("weak_points", [])[:3]
                if _clean_text(value, 80)
            ]

        styles = preferences.get("content_style")
        content_style = _content_style_tokens(styles if isinstance(styles, list) else [])
        goal = _clean_text(preferences.get("goal"), 120) or "概念理解"
        if focus_points:
            reason = (
                f"结合“{goal}”目标，并优先补强近期掌握度较低的"
                f"{'、'.join(focus_points)}。"
            )
        else:
            reason = f"当前课程暂无稳定薄弱点，按“{goal}”目标和学习偏好组织内容。"

        return {
            "strategy_version": 1,
            "course_id": course_id,
            "course_name": _clean_text(course_name, 120) or "通用课程",
            "explanation_depth": explanation_depth,
            "content_style": content_style,
            "quiz_difficulty": quiz_difficulty,
            "feedback_style": feedback_style,
            "focus_knowledge_points": focus_points,
            "avoid": ["直接给出完整答案"] if feedback_style != "direct" else [],
            "reason": reason,
            "profile_updated_at": _clean_text(profile.get("updated_at"), 40),
        }

    def normalize_knowledge_points(
        self,
        raw_points: list[Any],
        course_profile: dict[str, Any] | None = None,
        context: str = "",
    ) -> list[dict[str, Any]]:
        course_profile = course_profile or {}
        mastery = (
            course_profile.get("mastery")
            if isinstance(course_profile.get("mastery"), dict)
            else {}
        )
        existing: list[dict[str, Any]] = []
        for point_id, row in mastery.items():
            if not isinstance(row, dict):
                continue
            name = _clean_text(row.get("name"), 80)
            if name:
                existing.append(
                    {
                        "knowledge_point_id": point_id,
                        "name": name,
                        "parent_name": _clean_text(row.get("parent_name"), 80),
                    }
                )

        cleaned_points: list[str] = []
        for value in raw_points:
            text = _clean_text(value, 80)
            if text and text not in cleaned_points:
                cleaned_points.append(text)

        llm_rows = self._llm_normalize_points(cleaned_points, existing, context)
        llm_by_raw = {
            _compact_key(row.get("raw_name") or row.get("name")): row
            for row in llm_rows
            if isinstance(row, dict)
        }
        result: list[dict[str, Any]] = []
        for raw_name in cleaned_points:
            matched = self._match_existing_point(raw_name, existing)
            llm_row = llm_by_raw.get(_compact_key(raw_name), {})
            suggested_name = _clean_text(llm_row.get("name"), 80) or raw_name
            suggested_parent = _clean_text(llm_row.get("parent_name"), 80)
            if matched is None and llm_row.get("existing_id") in mastery:
                matched = next(
                    (
                        row
                        for row in existing
                        if row["knowledge_point_id"] == llm_row.get("existing_id")
                    ),
                    None,
                )
            if matched:
                row = {
                    **matched,
                    "raw_name": raw_name,
                    "confidence": 0.9,
                    "is_new": False,
                }
            else:
                row = {
                    "knowledge_point_id": build_knowledge_point_id(
                        suggested_name,
                        suggested_parent,
                    ),
                    "name": suggested_name,
                    "parent_name": suggested_parent,
                    "raw_name": raw_name,
                    "confidence": float(llm_row.get("confidence", 0.6) or 0.6),
                    "is_new": True,
                }
            result.append(row)
        return result

    def _match_existing_point(
        self,
        raw_name: str,
        existing: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        raw_key = _compact_key(raw_name)
        best: tuple[float, dict[str, Any] | None] = (0.0, None)
        for row in existing:
            candidate_key = _compact_key(row.get("name"))
            if raw_key == candidate_key:
                return row
            score = SequenceMatcher(None, raw_key, candidate_key).ratio()
            if score > best[0]:
                best = (score, row)
        return best[1] if best[0] >= 0.78 else None

    def _llm_normalize_points(
        self,
        raw_points: list[str],
        existing: list[dict[str, Any]],
        context: str,
    ) -> list[dict[str, Any]]:
        if not self.llm_call or not raw_points:
            return []
        prompt = {
            "context": _clean_text(context, 1200),
            "raw_points": raw_points,
            "existing_points": existing,
            "requirements": [
                "返回 JSON 数组",
                "每项包含 raw_name/name/parent_name/confidence",
                "能匹配已有知识点时填写 existing_id",
                "名称保持课程通用且简洁",
            ],
        }
        try:
            raw = self.llm_call(
                messages=[
                    {
                        "role": "system",
                        "content": "你负责课程知识点提取和归一化，只输出严格 JSON。",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt, ensure_ascii=False),
                    },
                ],
                temperature=0.1,
                max_tokens=1800,
            )
            payload = _extract_json(raw)
            rows = payload.get("knowledge_points", []) if isinstance(payload, dict) else payload
            return rows if isinstance(rows, list) else []
        except Exception:
            return []

    def collect_evidence_observations(
        self,
        profile: dict[str, Any],
        classroom: dict[str, Any],
        report: dict[str, Any],
        events: list[dict[str, Any]],
        normalized_points: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        course_name = (
            _clean_text(classroom.get("course"), 120)
            or _clean_text(classroom.get("topic"), 120)
            or "通用课程"
        )
        course_id = build_course_id(course_name)
        course = (
            profile.get("courses", {}).get(course_id, {})
            if isinstance(profile.get("courses"), dict)
            else {}
        )
        raw_points = list((report.get("knowledge_summary") or {}).keys())
        normalized = normalized_points or self.normalize_knowledge_points(
            raw_points,
            course,
            context=f"{course_name} {_clean_text(classroom.get('topic'), 120)}",
        )
        normalized_by_raw = {row["raw_name"]: row for row in normalized}
        event_by_id = {
            str(event.get("id")): event
            for event in events
            if isinstance(event, dict) and event.get("id")
        }
        observations: list[dict[str, Any]] = []
        for raw_name, summary in (report.get("knowledge_summary") or {}).items():
            if not isinstance(summary, dict):
                continue
            evidence_ids = sorted(
                {
                    str(event_id)
                    for event_id in summary.get("event_ids", [])
                    if str(event_id) in event_by_id
                }
            )
            question_total = int(summary.get("total", 0) or 0)
            if question_total <= 0 or not evidence_ids:
                continue

            normalized_point = normalized_by_raw.get(raw_name) or {
                "knowledge_point_id": build_knowledge_point_id(raw_name),
                "name": raw_name,
                "parent_name": "",
            }
            point_id = normalized_point["knowledge_point_id"]
            observed = max(0, min(100, int(round(float(summary.get("mastery", 0) or 0)))))
            source_id = _stable_id(
                "evidence",
                classroom.get("id"),
                point_id,
                *evidence_ids,
                length=16,
            )
            observations.append(
                {
                    "source_id": source_id,
                    "course_id": course_id,
                    "course_name": course_name,
                    "classroom_id": _clean_text(classroom.get("id"), 128),
                    "knowledge_point_id": point_id,
                    "knowledge_point_name": normalized_point["name"],
                    "parent_name": normalized_point.get("parent_name", ""),
                    "score": observed,
                    "question_total": question_total,
                    "evidence_ids": evidence_ids,
                    "created_at": self.now_provider(),
                }
            )
        return observations

    def analyze_learning_evidence(
        self,
        profile: dict[str, Any],
        classroom: dict[str, Any],
        report: dict[str, Any],
        events: list[dict[str, Any]],
        observations: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        current_observations = observations or self.collect_evidence_observations(
            profile,
            classroom,
            report,
            events,
        )
        courses = profile.get("courses") if isinstance(profile.get("courses"), dict) else {}
        evidence_buffer = (
            profile.get("evidence_buffer")
            if isinstance(profile.get("evidence_buffer"), dict)
            else {}
        )
        proposals: list[dict[str, Any]] = []
        for current in current_observations:
            course_id = current["course_id"]
            point_id = current["knowledge_point_id"]
            course = courses.get(course_id, {}) if isinstance(courses.get(course_id), dict) else {}
            point_buffer = (
                evidence_buffer.get(course_id, {}).get(point_id, {})
                if isinstance(evidence_buffer.get(course_id), dict)
                else {}
            )
            buffered_rows = (
                point_buffer.get("observations", [])
                if isinstance(point_buffer, dict)
                else []
            )
            combined_by_source = {
                row.get("source_id"): row
                for row in buffered_rows
                if isinstance(row, dict) and row.get("source_id")
            }
            combined_by_source[current["source_id"]] = current
            combined = list(combined_by_source.values())
            question_total = sum(
                int(row.get("question_total", 0) or 0)
                for row in combined
            )
            evidence_ids = sorted(
                {
                    str(event_id)
                    for row in combined
                    for event_id in row.get("evidence_ids", [])
                    if str(event_id)
                }
            )
            if question_total < 2 or len(evidence_ids) < 2:
                continue
            weighted_total = sum(
                float(row.get("score", 0) or 0)
                * int(row.get("question_total", 0) or 0)
                for row in combined
            )
            observed = max(
                0,
                min(100, round(weighted_total / question_total)),
            )
            existing = (course.get("mastery") or {}).get(point_id, {})
            before = int(round(float(existing.get("score", 50) or 50)))
            after = max(0, min(100, round(before * 0.35 + observed * 0.65)))
            confidence = min(
                0.95,
                round(0.45 + min(question_total, 5) * 0.06 + min(len(evidence_ids), 5) * 0.08, 2),
            )
            proposal_id = _stable_id(
                "update",
                course_id,
                point_id,
                *evidence_ids,
                length=16,
            )
            direction = "提升" if after > before else "下调" if after < before else "保持"
            proposals.append(
                {
                    "id": proposal_id,
                    "course_id": course_id,
                    "course_name": current["course_name"],
                    "classroom_id": _clean_text(classroom.get("id"), 128),
                    "type": "mastery_adjustment",
                    "knowledge_point_id": point_id,
                    "knowledge_point_name": current["knowledge_point_name"],
                    "parent_name": current.get("parent_name", ""),
                    "before": before,
                    "after": after,
                    "observed_score": observed,
                    "confidence": confidence,
                    "reason": (
                        f"累计课堂证据覆盖 {question_total} 道题，"
                        f"观测掌握度为 {observed}%，建议{direction}课程掌握度。"
                    ),
                    "evidence_ids": evidence_ids,
                    "status": "pending",
                    "created_at": self.now_provider(),
                }
            )
        return proposals
