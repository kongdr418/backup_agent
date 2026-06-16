"""Classroom lineage parsing and inheritance helpers."""

from __future__ import annotations

import re
from typing import Protocol


class ClassroomLineageStorage(Protocol):
    def load_classroom(self, user_id: str, classroom_id: str) -> dict | None:
        ...


def safe_classroom_ref(value: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9_-]{1,128}$', value or ''))


def resolve_classroom_lineage(data: dict) -> dict | None:
    course_root_id = (data.get('course_root_id') or '').strip()
    parent_classroom_id = (data.get('parent_classroom_id') or '').strip()
    lesson_kind = (data.get('lesson_kind') or '').strip() or (
        'next_lesson' if parent_classroom_id else 'root'
    )
    if course_root_id and not safe_classroom_ref(course_root_id):
        return None
    if parent_classroom_id and not safe_classroom_ref(parent_classroom_id):
        return None
    if not re.match(r'^[a-zA-Z0-9_-]{1,40}$', lesson_kind):
        return None
    try:
        lesson_depth = max(0, min(20, int(data.get('lesson_depth', 0) or 0)))
    except (TypeError, ValueError):
        lesson_depth = 0
    try:
        lesson_index = max(1, min(500, int(data.get('lesson_index', 1) or 1)))
    except (TypeError, ValueError):
        lesson_index = 1
    return {
        'course_root_id': course_root_id,
        'parent_classroom_id': parent_classroom_id,
        'lesson_depth': lesson_depth,
        'lesson_index': lesson_index,
        'lesson_kind': lesson_kind,
    }


def inherit_classroom_lineage(
    storage: ClassroomLineageStorage,
    user_id: str,
    lineage: dict,
    course: str,
) -> tuple[dict, str]:
    parent_id = (lineage.get('parent_classroom_id') or '').strip()
    if not parent_id:
        return lineage, course
    parent = storage.load_classroom(user_id, parent_id)
    if parent is None:
        return lineage, course

    inherited = dict(lineage)
    inherited['course_root_id'] = (
        inherited.get('course_root_id')
        or parent.get('course_root_id')
        or parent.get('id')
        or parent_id
    )
    try:
        parent_depth = int(parent.get('lesson_depth', 0) or 0)
    except (TypeError, ValueError):
        parent_depth = 0
    try:
        parent_index = int(parent.get('lesson_index', 1) or 1)
    except (TypeError, ValueError):
        parent_index = 1
    if int(inherited.get('lesson_depth', 0) or 0) <= 0:
        inherited['lesson_depth'] = parent_depth + 1
    if int(inherited.get('lesson_index', 1) or 1) <= 1:
        inherited['lesson_index'] = parent_index + 1

    inherited_course = course
    if not inherited_course or inherited_course == '通用课程':
        inherited_course = parent.get('course') or parent.get('topic') or course
    return inherited, inherited_course
