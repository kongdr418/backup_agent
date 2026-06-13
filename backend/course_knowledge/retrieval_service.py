from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any

from .config import (
    KEYWORD_WEIGHT,
    MAX_EVIDENCE_RESULTS,
    MAX_KNOWLEDGE_POINTS,
    MAX_LESSONS,
    MIN_COURSE_MATCH_SCORE,
    MIN_HYBRID_SCORE,
    MIN_VECTOR_SCORE,
    STRONG_KEYWORD_SCORE,
    VECTOR_WEIGHT,
)
from .storage import CourseKnowledgeStorage


logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    return re.sub(r"[\s　]+", " ", text.strip().lower())


def _search_terms(text: str) -> set[str]:
    normalized = _normalize(text)
    terms = {
        token
        for token in re.findall(r"[a-z0-9+#.]+", normalized)
        if len(token) >= 2
    }
    for sequence in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(sequence) <= 2:
            terms.add(sequence)
            continue
        terms.update(sequence[index:index + 2] for index in range(len(sequence) - 1))
    return terms


def _keyword_overlap(query: str, keywords: list[str]) -> float:
    if not query or not keywords:
        return 0.0
    query_tokens = _search_terms(query)
    if not query_tokens:
        return 0.0
    searchable = " ".join(_normalize(str(keyword)) for keyword in keywords if keyword)
    matched = sum(1 for token in query_tokens if token in searchable)
    return matched / len(query_tokens)


def _empty_context(course_name: str = "") -> dict[str, Any]:
    return {
        "course_id": "",
        "course_name": course_name,
        "summary": "",
        "knowledge_points": [],
        "lessons": [],
        "evidence": [],
    }


PPT_KNOWLEDGE_TITLE = "## 课程知识库参考"


class CourseKnowledgeRetriever:
    def __init__(
        self,
        backend_dir: str,
        storage: CourseKnowledgeStorage | None = None,
        vector_index: Any | None = None,
    ) -> None:
        self.backend_dir = backend_dir
        self.storage = storage or CourseKnowledgeStorage(backend_dir)
        self.vector_index = vector_index

    def build_ppt_knowledge_notes(
        self,
        user_id: str,
        course: str = "",
        topic: str = "",
    ) -> str:
        context = self.retrieve_course_context(user_id, course, topic)
        course_name = context.get("course_name", "")
        summary = context.get("summary", "")
        knowledge_points = context.get("knowledge_points", [])
        lessons = context.get("lessons", [])

        if not knowledge_points and not lessons:
            return ""

        parts = [PPT_KNOWLEDGE_TITLE]
        if course_name:
            parts.append(f"课程名称：{course_name}")
        if summary:
            parts.append(f"课程简介：{summary}")

        if knowledge_points:
            parts.append("\n核心知识点（请确保PPT内容覆盖以下要点）：")
            for kp in knowledge_points[:8]:
                label = kp.get("label", "")
                if label:
                    parts.append(f"- {label}")

        if lessons:
            parts.append("\n相关课次（按此顺序组织内容）：")
            for lesson in lessons[:6]:
                title = lesson.get("title", "")
                if title:
                    parts.append(f"- {title}")

        parts.append(
            "\n请确保PPT内容覆盖以上知识点，并按课程大纲逻辑组织内容结构。"
            "不要将知识库元信息直接展示在幻灯片正文中。"
        )
        return "\n".join(parts)

    def retrieve_course_context(
        self,
        user_id: str,
        course: str = "",
        topic: str = "",
    ) -> dict[str, Any]:
        course_map = self.storage.load_course_map(user_id)
        courses = course_map.get("courses", [])

        query_course = course or topic
        if not query_course:
            logger.info("[BGE] search_skipped reason=course_missing")
            return _empty_context(course)

        matched_course = self._find_best_course(courses, query_course)
        if not matched_course:
            # 跨课程兜底：用 topic 在所有课程中做向量搜索
            if topic and courses:
                best = self._search_across_courses(user_id, courses, topic)
                if best:
                    logger.info(
                        "[BGE] cross_course_fallback topic=%s matched_course=%s",
                        topic,
                        best.get("course_name", ""),
                    )
                    matched_course = best
            if not matched_course:
                logger.info(
                    "[BGE] search_skipped reason=course_not_matched available_courses=%d",
                    len(courses),
                )
                return _empty_context(course)

        course_id = matched_course.get("course_id", "")
        catalog = self.storage.load_course_catalog(user_id, course_id) or {}
        chunks = self.storage.load_chunk_index(user_id, course_id)

        if topic:
            ranked_chunks = self._rank_chunks(user_id, course_id, chunks, topic)
            if not ranked_chunks:
                return _empty_context(course)
            evidence = self._evidence_from_ranked_chunks(
                ranked_chunks,
                matched_course.get("course_name", ""),
            )
            matched_points = self._points_from_ranked_chunks(
                matched_course.get("knowledge_points", []),
                ranked_chunks,
                topic,
            )
            matched_lessons = self._lessons_from_ranked_chunks(
                matched_course.get("lessons", []),
                ranked_chunks,
                topic,
            )
        else:
            logger.info(
                "[BGE] search_skipped reason=topic_missing course_id=%s",
                course_id,
            )
            matched_points = self._match_knowledge_points(
                matched_course.get("knowledge_points", []),
                topic,
            )
            matched_lessons = self._match_lessons(
                matched_course.get("lessons", []),
                topic,
            )
            evidence = self._build_evidence(
                chunks,
                topic,
                matched_course.get("course_name", ""),
            )

        return {
            "course_id": course_id,
            "course_name": matched_course.get("course_name", course),
            "summary": matched_course.get("summary", ""),
            "knowledge_points": matched_points[:MAX_KNOWLEDGE_POINTS],
            "lessons": matched_lessons[:MAX_LESSONS],
            "evidence": evidence[:MAX_EVIDENCE_RESULTS],
        }

    def _rank_chunks(
        self,
        user_id: str,
        course_id: str,
        chunks: list[dict[str, Any]],
        topic: str,
    ) -> list[tuple[float, float, float, dict[str, Any]]]:
        keyword_scores = {
            str(chunk.get("chunk_id", "")): _keyword_overlap(
                topic,
                [
                    chunk.get("section", ""),
                    chunk.get("text", ""),
                    *chunk.get("keywords", []),
                ],
            )
            for chunk in chunks
        }
        vector_scores: dict[str, float] = {}
        if self.vector_index is not None:
            try:
                vector_scores = self.vector_index.query_scores(
                    user_id,
                    course_id,
                    chunks,
                    topic,
                )
            except Exception as exc:
                logger.warning(
                    "[BGE] vector_search_failed course_id=%s "
                    "fallback=keyword error=%s",
                    course_id,
                    type(exc).__name__,
                )

        ranked: list[tuple[float, float, float, dict[str, Any]]] = []
        vector_available = bool(vector_scores)
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id", ""))
            keyword_score = max(0.0, min(1.0, keyword_scores.get(chunk_id, 0.0)))
            vector_score = max(0.0, min(1.0, vector_scores.get(chunk_id, 0.0)))
            hybrid_score = (
                vector_score * VECTOR_WEIGHT
                + keyword_score * KEYWORD_WEIGHT
                if vector_available
                else keyword_score
            )
            accepted = (
                keyword_score >= STRONG_KEYWORD_SCORE
                or (
                    vector_available
                    and vector_score >= MIN_VECTOR_SCORE
                    and hybrid_score >= MIN_HYBRID_SCORE
                )
                or (not vector_available and keyword_score > 0)
            )
            if accepted:
                ranked.append((hybrid_score, vector_score, keyword_score, chunk))
        ranked.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
        top_score = ranked[0][0] if ranked else 0.0
        logger.info(
            "[BGE] hybrid_search_complete course_id=%s candidates=%d "
            "matches=%d mode=%s top_score=%.4f",
            course_id,
            len(chunks),
            len(ranked),
            "hybrid" if vector_available else "keyword",
            top_score,
        )
        return ranked

    def _evidence_from_ranked_chunks(
        self,
        ranked_chunks: list[tuple[float, float, float, dict[str, Any]]],
        course_name: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                "chunk_id": chunk.get("chunk_id", ""),
                "chunk_type": chunk.get("chunk_type", ""),
                "section": chunk.get("section", ""),
                "text": chunk.get("text", ""),
                "keywords": list(chunk.get("keywords", [])),
                "knowledge_point_ids": list(chunk.get("knowledge_point_ids", [])),
                "evidence_label": chunk.get("evidence_label", ""),
                "source_name": course_name,
                "relevance_score": round(hybrid_score, 4),
                "vector_score": round(vector_score, 4),
                "keyword_score": round(keyword_score, 4),
            }
            for hybrid_score, vector_score, keyword_score, chunk in ranked_chunks
        ]

    def _points_from_ranked_chunks(
        self,
        knowledge_points: list[dict[str, Any]],
        ranked_chunks: list[tuple[float, float, float, dict[str, Any]]],
        topic: str,
    ) -> list[dict[str, Any]]:
        point_ids = {
            str(point_id)
            for _, _, _, chunk in ranked_chunks
            for point_id in chunk.get("knowledge_point_ids", [])
            if point_id
        }
        searchable = " ".join(
            " ".join(
                [
                    str(chunk.get("section", "")),
                    str(chunk.get("text", "")),
                    *[str(item) for item in chunk.get("keywords", [])],
                ]
            )
            for _, _, _, chunk in ranked_chunks
        )
        results = [
            {
                "knowledge_point_id": kp.get("knowledge_point_id", ""),
                "label": kp.get("label", ""),
            }
            for kp in knowledge_points
            if kp.get("knowledge_point_id") in point_ids
            or _keyword_overlap(kp.get("label", ""), [searchable]) > 0
        ]
        return results or self._match_knowledge_points(knowledge_points, topic)

    def _lessons_from_ranked_chunks(
        self,
        lessons: list[dict[str, Any]],
        ranked_chunks: list[tuple[float, float, float, dict[str, Any]]],
        topic: str,
    ) -> list[dict[str, Any]]:
        searchable = " ".join(
            " ".join(
                [
                    str(chunk.get("section", "")),
                    str(chunk.get("text", "")),
                    *[str(item) for item in chunk.get("keywords", [])],
                ]
            )
            for _, _, _, chunk in ranked_chunks
        )
        results = [
            {
                "lesson_id": lesson.get("lesson_id", ""),
                "title": lesson.get("title", ""),
            }
            for lesson in lessons
            if _keyword_overlap(
                " ".join(
                    [
                        str(lesson.get("title", "")),
                        *[str(item) for item in lesson.get("knowledge_points", [])],
                    ]
                ),
                [searchable],
            ) > 0
        ]
        return results or self._match_lessons(lessons, topic)

    def _find_best_course(
        self,
        courses: list[dict[str, Any]],
        course_name: str,
    ) -> dict[str, Any] | None:
        if not courses:
            return None
        if not course_name:
            return None

        normalized_query = _normalize(course_name)
        for course in courses:
            if _normalize(course.get("course_name", "")) == normalized_query:
                return course

        best: dict[str, Any] | None = None
        best_score = 0.0
        for course in courses:
            name = _normalize(course.get("course_name", ""))
            if not name:
                continue
            # 子串包含
            if normalized_query in name or name in normalized_query:
                score = min(len(name), len(normalized_query)) / max(
                    len(name),
                    len(normalized_query),
                    1,
                )
            else:
                # 中文字符重叠（2-gram Jaccard）
                query_ngrams = _search_terms(normalized_query)
                name_ngrams = _search_terms(name)
                if query_ngrams and name_ngrams:
                    overlap = len(query_ngrams & name_ngrams)
                    union = len(query_ngrams | name_ngrams)
                    char_score = overlap / union if union else 0.0
                else:
                    char_score = 0.0
                # SequenceMatcher
                seq_score = SequenceMatcher(None, normalized_query, name).ratio()
                score = max(char_score, seq_score)
            if score >= MIN_COURSE_MATCH_SCORE and score > best_score:
                best_score = score
                best = course
        return best

    def _search_across_courses(
        self,
        user_id: str,
        courses: list[dict[str, Any]],
        topic: str,
    ) -> dict[str, Any] | None:
        """当课程名匹配失败时，用 topic 在所有课程中做向量搜索，返回最佳匹配的课程。"""
        best_course: dict[str, Any] | None = None
        best_top_score = 0.0
        for course in courses:
            course_id = course.get("course_id", "")
            if not course_id:
                continue
            chunks = self.storage.load_chunk_index(user_id, course_id)
            if not chunks:
                continue
            ranked = self._rank_chunks(user_id, course_id, chunks, topic)
            if not ranked:
                continue
            top_score = ranked[0][0] if ranked else 0.0
            if top_score > best_top_score:
                best_top_score = top_score
                best_course = course
        return best_course

    def _match_knowledge_points(
        self,
        knowledge_points: list[dict[str, Any]],
        topic: str,
    ) -> list[dict[str, Any]]:
        if not knowledge_points:
            return []

        if not topic:
            return [
                {
                    "knowledge_point_id": kp.get("knowledge_point_id", ""),
                    "label": kp.get("label", ""),
                }
                for kp in knowledge_points
            ]

        scored: list[tuple[float, dict[str, Any]]] = []
        for kp in knowledge_points:
            label = kp.get("label", "")
            score = _keyword_overlap(topic, [label])
            scored.append((score, kp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "knowledge_point_id": kp.get("knowledge_point_id", ""),
                "label": kp.get("label", ""),
            }
            for score, kp in scored
            if score > 0
        ]

    def _match_lessons(
        self,
        lessons: list[dict[str, Any]],
        topic: str,
    ) -> list[dict[str, Any]]:
        if not lessons:
            return []

        if not topic:
            return [
                {
                    "lesson_id": lesson.get("lesson_id", ""),
                    "title": lesson.get("title", ""),
                }
                for lesson in lessons
            ]

        scored: list[tuple[float, dict[str, Any]]] = []
        for lesson in lessons:
            title = lesson.get("title", "")
            kp_labels = lesson.get("knowledge_points", [])
            score = _keyword_overlap(topic, [title] + kp_labels)
            scored.append((score, lesson))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "lesson_id": lesson.get("lesson_id", ""),
                "title": lesson.get("title", ""),
            }
            for score, lesson in scored
            if score > 0
        ]

    def _build_evidence(
        self,
        chunks: list[dict[str, Any]],
        topic: str,
        course_name: str,
    ) -> list[dict[str, Any]]:
        if not chunks:
            return []

        if not topic:
            return [
                {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "chunk_type": chunk.get("chunk_type", ""),
                    "section": chunk.get("section", ""),
                    "text": chunk.get("text", ""),
                    "evidence_label": chunk.get("evidence_label", ""),
                    "source_name": course_name,
                }
                for chunk in chunks
            ]

        scored: list[tuple[float, dict[str, Any]]] = []
        for chunk in chunks:
            text = chunk.get("text", "")
            keywords = chunk.get("keywords", [])
            score = _keyword_overlap(topic, [text] + keywords)
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "chunk_id": chunk.get("chunk_id", ""),
                "chunk_type": chunk.get("chunk_type", ""),
                "section": chunk.get("section", ""),
                "text": chunk.get("text", ""),
                "evidence_label": chunk.get("evidence_label", ""),
                "source_name": course_name,
            }
            for score, chunk in scored
            if score > 0
        ]
