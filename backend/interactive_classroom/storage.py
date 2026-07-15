from __future__ import annotations

import json
import os
import re
import shutil
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from interactive_classroom.schema import LearningEvent


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_id(value: str, field_name: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", value or ""):
        raise ValueError(f"invalid {field_name}")
    return value


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


class ClassroomStorage:
    def __init__(self, backend_dir: str) -> None:
        self.backend_dir = backend_dir
        self.memory_root = os.path.join(backend_dir, "memory", "users")
        self._event_locks: dict[tuple[str, str], threading.Lock] = {}
        self._event_locks_guard = threading.Lock()
        self._answer_locks: dict[tuple[str, str], threading.Lock] = {}
        self._answer_locks_guard = threading.Lock()

    def _answer_lock(self, user_id: str, classroom_id: str) -> threading.Lock:
        key = (user_id, classroom_id)
        with self._answer_locks_guard:
            return self._answer_locks.setdefault(key, threading.Lock())

    def classroom_dir(self, user_id: str, classroom_id: str, create: bool = True) -> str:
        user_id = _safe_id(user_id, "user_id")
        classroom_id = _safe_id(classroom_id, "classroom_id")
        path = os.path.join(
            self.memory_root,
            user_id,
            "interactive_classrooms",
            classroom_id,
        )
        if create:
            os.makedirs(path, exist_ok=True)
        return path

    def audio_dir(self, user_id: str, classroom_id: str) -> str:
        path = os.path.join(self.classroom_dir(user_id, classroom_id), "audio")
        os.makedirs(path, exist_ok=True)
        return path

    def _write_json_file(self, path: str, payload: dict[str, Any]) -> None:
        temp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def save_classroom(self, user_id: str, classroom_id: str, payload: dict[str, Any]) -> str:
        path = os.path.join(self.classroom_dir(user_id, classroom_id), "classroom.json")
        payload["updated_at"] = _now_iso()
        self._write_json_file(path, payload)
        return path

    def load_classroom(self, user_id: str, classroom_id: str) -> dict[str, Any] | None:
        path = os.path.join(self.classroom_dir(user_id, classroom_id, create=False), "classroom.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def rename_classroom(self, user_id: str, classroom_id: str, title: str) -> bool:
        title = (title or "").strip()
        if not title:
            return False
        classroom = self.load_classroom(user_id, classroom_id)
        if classroom is None:
            return False
        classroom["title"] = title[:80]
        self.save_classroom(user_id, classroom_id, classroom)
        return True

    def delete_classroom(self, user_id: str, classroom_id: str) -> bool:
        cdir = self.classroom_dir(user_id, classroom_id, create=False)
        root = os.path.join(self.memory_root, _safe_id(user_id, "user_id"), "interactive_classrooms")
        abs_root = os.path.abspath(root)
        abs_dir = os.path.abspath(cdir)
        if not abs_dir.startswith(abs_root + os.sep):
            raise ValueError("invalid classroom path")
        if not os.path.exists(abs_dir):
            return False
        shutil.rmtree(abs_dir)
        return True

    def delete_all_classrooms(self, user_id: str) -> int:
        user_id = _safe_id(user_id, "user_id")
        root = os.path.join(self.memory_root, user_id, "interactive_classrooms")
        if not os.path.exists(root):
            return 0
        count = 0
        for classroom_id in os.listdir(root):
            cdir = os.path.join(root, classroom_id)
            if not os.path.isdir(cdir):
                continue
            shutil.rmtree(cdir)
            count += 1
        return count

    def save_answers(
        self,
        user_id: str,
        classroom_id: str,
        scene_id: str,
        answers_payload: dict[str, Any],
    ) -> None:
        with self._answer_lock(user_id, classroom_id):
            path = os.path.join(self.classroom_dir(user_id, classroom_id), "answers.json")
            existing: dict[str, Any] = {"scenes": {}}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.setdefault("scenes", {})
            existing["scenes"][scene_id] = answers_payload
            existing["updated_at"] = _now_iso()
            self._write_json_file(path, existing)

    def load_answers(self, user_id: str, classroom_id: str) -> dict[str, Any]:
        path = os.path.join(self.classroom_dir(user_id, classroom_id, create=False), "answers.json")
        if not os.path.exists(path):
            return {"scenes": {}}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_report(self, user_id: str, classroom_id: str, payload: dict[str, Any]) -> None:
        path = os.path.join(self.classroom_dir(user_id, classroom_id), "report.json")
        payload["updated_at"] = _now_iso()
        self._write_json_file(path, payload)

    def load_report(self, user_id: str, classroom_id: str) -> dict[str, Any] | None:
        path = os.path.join(
            self.classroom_dir(user_id, classroom_id, create=False),
            "report.json",
        )
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None

    def load_knowledge_point_cache(
        self,
        user_id: str,
        classroom_id: str,
    ) -> list[dict[str, Any]]:
        path = os.path.join(
            self.classroom_dir(user_id, classroom_id, create=False),
            "knowledge_point_map.json",
        )
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        rows = payload.get("knowledge_points", []) if isinstance(payload, dict) else []
        return rows if isinstance(rows, list) else []

    def save_knowledge_point_cache(
        self,
        user_id: str,
        classroom_id: str,
        rows: list[dict[str, Any]],
    ) -> None:
        path = os.path.join(
            self.classroom_dir(user_id, classroom_id),
            "knowledge_point_map.json",
        )
        self._write_json_file(
            path,
            {
                "knowledge_points": rows,
                "updated_at": _now_iso(),
            },
        )

    def list_classrooms(self, user_id: str) -> list[dict[str, Any]]:
        user_id = _safe_id(user_id, "user_id")
        root = os.path.join(self.memory_root, user_id, "interactive_classrooms")
        if not os.path.exists(root):
            return []
        rows: list[dict[str, Any]] = []
        for classroom_id in os.listdir(root):
            cdir = os.path.join(root, classroom_id)
            if not os.path.isdir(cdir):
                continue
            cpath = os.path.join(cdir, "classroom.json")
            if not os.path.exists(cpath):
                continue
            try:
                with open(cpath, "r", encoding="utf-8") as f:
                    c = json.load(f)
                rows.append(
                    {
                        "id": c.get("id", classroom_id),
                        "title": c.get("title", ""),
                        "topic": c.get("topic", ""),
                        "course": c.get("course", ""),
                        "course_root_id": c.get("course_root_id") or c.get("id", classroom_id),
                        "parent_classroom_id": c.get("parent_classroom_id", ""),
                        "lesson_depth": _safe_int(c.get("lesson_depth", 0), 0),
                        "lesson_index": _safe_int(c.get("lesson_index", 1), 1),
                        "lesson_kind": c.get("lesson_kind", "root"),
                        "scene_count": len(c.get("scenes", [])),
                        "created_at": c.get("created_at", ""),
                        "updated_at": c.get("updated_at", ""),
                        "status": c.get("status", "ready"),
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
        rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return rows

    # ---- 学习事件 (P7) ----

    def _events_path(self, user_id: str, classroom_id: str) -> str:
        return os.path.join(self.classroom_dir(user_id, classroom_id), "learning_events.json")

    def _event_lock(self, user_id: str, classroom_id: str) -> threading.Lock:
        user_id = _safe_id(user_id, "user_id")
        classroom_id = _safe_id(classroom_id, "classroom_id")
        key = (user_id, classroom_id)
        with self._event_locks_guard:
            lock = self._event_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._event_locks[key] = lock
            return lock

    def _load_events_file(self, user_id: str, classroom_id: str) -> dict[str, Any]:
        path = self._events_path(user_id, classroom_id)
        if not os.path.exists(path):
            return {"events": []}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_events_file(self, user_id: str, classroom_id: str, data: dict[str, Any]) -> None:
        path = self._events_path(user_id, classroom_id)
        self._write_json_file(path, data)

    def save_event(self, user_id: str, classroom_id: str, event: "LearningEvent") -> None:
        with self._event_lock(user_id, classroom_id):
            data = self._load_events_file(user_id, classroom_id)
            data["events"].append(event.to_dict())
            data["updated_at"] = _now_iso()
            self._write_events_file(user_id, classroom_id, data)

    def load_events(self, user_id: str, classroom_id: str) -> list[dict[str, Any]]:
        with self._event_lock(user_id, classroom_id):
            data = self._load_events_file(user_id, classroom_id)
        return data.get("events", [])

    def record_event_once(self, user_id: str, classroom_id: str, event: "LearningEvent") -> "LearningEvent":
        """Atomically append an event unless its dedupe_key already exists."""
        with self._event_lock(user_id, classroom_id):
            data = self._load_events_file(user_id, classroom_id)
            events = data.setdefault("events", [])
            if event.dedupe_key:
                for ev_data in events:
                    if ev_data.get("dedupe_key") == event.dedupe_key:
                        from interactive_classroom.schema import LearningEvent
                        return LearningEvent(**{
                            k: v for k, v in ev_data.items()
                            if k in LearningEvent.__dataclass_fields__
                        })
            events.append(event.to_dict())
            data["updated_at"] = _now_iso()
            self._write_events_file(user_id, classroom_id, data)
            return event

    def find_event_by_dedupe_key(
        self, user_id: str, classroom_id: str, dedupe_key: str
    ) -> "LearningEvent | None":
        if not dedupe_key:
            return None
        events = self.load_events(user_id, classroom_id)
        for ev_data in events:
            if ev_data.get("dedupe_key") == dedupe_key:
                from interactive_classroom.schema import LearningEvent
                return LearningEvent(**{k: v for k, v in ev_data.items() if k in LearningEvent.__dataclass_fields__})
        return None
