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
    source: dict[str, Any] = field(default_factory=dict)
    agents: list[dict[str, Any]] = field(default_factory=list)
    knowledge_points: list[str] = field(default_factory=list)
    scenes: list[ClassroomScene] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
