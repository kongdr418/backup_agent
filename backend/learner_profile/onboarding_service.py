from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Callable

from .schemas import COGNITIVE_PREFERENCE_KEYS


FIELD_ORDER = (
    "learning_stage",
    "learning_basis",
    "background",
    "goal",
    "content_style",
    "preferred_difficulty",
    "tutoring_style",
    "interest_directions",
)

FIELD_QUESTIONS = {
    "learning_stage": "先认识一下你：你目前处于什么学习阶段或年级？",
    "learning_basis": "你觉得自己目前的学习基础怎样？（零基础/有基础/进阶学习）",
    "background": "可以聊聊你的学习背景吗？比如专业、学过哪些课程？",
    "goal": "你现在最想达成哪类学习目标？请选择：概念理解、考试通过、项目实战或能力提升。",
    "content_style": "你偏好哪些内容呈现方式？可多选：图解、案例、步骤推导、对比辨析、代码实操或精简总结。",
    "preferred_difficulty": "你希望学习内容的难度偏基础、中等，还是更有挑战？",
    "tutoring_style": "你更喜欢哪种辅导方式？请选择：引导式、分步讲解、直接反馈或启发提问。",
    "interest_directions": "最后，你对哪些方向更感兴趣？可多选：人工智能应用、软件开发、数据分析、工程实践或生活应用。",
}

OPTION_ALIASES = {
    "learning_stage": {
        "大一": ("大一", "大学一年级"),
        "大二": ("大二", "大学二年级"),
        "大三": ("大三", "大学三年级"),
        "大四": ("大四", "大学四年级"),
        "硕士": ("硕士", "研究生", "研一", "研二", "研三"),
        "博士": ("博士", "博一", "博二", "博三", "博四"),
        "专升本": ("专升本",),
    },
    "learning_basis": {
        "零基础": ("零基础", "小白", "没学过", "从未学过", "完全不会"),
        "有基础": ("有基础", "基础一般", "学过一些", "接触过", "略懂"),
        "进阶学习": ("进阶学习", "进阶", "深入学习", "比较熟练", "熟练掌握"),
    },
    "goal": {
        "概念理解": ("概念理解", "理解概念", "弄懂原理", "掌握原理"),
        "考试通过": ("考试通过", "通过考试", "备考", "考研", "期末考试"),
        "项目实战": ("项目实战", "完成项目", "做项目", "项目实践"),
        "能力提升": ("能力提升", "提升能力", "提高水平", "查漏补缺"),
    },
    "content_style": {
        "图解": ("图解", "图示", "图表", "可视化"),
        "案例": ("案例", "例子", "举例", "实例"),
        "步骤推导": ("步骤推导", "逐步推导", "推导过程", "原理推导"),
        "对比辨析": ("对比辨析", "对比", "比较", "区分异同"),
        "代码实操": ("代码实操", "动手实践", "动手实操", "写代码", "编程练习", "实操", "实践"),
        "精简总结": ("精简总结", "简洁总结", "要点总结", "总结重点"),
    },
    "preferred_difficulty": {
        "基础": ("基础", "简单", "入门", "容易"),
        "中等": ("中等", "适中", "一般难度"),
        "挑战": ("挑战", "有挑战", "困难", "高难度", "进阶难度"),
    },
    "tutoring_style": {
        "引导式": ("引导式", "引导我", "给提示", "循序引导"),
        "分步讲解": ("分步讲解", "一步一步", "逐步讲解", "细讲", "详细讲解"),
        "直接反馈": ("直接反馈", "直接指出", "直接告诉", "马上纠正"),
        "启发提问": ("启发提问", "提问启发", "启发式提问", "通过提问"),
    },
    "interest_directions": {
        "人工智能应用": ("人工智能应用", "人工智能", "AI", "机器学习", "深度学习"),
        "软件开发": ("软件开发", "写软件", "开发应用", "编程开发"),
        "数据分析": ("数据分析", "数据挖掘", "数据处理"),
        "工程实践": ("工程实践", "工程项目", "工程开发"),
        "生活应用": ("生活应用", "日常应用", "实际生活"),
    },
}

MULTI_SELECT_FIELDS = {"content_style", "interest_directions"}


def _extract_json(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def _clean_text(value: Any, max_length: int = 300) -> str:
    return " ".join(str(value or "").split())[:max_length]


def _clean_list(value: Any, max_items: int = 6) -> list[str]:
    rows = value if isinstance(value, list) else re.split(r"[，、,;/|+]", str(value or ""))
    result: list[str] = []
    for row in rows:
        text = _clean_text(row, 40)
        if text and text not in result:
            result.append(text)
        if len(result) >= max_items:
            break
    return result


def _option_matches(field: str, value: Any) -> list[str]:
    if isinstance(value, list):
        text = "、".join(_clean_text(row, 80) for row in value)
    else:
        text = _clean_text(value, 300)
    if not text:
        return []
    lowered = text.lower()
    return [
        canonical
        for canonical, aliases in OPTION_ALIASES.get(field, {}).items()
        if any(
            (
                re.search(
                    rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])",
                    lowered,
                )
                if alias.isascii()
                else alias.lower() in lowered
            )
            for alias in aliases
        )
    ]


def _normalize_option(field: str, value: Any) -> str | list[str]:
    matches = _option_matches(field, value)
    if field in MULTI_SELECT_FIELDS:
        return matches
    return matches[0] if len(matches) == 1 else ""


class ProfileOnboardingService:
    def __init__(self, llm_call: Callable[..., str] | None = None) -> None:
        self.llm_call = llm_call

    def advance(
        self,
        *,
        profile: dict[str, Any],
        messages: list[dict[str, str]],
        llm_config: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        draft = deepcopy(profile)
        self._ensure_shape(draft)
        self._normalize_draft(draft)
        current_before = self._next_missing_field(draft)
        llm_result: dict[str, Any] = {}

        if messages and messages[-1].get("role") == "user":
            if current_before:
                self._apply_fallback_answer(
                    draft,
                    current_before,
                    messages[-1].get("content", ""),
                )
            current_after_local = self._next_missing_field(draft)
            if current_after_local == current_before:
                llm_result = self._extract_with_llm(draft, messages, llm_config or {})
                if isinstance(llm_result.get("extracted"), dict):
                    self._merge_extracted(draft, llm_result["extracted"])

        current_field = self._next_missing_field(draft)
        completed = current_field == ""
        if completed:
            reply = "画像信息已经比较完整，请检查下方画像草稿。确认无误后即可保存。"
        else:
            reply = FIELD_QUESTIONS[current_field]

        return {
            "reply": reply,
            "draft": draft,
            "completed": completed,
            "current_field": current_field,
            "messages": messages,
        }

    def _extract_with_llm(
        self,
        draft: dict[str, Any],
        messages: list[dict[str, str]],
        llm_config: dict[str, str],
    ) -> dict[str, Any]:
        if self.llm_call is None:
            return {}
        prompt = {
            "profile": {
                "basic": draft["basic"],
                "preferences": draft["preferences"],
                "global_traits": draft["global_traits"],
            },
            "conversation": messages[-10:],
            "required_fields": list(FIELD_ORDER),
        }
        system = (
            "你是面向大学生的学习画像信息抽取器。只根据学生明确表达提取画像，不要猜测，"
            "不要提问，不要生成回复文案。\n\n"
            "字段定义与预设选项：\n"
            "- learning_stage: 学习阶段/年级，预设值：'大一'、'大二'、'大三'、'大四'、'硕士'、'博士'、'专升本'\n"
            "- learning_basis: 知识掌握程度，预设值：'零基础'、'有基础'、'进阶学习'\n"
            "- background: 学习背景、专业、学过什么课程，自由文本\n"
            "- goal: 【单选】学习目标，预设值：'概念理解'、'考试通过'、'项目实战'、'能力提升'，用户说'理解概念'→'概念理解'，'完成项目'→'项目实战'\n"
            "- content_style: 【多选数组】内容风格偏好，预设值：'图解'、'案例'、'步骤推导'、'对比辨析'、'代码实操'、'精简总结'，用户说'实践'→'代码实操'，'例子'→'案例'\n"
            "- preferred_difficulty: 【单选】期望难度，预设值：'基础'、'中等'、'挑战'\n"
            "- tutoring_style: 【单选】辅导方式，预设值：'引导式'、'分步讲解'、'直接反馈'、'启发提问'\n"
            "- interest_directions: 【多选数组】兴趣方向，预设值：'人工智能应用'、'软件开发'、'数据分析'、'工程实践'、'生活应用'\n\n"
            "处理规则：\n"
            "1. 单选字段用户给了多个选项时，extracted留空，由系统继续询问\n"
            "2. 多选字段用户给了多个选项时，拆分为数组填入\n"
            "3. 用户自然语言必须映射到预设值\n\n"
            "拆分示例：\n"
            "用户说'大二 学过C语言和Python' → learning_stage='大二', learning_basis='有基础', background='学过C语言和Python'\n"
            "用户说'理解概念和完成项目' → extracted.goal留空\n"
            "用户说'动手实践和案例' → content_style=['代码实操','案例']\n"
            "用户说'案例和图解吧' → content_style=['案例','图解']\n\n"
            "仅返回 JSON："
            '{"extracted":{"basic":{"learning_stage":"","learning_basis":"","background":""},'
            '"preferences":{"goal":"","content_style":[],"preferred_difficulty":"","tutoring_style":""},'
            '"cognitive_preferences":[],"interest_directions":[]}}。'
        )
        try:
            raw = self.llm_call(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                temperature=0.2,
                max_tokens=1200,
                **llm_config,
            )
        except Exception:
            return {}
        return _extract_json(raw)

    @staticmethod
    def _ensure_shape(draft: dict[str, Any]) -> None:
        draft.setdefault("basic", {})
        draft.setdefault("preferences", {})
        draft.setdefault("global_traits", {})
        draft["global_traits"].setdefault("cognitive_preferences", {})
        draft["global_traits"].setdefault("interest_directions", [])

    @staticmethod
    def _normalize_draft(draft: dict[str, Any]) -> None:
        basic = draft["basic"]
        preferences = draft["preferences"]
        for field in ("learning_stage", "learning_basis"):
            basic[field] = _normalize_option(field, basic.get(field))
        for field in ("goal", "preferred_difficulty", "tutoring_style"):
            preferences[field] = _normalize_option(field, preferences.get(field))
        preferences["content_style"] = _normalize_option(
            "content_style",
            preferences.get("content_style"),
        )
        interests = _normalize_option(
            "interest_directions",
            [
                row.get("label", "")
                for row in draft["global_traits"].get("interest_directions", [])
                if isinstance(row, dict)
            ],
        )
        draft["global_traits"]["interest_directions"] = [
            {
                "label": label,
                "weight": 1,
                "confidence": 1,
                "source": "self_reported",
                "status": "confirmed",
                "evidence_ids": [],
            }
            for label in interests
        ]

    def _merge_extracted(self, draft: dict[str, Any], value: Any) -> None:
        if not isinstance(value, dict):
            return
        basic = value.get("basic") if isinstance(value.get("basic"), dict) else {}
        preferences = (
            value.get("preferences")
            if isinstance(value.get("preferences"), dict)
            else {}
        )
        for key in ("learning_stage", "learning_basis"):
            normalized = _normalize_option(key, basic.get(key))
            if normalized:
                draft["basic"][key] = normalized
        background = _clean_text(basic.get("background"))
        if background:
            draft["basic"]["background"] = background

        # 智能拆分：当 learning_basis 包含具体课程/技术描述时，拆分到 background
        basis = _clean_text(basic.get("learning_basis"))
        bg = _clean_text(basic.get("background"))
        if basis and not bg:
            course_patterns = r'(学过|学习过|修过|上过|接触过|C语言|Python|Java|MySQL|数据结构|操作系统|计算机网络|数据库|机器学习|深度学习)'
            if re.search(course_patterns, basis):
                draft["basic"]["background"] = basis
                # learning_basis 设为对应的基础等级
                if any(w in basis for w in ['零', '没', '从未', '小白']):
                    draft["basic"]["learning_basis"] = "零基础"
                elif any(w in basis for w in ['进阶', '深入', '精通', '熟练']):
                    draft["basic"]["learning_basis"] = "进阶学习"
                else:
                    draft["basic"]["learning_basis"] = "有基础"
        for key in ("goal", "preferred_difficulty", "tutoring_style"):
            normalized = _normalize_option(key, preferences.get(key))
            if normalized:
                draft["preferences"][key] = normalized
        styles = _normalize_option("content_style", preferences.get("content_style"))
        if styles:
            draft["preferences"]["content_style"] = styles

        cognitive = _clean_list(value.get("cognitive_preferences"))
        for key in cognitive:
            if key not in COGNITIVE_PREFERENCE_KEYS:
                continue
            draft["global_traits"]["cognitive_preferences"][key] = {
                "weight": 1,
                "confidence": 1,
                "source": "self_reported",
                "status": "confirmed",
                "evidence_ids": [],
            }

        interests = _normalize_option(
            "interest_directions",
            value.get("interest_directions"),
        )
        if interests:
            draft["global_traits"]["interest_directions"] = [
                {
                    "label": label,
                    "weight": 1,
                    "confidence": 1,
                    "source": "self_reported",
                    "status": "confirmed",
                    "evidence_ids": [],
                }
                for label in interests
            ]

    @staticmethod
    def _apply_fallback_answer(
        draft: dict[str, Any],
        field: str,
        answer: str,
    ) -> None:
        text = _clean_text(answer)
        if not text:
            return
        if field == "background":
            draft["basic"][field] = "暂无补充" if field == "background" and text in {"没有", "无"} else text
            return
        if field in {"learning_stage", "learning_basis"}:
            normalized = _normalize_option(field, text)
            if normalized:
                draft["basic"][field] = normalized
            return
        if field in {"goal", "content_style", "preferred_difficulty", "tutoring_style"}:
            normalized = _normalize_option(field, text)
            if normalized:
                draft["preferences"][field] = normalized
            return
        if field == "interest_directions":
            interests = _normalize_option(field, text)
            draft["global_traits"]["interest_directions"] = [
                {
                    "label": label,
                    "weight": 1,
                    "confidence": 1,
                    "source": "self_reported",
                    "status": "confirmed",
                    "evidence_ids": [],
                }
                for label in interests
            ]

    @staticmethod
    def _next_missing_field(draft: dict[str, Any]) -> str:
        basic = draft["basic"]
        preferences = draft["preferences"]
        values = {
            "learning_stage": basic.get("learning_stage"),
            "learning_basis": basic.get("learning_basis"),
            "goal": preferences.get("goal"),
            "content_style": preferences.get("content_style"),
            "preferred_difficulty": preferences.get("preferred_difficulty"),
            "tutoring_style": preferences.get("tutoring_style"),
            "background": basic.get("background"),
            "interest_directions": draft["global_traits"].get("interest_directions"),
        }
        for field in FIELD_ORDER:
            if not values.get(field):
                return field
        return ""
