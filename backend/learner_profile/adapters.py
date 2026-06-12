from __future__ import annotations

from typing import Any

from .storage import PPT_LEARNING_STRATEGY_TITLE


_PATTERN_LABELS = {
    "diagram": "图示结构",
    "example": "案例讲解",
    "step_by_step": "步骤推导",
    "comparison": "对比辨析",
    "concise_summary": "精简总结",
    "code_practice": "实践操作",
}

_ERROR_LABELS = {
    "concept_confusion": "概念混淆",
    "prerequisite_gap": "前置知识缺失",
    "procedural_error": "步骤错误",
    "application_failure": "迁移应用困难",
    "careless_error": "审题疏漏",
    "expression_gap": "表达不完整",
}

_TRANSFER_LABELS = {
    "unobserved": "证据积累中",
    "recall": "概念复述",
    "near_transfer": "近迁移",
    "far_transfer": "远迁移",
    "integrated_problem_solving": "综合问题解决",
}


def build_ppt_strategy_notes(strategy: dict[str, Any]) -> str:
    content = strategy.get("content_strategy")
    assessment = strategy.get("assessment_strategy")
    content = content if isinstance(content, dict) else {}
    assessment = assessment if isinstance(assessment, dict) else {}
    patterns = [
        _PATTERN_LABELS.get(str(value), str(value))
        for value in content.get("preferred_patterns", [])
        if str(value)
    ]
    interests = [str(value) for value in content.get("interest_contexts", []) if str(value)]
    errors = [
        _ERROR_LABELS.get(str(value), str(value))
        for value in assessment.get("error_targets", [])
        if str(value)
    ]
    transfer = _TRANSFER_LABELS.get(
        str(assessment.get("transfer_level") or "unobserved"),
        str(assessment.get("transfer_level") or "证据积累中"),
    )
    focus = [
        str(value)
        for value in strategy.get("focus_knowledge_points", [])
        if str(value)
    ]
    lines = [
        PPT_LEARNING_STRATEGY_TITLE,
        f"内容组织：{'、'.join(patterns) or '图示结构、案例讲解'}",
        f"兴趣案例：{'、'.join(interests) or '结合课程常见应用'}",
        f"重点补强：{'、'.join(focus) or '按课程目标推进'}",
        f"错误模式：{'、'.join(errors) or '暂无稳定错误模式'}",
        f"迁移水平：{transfer}",
        f"策略理由：{strategy.get('reason') or '根据已确认画像调整。'}",
        "只将这些信息用于内容深度、案例、结构和练习设计，不要在幻灯片正文展示画像字段。",
    ]
    return "\n".join(lines)
