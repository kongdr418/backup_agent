from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ClassroomAction:
    id: str
    type: str
    agent_id: str = "teacher"
    text: str = ""
    audio_url: str = ""
    speed: float = 1.0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuizQuestion:
    id: str
    type: str
    question: str
    options: list[dict[str, str]]
    answer: list[str]
    analysis: str
    points: int = 1
    knowledge_point: str = ""
    # P1-3: 简答题扩展字段
    # - reference_answer: 简答题参考答案（type="short_answer" 时使用）
    # - rubric: 评分维度列表，可选；缺省用 ['准确性', '完整性', '表达']
    reference_answer: str = ""
    rubric: list[str] = field(default_factory=list)


@dataclass
class ClassroomScene:
    id: str
    type: str
    title: str
    order: int
    knowledge_points: list[str] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)
    actions: list[ClassroomAction] = field(default_factory=list)


@dataclass
class LearningEvent:
    """课堂学习事件 —— 可追踪、可解释的学习证据。"""
    id: str
    type: str  # quiz_submitted | short_answer_scored | scene_reviewed | recommended_task_opened | recommended_task_completed | classroom_completed
    user_id: str
    classroom_id: str
    scene_id: str = ""
    course_id: str = ""
    created_at: str = ""
    # 事件关联的知识点
    knowledge_points: list[str] = field(default_factory=list)
    # 事件负载：不同事件类型携带不同结构
    payload: dict[str, Any] = field(default_factory=dict)
    # 重试信息
    retry_of: str = ""  # 如果是重试，指向原事件 ID
    dedupe_key: str = ""  # 幂等键，用于防重复提交

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InteractiveClassroom:
    id: str
    user_id: str
    title: str
    topic: str
    course: str
    status: str
    created_at: str
    updated_at: str
    tts: dict[str, str]
    student_profile: dict[str, str] = field(default_factory=dict)
    generation_strategy: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)
    agents: list[dict[str, Any]] = field(default_factory=list)
    knowledge_points: list[str] = field(default_factory=list)
    scenes: list[ClassroomScene] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
