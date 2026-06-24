from __future__ import annotations

import asyncio
import os
import re
import json
from datetime import datetime
from difflib import SequenceMatcher
from html import unescape
from typing import Any, Callable
from uuid import uuid4

from .critic_service import (
    ClassroomCriticService,
    CriticResult,
    build_grounding_context,
    normalize_critic_mode,
)
from .schema import ClassroomAction, ClassroomScene, InteractiveClassroom
from .storage import ClassroomStorage
from .tts_service import (
    DEFAULT_TTS_MAX_CONCURRENCY,
    ClassroomTTSService,
    synthesize_actions_parallel_with_progress,
)

from .generation_progress import (
    CancelCheck,
    ProgressCallback,
    _emit_progress,
    _raise_if_cancelled,
)
from .scene_content import (
    _clean_knowledge_point,
    _clean_quiz_text,
    _clean_text,
    _conceptual_distractors,
    _is_decorative_quiz_text,
    _is_meta_practice_question_text,
    _is_quiz_source_scene,
    _normalize_student_profile,
    _practice_evidence_by_point,
    _question,
    _question_has_scene_index,
    _quiz_points_from_scene,
    _scene_text_snippets,
    _scene_text_values,
    _student_profile_hint,
)

class QuizSceneBuilderMixin:
    def _build_quiz_questions(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        max_questions: int = 5,
        qid_prefix: str = "q",
    ) -> list[dict[str, Any]]:
        slide_scenes = [scene for scene in scenes if scene.type == "slide"]
        # 过滤开场/目录页，避免生成无意义题目
        eligible_scenes = [
            s for i, s in enumerate(slide_scenes)
            if _is_quiz_source_scene(s, is_first_slide=(i == 0))
        ]
        if not eligible_scenes:
            # 兜底：如果全部被过滤，跳过第一页使用剩余页面
            eligible_scenes = slide_scenes[1:] if len(slide_scenes) > 1 else slide_scenes
        titles = [
            scene.title
            for scene in eligible_scenes
            if scene.title and not _is_decorative_quiz_text(scene.title)
        ]
        all_points: list[str] = []
        for scene in eligible_scenes:
            all_points.extend(_quiz_points_from_scene(scene))

        questions: list[dict[str, Any]] = []
        for scene in eligible_scenes[:3]:
            key_points = _quiz_points_from_scene(scene)
            snippets = _scene_text_snippets(scene)
            primary_point = key_points[0] if key_points else (
                scene.title if scene.title and not _is_decorative_quiz_text(scene.title) else topic
            )
            other_points = [
                point
                for point in [*all_points, *titles]
                if point and point not in {primary_point, scene.title} and not _is_decorative_quiz_text(point)
            ]

            if snippets:
                correct = snippets[0]
                distractors = _conceptual_distractors(
                    correct,
                    scene_title=scene.title,
                    topic=topic,
                    pool=[*snippets[1:], *other_points],
                )
                questions.append(
                    _question(
                        qid=f"{qid_prefix}{len(questions) + 1}",
                        question=f"根据课堂对“{primary_point}”的讲解，哪一项最能说明它的判断依据？",
                        correct=correct,
                        distractors=distractors,
                        analysis=f"这道题考查的是对“{primary_point}”相关概念和条件的理解，而不是记住页面标题。",
                        knowledge_point=primary_point,
                    )
                )

            if key_points and len(questions) < max_questions:
                correct = (
                    f"先识别{primary_point}的适用条件，再结合题目情境选择相应概念或处理步骤"
                )
                distractors = _conceptual_distractors(
                    correct,
                    scene_title=scene.title,
                    topic=topic,
                    pool=other_points,
                )
                questions.append(
                    _question(
                        qid=f"{qid_prefix}{len(questions) + 1}",
                        question=f"分析“{primary_point}”相关题目时，应该优先完成哪一个应用步骤？",
                        correct=correct,
                        distractors=distractors,
                        analysis=f"这类题需要先识别“{primary_point}”的适用条件，再结合题目情境判断。",
                        knowledge_point=primary_point,
                    )
                )

            if len(questions) >= max_questions:
                break

        if questions:
            return questions[:max_questions]

        return [
            _question(
                qid=f"{qid_prefix}1",
                question=f"本节《{topic}》课堂首先要抓住什么？",
                correct=f"{topic} 的核心概念、适用场景和关键步骤",
                distractors=[
                    "页面颜色和装饰元素",
                    "与主题无关的背景故事",
                    "只背最后一页标题",
                ],
                analysis="交互式课堂的目标是理解本节主题的概念、场景和关键步骤，而不是记住页面形式。",
                knowledge_point=topic,
            )
        ]

    def _get_quiz_generator(self) -> Any:
        if self.quiz_generator is not None:
            return self.quiz_generator
        from generators.quiz_generator import QuizGenerator

        self.quiz_generator = QuizGenerator()
        return self.quiz_generator

    def _build_slide_summaries(self, scenes: list[ClassroomScene]) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for scene in scenes:
            content = scene.content or {}
            extracted = content.get("extracted_text", [])
            # 抓首条 speech action 的讲稿正文（如果有）—— 讲稿比 SVG 文本更"语义化"
            speech_text = ""
            for action in scene.actions or []:
                if action.type == "speech" and action.text:
                    speech_text = action.text
                    break
            if len(speech_text) > 320:
                speech_text = speech_text[:320].rstrip("，。；、 ") + "…"
            knowledge_points = [
                point for point in _quiz_points_from_scene(scene)
                if not _is_decorative_quiz_text(point)
            ][:8]
            extracted_texts = (
                [
                    _clean_text(str(item))
                    for item in extracted
                    if _clean_text(str(item)) and not _is_decorative_quiz_text(str(item))
                ][:16]
                if isinstance(extracted, list)
                else []
            )
            summaries.append(
                {
                    "scene_id": scene.id,
                    "title": scene.title,
                    "knowledge_points": knowledge_points,
                    "extracted_text": extracted_texts,
                    "speech_excerpt": speech_text,
                }
            )
        return summaries

    def _build_context_quiz_prompt(
        self,
        topic: str,
        slide_summaries: list[dict[str, Any]],
        question_count: int,
        student_profile: dict[str, str] | None = None,
        require_short_answer: bool = False,
    ) -> str:
        context_lines = []
        for idx, slide in enumerate(slide_summaries, start=1):
            title = str(slide.get("title", "")).strip()
            points = [str(p).strip() for p in slide.get("knowledge_points", []) if str(p).strip()]
            texts = [str(t).strip() for t in slide.get("extracted_text", []) if str(t).strip()]
            context_lines.append(
                f"{idx}. 页面标题：{title}\n"
                f"   关键点：{'；'.join(points[:6]) or '无'}\n"
                f"   页面文本：{'；'.join(texts[:10]) or '无'}"
            )
        profile_hint = _student_profile_hint(_normalize_student_profile(student_profile))
        profile_section = f"\n## 学生画像\n{profile_hint}\n" if profile_hint else ""

        # 默认规则：每 4 道题里"可以有" 1 道简答（不强制）
        # 强化规则（require_short_answer=True）：本场必须包含 1 道简答，剩余用单选/多选凑齐
        if require_short_answer:
            short_answer_rule = (
                f"7. **本场强制要求 1 道简答题**：本题共 {question_count} 道，必须包含恰好 1 道简答题，"
                f"剩余 {question_count - 1} 道做单选题。简答题要能让学生写 2-4 句作答，"
                f"必须给 `reference_answer`（2-4 句参考答案）和 `rubric`（3 个以内评分维度）。"
                f"**不要给简答题写 options/answer 字段。**"
                f"如果某知识点不好出 4 选项单选，可以把单选改成「为什么…」「如何判断…"
                f"」「对比 X 与 Y」等开放性判断题，再跟 1 道标准简答搭配。"
            )
        else:
            short_answer_rule = (
                "7. **本场不要求简答题**：不要主动出简答题。如果觉得该知识点确实需要 1 道简答才能测出深度，"
                "才出 1 道（且必须给 `reference_answer` 和 `rubric`）。"
                "**不要每场都加简答**——仅当单选/多选无法覆盖某个深度理解时再加。"
            )

        return f"""请基于下面的课堂页面内容，为《{topic}》生成 {question_count} 道随堂测验题，并以 JSON 返回。

## 课堂页面内容
{chr(10).join(context_lines)}
{profile_section}

## 出题要求
1. 题目必须直接来自上面的页面标题、关键点或页面文本，不能泛泛问主题定义。
1a. `knowledge_point` 必须逐字复制上方某个“页面标题”或“关键点”，禁止自行概括、改写或扩写。
1b. **跳过开场/目录类页面**：如果某些页面的标题是课程名称、目录、欢迎语、自我介绍、学习目标概述等开场性质的内容，不要基于这些页面出题。只围绕有实质知识点的页面出题。
1c. **禁止页面位置匹配题**：不要问"第几页/第几个讲解场景主要围绕什么"、"哪个页面标题是什么"、"某知识点出现在哪一页"。题目必须考概念辨析、判断依据、应用步骤、错因修正或迁移应用。
1d. **禁止通用套话题**：不得使用“关于 X，以下哪项最能说明本节要求掌握的判断依据”“遇到与 X 相关的新题时应该优先采用哪种步骤”等可替换任意主题的模板。题干必须写出当前页面中的具体对象、条件、过程或因果关系。
1e. 每道题的正确答案和解析都必须能从页面文字直接核对；如果页面依据不足以支撑一道高质量题，就减少题量，不得用目录词、机构名、页码、章节编号或其他页面碎片凑选项。
1f. **禁止学习报告/推荐任务元题**：不要问“根据学习报告建议”“课堂建议应围绕哪些方面”“学生被推荐优先复习哪些内容”“推荐原因是什么”。题目必须直接考学生对知识点本身的理解、判断或应用。
2. 单选题为主，可少量多选题；每题 4 个选项，干扰项要像真实学生会混淆的错误理解。
   **多选题识别强约束**：如果题干含「以下哪些」「下列哪些」「哪些选项」「哪些是」「多选」等表述，**必须**把 `type` 设为「多选题」并给 `answer` 多个字母（如 "A,C"）。否则前端 UI 会按单选渲染，题干和交互对不上。
3. 每题必须给出 analysis，说明答案为什么对，并尽量指向具体页面编号（如"第 2 页"）或关键点。不要使用任何内部 ID。
4. 每题必须给出 knowledge_point，优先使用对应页面标题或关键点。
5. 不要生成填空题、代码输出题。
6. 如果有学生画像，题目难度、选项干扰方式和解析语言要匹配画像。
{short_answer_rule}

## JSON 格式
直接返回 JSON，不要 Markdown 代码块，不要解释文字。
{{
  "title": "{topic}",
  "modules": [
    {{
      "title": "模块名",
      "questions": [
        {{
          "num": "1",
          "type": "单选题",
          "text": "题干",
          "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
          "answer": "A",
          "analysis": "解析",
          "knowledge_point": "知识点"
        }},
        {{
          "num": "2",
          "type": "简答题",
          "text": "题干",
          "reference_answer": "2-4 句参考答案",
          "rubric": ["维度1", "维度2", "维度3"],
          "analysis": "答题要点提示",
          "knowledge_point": "知识点"
        }}
      ]
    }}
  ]
}}"""

    def _generate_context_quiz_json(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        question_count: int,
        student_profile: dict[str, str] | None = None,
        require_short_answer: bool = False,
        critic_feedback: str = "",
    ) -> str:
        quiz_generator = self._get_quiz_generator()
        slide_summaries = self._build_slide_summaries(scenes)
        if hasattr(quiz_generator, "generate_context_quiz_json"):
            try:
                return quiz_generator.generate_context_quiz_json(
                    topic=topic,
                    slide_summaries=slide_summaries,
                    question_count=question_count,
                    student_profile=_normalize_student_profile(student_profile),
                    require_short_answer=require_short_answer,
                    critic_feedback=critic_feedback,
                )
            except TypeError:
                # 外部 quiz_generator 不支持新参数，回退到不带参数版本
                return quiz_generator.generate_context_quiz_json(
                    topic=topic,
                    slide_summaries=slide_summaries,
                    question_count=question_count,
                )
        prompt = self._build_context_quiz_prompt(
            topic, slide_summaries, question_count, student_profile, require_short_answer
        )
        if critic_feedback:
            prompt += f"""

## 上一次审查未通过，必须修正
{critic_feedback}

请丢弃上一次结果并重新生成整套题，不要只修改一个字段。仍然只返回规定的 JSON。
"""
        return quiz_generator._call_llm(prompt)  # noqa: SLF001

    @staticmethod
    def _build_quiz_retry_feedback(issue_codes: list[str]) -> str:
        guidance = {
            "unsupported_knowledge_point": (
                "knowledge_point 未被页面原文支持；必须逐字复制页面标题或关键点"
            ),
            "answer_analysis_conflict": (
                "answer 与 analysis 指认的正确选项冲突；重新核对每个选项和答案"
            ),
            "invalid_options": "选择题必须有 4 个非空且互不重复的选项",
            "invalid_answer": "answer 必须对应现有选项",
            "single_answer_count": "单选题只能有 1 个正确答案",
            "multiple_answer_count": "多选题至少有 2 个正确答案",
            "missing_analysis": "每道题必须给出基于页面原文的解析",
            "missing_questions": "没有生成可用题目",
            "generation_failed": "JSON 不完整或字段不符合格式要求",
            "semantic_critic_error": "语义审查未能确认内容，请严格贴合页面原文",
            "semantic_rejected": "题目与页面依据不一致",
        }
        rows = []
        for code in issue_codes or ["generation_failed"]:
            rows.append(f"- {code}: {guidance.get(code, '修复该审查问题')}")
        rows.append("- 禁止生成可替换任意主题的通用题干或通用步骤题")
        return "\n".join(rows)

    def _clean_llm_json(self, value: str) -> str:
        text = (value or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return text.strip()

    def _parse_option(self, option: Any, fallback_label: str) -> tuple[str, str]:
        raw = _clean_quiz_text(str(option))
        match = re.match(r"^([A-Da-d])[\.\、\)\s：:]+(.+)$", raw)
        if match:
            return match.group(1).upper(), _clean_quiz_text(match.group(2))
        return fallback_label, raw

    def _normalize_llm_answers(self, value: Any) -> list[str]:
        if isinstance(value, list):
            rows = value
        else:
            rows = re.findall(r"[A-Da-d]", str(value or ""))
        answers = sorted({str(row).strip().upper() for row in rows if str(row).strip().upper() in {"A", "B", "C", "D"}})
        return answers

    def _convert_llm_quiz_json(
        self,
        raw_json: str,
        scenes: list[ClassroomScene],
        max_questions: int,
        qid_prefix: str,
    ) -> list[dict[str, Any]]:
        data = json.loads(self._clean_llm_json(raw_json))
        modules = data.get("modules", [])
        if not isinstance(modules, list):
            return []

        scene_points: list[str] = []
        decorative_terms: list[str] = []
        for scene in scenes:
            if scene.title and not _is_decorative_quiz_text(scene.title):
                scene_points.append(scene.title)
            scene_points.extend(_quiz_points_from_scene(scene))
            decorative_terms.extend(
                text for text in _scene_text_values(scene)
                if _is_decorative_quiz_text(text)
            )
        decorative_terms = [
            term for term in dict.fromkeys(decorative_terms)
            if len(term) >= 4
        ][:20]

        questions: list[dict[str, Any]] = []
        for module in modules:
            for row in module.get("questions", []) if isinstance(module, dict) else []:
                if len(questions) >= max_questions:
                    break
                text = _clean_quiz_text(str(row.get("text") or row.get("question") or ""))
                if not text:
                    continue
                if _question_has_scene_index(text):
                    continue
                if _is_meta_practice_question_text(text):
                    continue
                if any(term in text for term in decorative_terms):
                    continue

                # 修复：原先不过滤 LLM 直给的 knowledge_point，导致 "page 15 关键点：xxx"
                # 这种带 slide/page 占位符 + 关键点/要点 前缀的脏数据直接落到题目里，
                # 进而污染 report.weak_points 标签。先清洗 LLM 提供的值；若清洗后仍
                # 命中占位符模式或为空，再回退到 scene_points。
                raw_kp = _clean_text(str(row.get("knowledge_point") or module.get("title") or ""))
                knowledge_point = _clean_knowledge_point(raw_kp) if raw_kp else ""
                if not knowledge_point or re.search(r"\b(slide|page)[_\-\s]*\d+\b", knowledge_point, flags=re.I):
                    knowledge_point = next(
                        (
                            point
                            for point in scene_points
                            if point and not re.search(r"\b(slide|page)[_\-\s]*\d+\b", point, flags=re.I)
                        ),
                        "",
                    )
                if not knowledge_point:
                    knowledge_point = topic
                if _is_decorative_quiz_text(knowledge_point):
                    knowledge_point = topic

                qtype_raw = str(row.get("type", "单选题"))
                is_short_answer = "简答" in qtype_raw or qtype_raw.strip().lower() in {"short_answer", "essay", "open"}

                if is_short_answer:
                    # 简答题：不要 options/answer；需要 reference_answer / rubric
                    reference_answer = _clean_quiz_text(
                        str(row.get("reference_answer") or row.get("answer") or "")
                    )
                    rubric_raw = row.get("rubric", [])
                    if isinstance(rubric_raw, list):
                        rubric = [str(r).strip() for r in rubric_raw if str(r).strip()][:5]
                    else:
                        rubric = []
                    if not reference_answer:
                        # 没有参考答案就跳过这道，不让脏数据进课堂
                        continue
                    questions.append(
                        {
                            "id": f"{qid_prefix}{len(questions) + 1}",
                            "type": "short_answer",
                            "question": text,
                            "options": [],
                            "answer": [reference_answer],
                            "analysis": _clean_quiz_text(
                                str(row.get("analysis") or f"参考要点：{reference_answer}")
                            ),
                            "points": 1,
                            "knowledge_point": knowledge_point,
                            "reference_answer": reference_answer,
                            "rubric": rubric,
                        }
                    )
                    continue

                # 单选 / 多选：必须有 4 个选项 + 合法 answer
                raw_options = row.get("options", [])
                answers = self._normalize_llm_answers(row.get("answer", []))
                if not isinstance(raw_options, list) or len(raw_options) < 4 or not answers:
                    continue

                options: list[dict[str, str]] = []
                used_values: set[str] = set()
                for idx, option in enumerate(raw_options[:4]):
                    value, label = self._parse_option(option, ["A", "B", "C", "D"][idx])
                    if value in used_values or value not in {"A", "B", "C", "D"} or not label:
                        continue
                    used_values.add(value)
                    options.append({"label": label, "value": value})
                if len(options) != 4 or any(answer not in used_values for answer in answers):
                    continue

                # 多选题识别：双重保险
                # 1) 答案有 2+ 个字母 → 多选（LLM 给的 answer 已经是列表/字符串含多字母）
                # 2) LLM 的 type 字段含"多"（"多选题"等）
                # 3) 题干文字含强信号（"以下哪些"/"下列哪些"/"哪些选项"/"哪些是"/"多选"）
                #    → 即便 LLM 错误地标了"单选题"也强制升级成多选
                is_multi_by_text = bool(
                    re.search(r"(以下哪些|下列哪些|哪些选项|哪些是|多选)", text)
                )
                normalized_type = (
                    "multiple"
                    if len(answers) > 1 or "多" in qtype_raw or is_multi_by_text
                    else "single"
                )
                questions.append(
                    {
                        "id": f"{qid_prefix}{len(questions) + 1}",
                        "type": normalized_type,
                        "question": text,
                        "options": options,
                        "answer": answers,
                        "analysis": _clean_quiz_text(str(row.get("analysis") or "请回到对应课堂页面复习该知识点。")),
                        "points": 1,
                        "knowledge_point": knowledge_point,
                    }
                )
            if len(questions) >= max_questions:
                break
        return questions

    def _build_llm_quiz_questions(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        max_questions: int,
        qid_prefix: str,
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        require_short_answer: bool = False,
        critic_mode: str = "off",
        knowledge_context: dict[str, Any] | None = None,
        semantic_reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        _raise_if_cancelled(cancel_check)
        if not self.llm_quiz_enabled:
            return [], self._critic_summary(
                CriticResult(
                    passed=True,
                    grounding_level="none",
                )
            )
        slide_summaries = self._build_slide_summaries(scenes)
        visible_texts: list[str] = []
        for summary in slide_summaries:
            visible_texts.extend(summary.get("knowledge_points", []))
            visible_texts.extend(summary.get("extracted_text", []))
        grounding = build_grounding_context(
            knowledge_context=knowledge_context,
            visible_texts=visible_texts,
            manuscript_note="",
        )
        critic = ClassroomCriticService(
            mode=critic_mode,
            semantic_reviewer=semantic_reviewer or self.semantic_reviewer,
        )
        last_result = CriticResult(
            passed=False,
            severity="error",
            issue_codes=["generation_failed"],
            grounding_level=grounding.level,
            retry_required=True,
        )
        critic_feedback = ""
        for attempt in range(3):
            try:
                raw_json = self._generate_context_quiz_json(
                    topic,
                    scenes,
                    max_questions,
                    student_profile,
                    require_short_answer,
                    critic_feedback,
                )
                _raise_if_cancelled(cancel_check)
                questions = self._convert_llm_quiz_json(
                    raw_json=raw_json,
                    scenes=scenes,
                    max_questions=max_questions,
                    qid_prefix=qid_prefix,
                )
                if (
                    require_short_answer
                    and questions
                    and not any(q.get("type") == "short_answer" for q in questions)
                ):
                    questions = self._force_one_short_answer(questions)
                last_result = critic.review_quiz_questions(
                    questions=questions,
                    grounding=grounding,
                )
                if questions and last_result.passed:
                    return questions, self._critic_summary(
                        last_result,
                        retried=attempt > 0,
                    )
                critic_feedback = self._build_quiz_retry_feedback(
                    last_result.issue_codes
                )
            except Exception:
                last_result = CriticResult(
                    passed=False,
                    severity="error",
                    issue_codes=["generation_failed"],
                    grounding_level=grounding.level,
                    retry_required=True,
                )
                critic_feedback = self._build_quiz_retry_feedback(
                    last_result.issue_codes
                )
        return [], self._critic_summary(
            last_result,
            retried=True,
            fallback=True,
        )

    @staticmethod
    def _force_one_short_answer(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """把最后一道单选/多选降级为简答。

        适用场景：要求 1 道简答但 LLM 没出。直接把最后一道的 options/answer
        丢掉，type 改成 short_answer；用其 analysis 兜底作 reference_answer，
        rubric 用默认三维度。题干是单选问题"X 是 Y 中的哪一类？"
        这种封闭问法对简答来说不理想，但作为兜底可接受——
        真正生产环境 LLM 99% 情况下会按 prompt 出题，落到这条分支的频率低。
        """
        if not questions:
            return questions
        # 已有简答就不强制（避免出现 2 道简答）
        if any(q.get("type") == "short_answer" for q in questions):
            return questions
        idx = len(questions) - 1
        target = dict(questions[idx])
        analysis_text = str(target.get("analysis") or "").strip()
        reference_answer = analysis_text or "请结合课堂内容作答。"
        target["type"] = "short_answer"
        target["options"] = []
        target["answer"] = [reference_answer]
        target["reference_answer"] = reference_answer
        target["rubric"] = ["准确性", "完整性", "表达"]
        questions[idx] = target
        return questions

    def _build_quiz_scene(
        self,
        quiz_index: int,
        order: int,
        topic: str,
        scenes: list[ClassroomScene],
        max_questions: int = 3,
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
        require_short_answer: bool = False,
        critic_mode: str = "off",
        knowledge_context: dict[str, Any] | None = None,
        semantic_reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> ClassroomScene | None:
        _raise_if_cancelled(cancel_check)
        qid_prefix = f"q{quiz_index}_"
        questions, critic_summary = self._build_llm_quiz_questions(
            topic,
            scenes,
            max_questions=max_questions,
            qid_prefix=qid_prefix,
            student_profile=student_profile,
            cancel_check=cancel_check,
            require_short_answer=require_short_answer,
            critic_mode=critic_mode,
            knowledge_context=knowledge_context,
            semantic_reviewer=semantic_reviewer,
        )
        _raise_if_cancelled(cancel_check)
        if not questions:
            questions = self._build_quiz_questions(
                topic,
                scenes,
                max_questions=max_questions,
                qid_prefix=qid_prefix,
            )
        quiz_source = "llm_json" if self.llm_quiz_enabled and not critic_summary.get("fallback") else "slide_text"
        knowledge_points: list[str] = []
        for scene in scenes:
            for point in [scene.title, *scene.knowledge_points]:
                if point and point not in knowledge_points:
                    knowledge_points.append(point)

        return ClassroomScene(
            id=f"scene_quiz_{quiz_index:03d}",
            type="quiz",
            title=f"随堂测验 {quiz_index}：{topic}",
            order=order,
            knowledge_points=knowledge_points[:6] or [topic],
            content={
                "questions": questions,
                "quiz_source": quiz_source,
                "covered_scene_ids": [scene.id for scene in scenes],
                "critic": critic_summary,
            },
            actions=[],
        )

    @staticmethod
    def _renumber_quiz_scenes(scenes: list[ClassroomScene], topic: str) -> None:
        quiz_index = 1
        for scene in scenes:
            if scene.type != "quiz":
                continue

            scene.id = f"scene_quiz_{quiz_index:03d}"
            scene.title = f"随堂测验 {quiz_index}：{topic}"

            questions = scene.content.get("questions", []) if isinstance(scene.content, dict) else []
            if isinstance(questions, list):
                for question_number, question in enumerate(questions, start=1):
                    if isinstance(question, dict):
                        question["id"] = f"q{quiz_index}_{question_number}"

            quiz_index += 1

    def build_practice_quiz_scene(
        self,
        *,
        topic: str,
        knowledge_points: list[str],
        task_type: str,
        generation_strategy: dict[str, Any] | None = None,
    ) -> ClassroomScene:
        clean_points = [
            _clean_text(str(value))[:80]
            for value in knowledge_points
            if _clean_text(str(value))
        ][:5]
        if not clean_points:
            clean_points = [_clean_text(topic) or "综合理解"]
        assessment = (
            generation_strategy.get("assessment_strategy", {})
            if isinstance(generation_strategy, dict)
            else {}
        )
        diagnostic_notes = [
            _clean_text(str(value))
            for value in assessment.get("practice_diagnostic_notes", [])
            if _clean_text(str(value))
        ][:5]
        evidence_by_point = _practice_evidence_by_point(assessment)
        source_scenes = [
            ClassroomScene(
                id=f"practice_source_{idx:03d}",
                type="slide",
                title=f"补强材料 {idx}",
                order=idx,
                knowledge_points=[point],
                content={
                    "extracted_text": [
                        point,
                        *evidence_by_point.get(point, []),
                    ]
                },
                actions=[],
            )
            for idx, point in enumerate(clean_points, start=1)
        ]
        profile = self._profile_from_generation_strategy(generation_strategy)
        scene = self._build_quiz_scene(
            quiz_index=1,
            order=1,
            topic=topic,
            scenes=source_scenes,
            max_questions=4,
            student_profile=profile,
            require_short_answer=task_type == "challenge_practice",
        )
        if scene is None:
            raise RuntimeError("练习题连续审查失败，已停止生成以避免返回通用保底题")
        scene.title = (
            f"挑战练习：{'、'.join(clean_points[:3])}"
            if task_type == "challenge_practice"
            else f"补强练习：{'、'.join(clean_points[:3])}"
        )
        scene.content["practice_task_type"] = task_type
        scene.content["error_targets"] = list(assessment.get("error_targets", []))
        scene.content["diagnostic_notes"] = diagnostic_notes
        scene.content["transfer_level"] = assessment.get(
            "transfer_level",
            "unobserved",
        )
        scene.content["covered_scene_ids"] = []
        return scene

    @staticmethod
    def _practice_strategy_instruction(
        point: str,
        task_type: str,
        generation_strategy: dict[str, Any] | None,
    ) -> str:
        assessment = (
            generation_strategy.get("assessment_strategy", {})
            if isinstance(generation_strategy, dict)
            else {}
        )
        error_targets = set(assessment.get("error_targets", []))
        requirements: list[str] = []
        if "concept_confusion" in error_targets:
            requirements.append("加入相近概念对比辨析")
        if "prerequisite_gap" in error_targets:
            requirements.append("先检查前置知识")
        if "procedural_error" in error_targets:
            requirements.append("要求展示关键步骤")
        if "application_failure" in error_targets:
            requirements.append("加入变式和应用情境")
        if "expression_gap" in error_targets:
            requirements.append("加入简答表达与要点核对")
        base = (
            f"围绕{point}完成迁移应用和综合判断"
            if task_type == "challenge_practice"
            else f"围绕{point}复习概念、判断依据和应用步骤"
        )
        return f"{base}；{'；'.join(requirements)}。" if requirements else f"{base}。"

    def _insert_quiz_scenes(
        self,
        topic: str,
        scenes: list[ClassroomScene],
        student_profile: dict[str, str] | None = None,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
        expected_extra_scene_count: int = 0,
        critic_mode: str = "off",
        knowledge_context: dict[str, Any] | None = None,
        semantic_reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> list[ClassroomScene]:
        _raise_if_cancelled(cancel_check)
        slide_scenes = [scene for scene in scenes if scene.type == "slide"]
        if not slide_scenes:
            return scenes

        quiz_index = 1
        pending_slides: list[ClassroomScene] = []
        quiz_source_slides = [
            scene for i, scene in enumerate(slide_scenes)
            if _is_quiz_source_scene(scene, is_first_slide=(i == 0))
        ]
        # 兜底：如果所有页面都被过滤为开场页，回退使用全部 slide（避免完全无测验）
        if not quiz_source_slides and slide_scenes:
            quiz_source_slides = list(slide_scenes)
        quiz_source_ids = {scene.id for scene in quiz_source_slides}
        total_quiz_source_slides = len(quiz_source_slides)
        # 估计要插入的 quiz 数量（按现有规则），用于阶段 3 的 scene_total
        # 密度：每 3 张讲解 → 1 个 mid 测验 + 末尾 1 个 final 测验
        # 实际 mid 数 = max(0, (N-1)//3)，加 1 个 final
        quiz_count_estimate = max(0, (total_quiz_source_slides - 1) // 3) + 1
        expected_scene_total = len(scenes) + quiz_count_estimate + max(0, expected_extra_scene_count)
        _emit_progress(
            progress_callback,
            stage="insert_quizzes",
            stage_index=2,
            scene_index=0,
            scene_total=quiz_count_estimate,
            expected_scene_total=expected_scene_total,
            expected_slide_total=len(slide_scenes),
        )

        quiz_source_index = 0
        completed_quiz_jobs = 0
        result: list[ClassroomScene] = []
        pending_quiz_job: dict[str, Any] | None = None

        def _append_scene(scene: ClassroomScene) -> None:
            result.append(scene)
            scene.order = len(result)

        def _emit_existing_scene(scene: ClassroomScene) -> None:
            _emit_progress(
                progress_callback,
                stage="insert_quizzes",
                stage_index=2,
                scene_index=completed_quiz_jobs,
                scene_total=quiz_count_estimate,
                expected_scene_total=expected_scene_total,
                expected_slide_total=len(slide_scenes),
                scene=scene,
            )

        def _flush_pending_quiz() -> None:
            nonlocal completed_quiz_jobs, pending_quiz_job
            if pending_quiz_job is None:
                return
            _raise_if_cancelled(cancel_check)
            job = pending_quiz_job
            pending_quiz_job = None
            completed_quiz_jobs += 1
            quiz_scene = self._build_quiz_scene(
                quiz_index=int(job["quiz_index"]),
                order=len(result) + 1,
                topic=topic,
                scenes=job["scenes"],
                max_questions=int(job["max_questions"]),
                student_profile=student_profile,
                cancel_check=cancel_check,
                progress_callback=progress_callback,
                require_short_answer=bool(job["require_short_answer"]),
                critic_mode=critic_mode,
                knowledge_context=knowledge_context,
                semantic_reviewer=semantic_reviewer,
            )
            if quiz_scene is None:
                _emit_progress(
                    progress_callback,
                    stage="insert_quizzes",
                    stage_index=2,
                    scene_index=completed_quiz_jobs,
                    scene_total=quiz_count_estimate,
                    expected_scene_total=expected_scene_total,
                    expected_slide_total=len(slide_scenes),
                )
                return

            _append_scene(quiz_scene)
            self._renumber_quiz_scenes(result, topic)
            _emit_progress(
                progress_callback,
                stage="insert_quizzes",
                stage_index=2,
                scene_index=completed_quiz_jobs,
                scene_total=quiz_count_estimate,
                expected_scene_total=expected_scene_total,
                expected_slide_total=len(slide_scenes),
                scene=quiz_scene,
            )

        for scene in scenes:
            _raise_if_cancelled(cancel_check)
            if scene.type != "slide":
                _append_scene(scene)
                _emit_existing_scene(scene)
                continue

            _flush_pending_quiz()
            _append_scene(scene)
            if scene.id not in quiz_source_ids:
                continue

            quiz_source_index += 1
            pending_slides.append(scene)

            is_last = quiz_source_index == total_quiz_source_slides
            # 密度调整：3 张讲解 → 1 个 mid 测验（之前是 2 张）
            enough_for_mid_quiz = len(pending_slides) >= 3 and not is_last
            enough_for_final_quiz = is_last and pending_slides

            if enough_for_mid_quiz or enough_for_final_quiz:
                # P1-3 调优：每 3 个测验页出 1 道简答题（quiz_index 3/6/9/...）
                # 配合"默认不强制"prompt，理论 ~33% 测验含简答。
                require_short_answer = (quiz_index % 3 == 0)
                pending_quiz_job = {
                    "quiz_index": quiz_index,
                    "scenes": list(pending_slides),
                    "max_questions": 2 if not is_last else 3,
                    "require_short_answer": require_short_answer,
                }
                quiz_index += 1
                pending_slides = []

        _flush_pending_quiz()
        self._renumber_quiz_scenes(result, topic)
        return result

