from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


SemanticReviewer = Callable[[dict[str, Any]], dict[str, Any]]

_VALID_MODES = {"off", "standard", "strict"}
_PROFILE_LEAK_PATTERNS = (
    re.compile(r"\bevidence_ids?\b", re.I),
    re.compile(r"\bgeneration_strategy\b", re.I),
    re.compile(r"\bconfirmed\b", re.I),
    re.compile(r"\bpending_updates?\b", re.I),
    re.compile(r"\bprofile[_\s-]*(?:status|version|confidence)\b", re.I),
    re.compile(r"(正式画像状态|未经确认的标签|内部画像字段)"),
)
_SEMANTIC_REVIEW_TRIGGERS = {
    "unsupported_knowledge_point",
}
_SEMANTIC_OVERRIDABLE_ISSUES = {"unsupported_knowledge_point"}


def normalize_critic_mode(value: Any) -> str:
    mode = str(value or "standard").strip().lower()
    return mode if mode in _VALID_MODES else "standard"


def _clean_text(value: Any, limit: int = 1200) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _contains_profile_leakage(text: str) -> bool:
    return any(pattern.search(text) for pattern in _PROFILE_LEAK_PATTERNS)


def _compact_key(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").lower(), flags=re.UNICODE)


def _extract_claimed_correct_answers(analysis: str) -> set[str]:
    text = str(analysis or "").upper()
    claimed: set[str] = set()
    patterns = (
        r"(?:正确答案|答案)\s*(?:是|为)?\s*[：:]?\s*([A-D](?:\s*[,，、和及]\s*[A-D])*)",
        r"(?:因此|所以|故)\s*[，,：:]?\s*([A-D])\s*(?:项)?\s*(?:是|为)?\s*正确",
        r"([A-D])\s*(?:项)?\s*(?:才是|是|为)\s*正确答案",
    )
    for pattern in patterns:
        for match in re.findall(pattern, text):
            claimed.update(re.findall(r"[A-D]", match))
    return claimed


@dataclass(frozen=True)
class GroundingContext:
    level: str
    texts: tuple[str, ...] = ()
    source_count: int = 0

    @property
    def combined_text(self) -> str:
        return "\n".join(self.texts)

    def supports(self, value: Any) -> bool:
        needle = _compact_key(value)
        if not needle:
            return False
        haystack = _compact_key(self.combined_text)
        if not haystack:
            return False
        return needle in haystack or any(
            len(part) >= 2 and part in haystack
            for part in re.split(r"[\s，。；、：:（）()\-]+", str(value or ""))
        )


@dataclass
class CriticResult:
    passed: bool
    severity: str = "none"
    issue_codes: list[str] = field(default_factory=list)
    grounding_level: str = "none"
    duration_ms: int = 0
    retry_required: bool = False
    fallback_required: bool = False
    llm_checked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_grounding_context(
    *,
    knowledge_context: dict[str, Any] | None,
    visible_texts: list[str] | tuple[str, ...] | None,
    manuscript_note: str,
) -> GroundingContext:
    knowledge_texts: list[str] = []
    if isinstance(knowledge_context, dict):
        for point in knowledge_context.get("knowledge_points", []):
            if isinstance(point, dict):
                text = point.get("label") or point.get("name")
            else:
                text = point
            cleaned = _clean_text(text, 300)
            if cleaned:
                knowledge_texts.append(cleaned)
        for evidence in knowledge_context.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            cleaned = _clean_text(
                evidence.get("text") or evidence.get("text_excerpt"),
                800,
            )
            if cleaned:
                knowledge_texts.append(cleaned)
    ppt_texts = [
        cleaned
        for value in (visible_texts or [])
        if (cleaned := _clean_text(value, 500))
    ]
    note = _clean_text(manuscript_note, 1200)
    if knowledge_texts:
        combined = [*knowledge_texts[:20], *ppt_texts[:30]]
        if note:
            combined.append(note)
        rows = tuple(dict.fromkeys(combined))
        return GroundingContext("knowledge_base", rows, len(rows))

    if ppt_texts:
        rows = tuple(dict.fromkeys(ppt_texts[:30]))
        if note:
            rows = (*rows, note)
        return GroundingContext("ppt", rows, len(rows))

    if note:
        return GroundingContext("manuscript", (note,), 1)
    return GroundingContext("none")


def content_llm_semantic_reviewer(
    payload: dict[str, Any],
    *,
    llm_call: Callable[..., str] | None = None,
    llm_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if llm_call is None:
        from generators.shared_config import content_llm_call

        llm_call = content_llm_call

    config = llm_config or {}
    raw = llm_call(
        messages=[
            {
                "role": "system",
                "content": (
                    "你是智慧课堂内容审查器。只判断内容是否得到给定依据支持，"
                    "以及题目、答案和解析是否语义一致。不要生成新内容。"
                    "只返回 JSON："
                    '{"passed": true, "issues": ["短问题说明"]}。'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"类型：{payload.get('kind', '')}\n"
                    f"依据等级：{payload.get('grounding_level', '')}\n"
                    f"依据：{_clean_text(payload.get('grounding'), 4000)}\n"
                    "待审查内容："
                    f"{_clean_text(json.dumps(payload.get('content'), ensure_ascii=False), 5000)}"
                ),
            },
        ],
        temperature=0.1,
        max_tokens=1500,
        model=config.get("content_model", ""),
        api_key=config.get("content_api_key", ""),
        base_url=config.get("content_base_url", ""),
        provider_type=config.get("content_provider_type", ""),
    )
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("semantic critic must return an object")
    return {
        "passed": bool(data.get("passed")),
        "issues": data.get("issues", []) if isinstance(data.get("issues"), list) else [],
    }


def build_content_llm_semantic_reviewer(
    llm_config: dict[str, Any] | None = None,
    *,
    llm_call: Callable[..., str] | None = None,
) -> SemanticReviewer:
    config = dict(llm_config or {})

    def review(payload: dict[str, Any]) -> dict[str, Any]:
        return content_llm_semantic_reviewer(
            payload,
            llm_call=llm_call,
            llm_config=config,
        )

    return review


class ClassroomCriticService:
    def __init__(
        self,
        *,
        mode: str = "standard",
        semantic_reviewer: SemanticReviewer | None = None,
    ) -> None:
        self.mode = normalize_critic_mode(mode)
        self.semantic_reviewer = semantic_reviewer

    def review_teaching_segments(
        self,
        *,
        segments: list[dict[str, Any]],
        valid_target_ids: set[str],
        grounding: GroundingContext,
    ) -> CriticResult:
        started = time.perf_counter()
        issues: list[str] = []
        if self.mode != "off" and grounding.level == "none":
            issues.append("missing_grounding")
        if not segments:
            issues.append("missing_segments")
        elif len(segments) < 2:
            issues.append("insufficient_segments")
        for segment in segments:
            target_id = str(segment.get("target_id") or "").strip()
            text = _clean_text(segment.get("text"))
            if target_id not in valid_target_ids:
                issues.append("invalid_target")
            if len(text) < 12:
                issues.append("segment_too_short")
            if _contains_profile_leakage(text):
                issues.append("profile_leakage")
        return self._finish_review(
            started=started,
            grounding=grounding,
            issues=issues,
            payload={"kind": "teaching_segments", "segments": segments},
        )

    def review_quiz_questions(
        self,
        *,
        questions: list[dict[str, Any]],
        grounding: GroundingContext,
    ) -> CriticResult:
        started = time.perf_counter()
        issues: list[str] = []
        if self.mode != "off" and grounding.level == "none":
            issues.append("missing_grounding")
        if not questions:
            issues.append("missing_questions")
        for question in questions:
            question_text = _clean_text(question.get("question"))
            analysis = _clean_text(question.get("analysis"))
            knowledge_point = _clean_text(question.get("knowledge_point"), 200)
            combined = f"{question_text}\n{analysis}\n{knowledge_point}"
            if _contains_profile_leakage(combined):
                issues.append("profile_leakage")
            if not question_text:
                issues.append("missing_question_text")
            if not analysis:
                issues.append("missing_analysis")
            if (
                self.mode != "off"
                and knowledge_point
                and not grounding.supports(knowledge_point)
            ):
                issues.append("unsupported_knowledge_point")

            qtype = str(question.get("type") or "single")
            answers = {
                str(value).strip().upper()
                for value in question.get("answer", [])
                if str(value).strip()
            }
            if qtype == "short_answer":
                if not _clean_text(
                    question.get("reference_answer") or question.get("analysis")
                ):
                    issues.append("missing_reference_answer")
                continue

            options = question.get("options", [])
            option_values = {
                str(row.get("value") or "").strip().upper()
                for row in options
                if isinstance(row, dict)
            }
            if len(options) != 4 or len(option_values) != 4:
                issues.append("invalid_options")
            if not answers or not answers.issubset(option_values):
                issues.append("invalid_answer")
            if qtype == "single" and len(answers) != 1:
                issues.append("single_answer_count")
            if qtype == "multiple" and len(answers) < 2:
                issues.append("multiple_answer_count")
            claimed_correct = _extract_claimed_correct_answers(analysis)
            if (
                len(answers) == 1
                and claimed_correct
                and claimed_correct != answers
            ):
                issues.append("answer_analysis_conflict")
        return self._finish_review(
            started=started,
            grounding=grounding,
            issues=issues,
            payload={"kind": "quiz_questions", "questions": questions},
        )

    def review_short_answer_grade(
        self,
        *,
        grade: dict[str, Any],
        reference_answer: str,
        student_answer: str,
    ) -> CriticResult:
        started = time.perf_counter()
        issues: list[str] = []
        score = grade.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            issues.append("invalid_score")
        elif score < 0 or score > 100:
            issues.append("invalid_score")
        feedback = _clean_text(grade.get("feedback"))
        if not feedback:
            issues.append("missing_feedback")
        support_text = _compact_key(f"{reference_answer} {student_answer}")
        for point in grade.get("covered_points", []):
            point_key = _compact_key(point)
            if point_key and point_key not in support_text:
                issues.append("unsupported_covered_point")
                break
        return self._finish_review(
            started=started,
            grounding=GroundingContext("reference"),
            issues=issues,
            payload={"kind": "short_answer_grade", "grade": grade},
        )

    def _finish_review(
        self,
        *,
        started: float,
        grounding: GroundingContext,
        issues: list[str],
        payload: dict[str, Any],
    ) -> CriticResult:
        unique_issues = list(dict.fromkeys(issues))
        should_semantic_review = (
            self.semantic_reviewer is not None
            and (
                self.mode == "strict"
                or (
                    self.mode == "standard"
                    and bool(set(unique_issues) & _SEMANTIC_REVIEW_TRIGGERS)
                )
            )
        )
        if should_semantic_review:
            try:
                semantic = self.semantic_reviewer(
                    {
                        "kind": payload["kind"],
                        "grounding_level": grounding.level,
                        "grounding": grounding.combined_text[:4000],
                        "content": payload.get("segments")
                        or payload.get("questions")
                        or payload.get("grade"),
                    }
                )
            except Exception:
                return self._result(
                    started,
                    grounding,
                    [*unique_issues, "semantic_critic_error"],
                    llm_checked=True,
                    fallback_required=True,
                )
            semantic_issues = [
                _clean_text(value, 80)
                for value in semantic.get("issues", [])
                if _clean_text(value, 80)
            ]
            if semantic.get("passed") is False and not semantic_issues:
                semantic_issues = ["semantic_rejected"]
            if unique_issues:
                # 语义 Critic 只负责确认语义类疑点；确定性结构/泄露问题不可覆盖。
                hard_issues = [
                    issue
                    for issue in unique_issues
                    if issue not in _SEMANTIC_OVERRIDABLE_ISSUES
                ]
                if semantic.get("passed") is True:
                    semantic_issues = hard_issues
                else:
                    semantic_issues = [
                        *hard_issues,
                        *[
                            issue
                            for issue in unique_issues
                            if issue in _SEMANTIC_OVERRIDABLE_ISSUES
                        ],
                        *semantic_issues,
                    ]
            return self._result(
                started,
                grounding,
                semantic_issues,
                llm_checked=True,
            )
        if unique_issues:
            return self._result(started, grounding, unique_issues)
        return self._result(started, grounding, [])

    @staticmethod
    def _result(
        started: float,
        grounding: GroundingContext,
        issues: list[str],
        *,
        llm_checked: bool = False,
        fallback_required: bool = False,
    ) -> CriticResult:
        failed = bool(issues)
        return CriticResult(
            passed=not failed,
            severity="error" if failed else "none",
            issue_codes=list(dict.fromkeys(issues))[:20],
            grounding_level=grounding.level,
            duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
            retry_required=failed,
            fallback_required=fallback_required,
            llm_checked=llm_checked,
        )
