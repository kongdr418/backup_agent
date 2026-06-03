from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_id(value: str, field_name: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", value or ""):
        raise ValueError(f"invalid {field_name}")
    return value


class ClassroomStorage:
    def __init__(self, backend_dir: str) -> None:
        self.backend_dir = backend_dir
        self.memory_root = os.path.join(backend_dir, "memory", "users")

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

    def save_classroom(self, user_id: str, classroom_id: str, payload: dict[str, Any]) -> str:
        path = os.path.join(self.classroom_dir(user_id, classroom_id), "classroom.json")
        payload["updated_at"] = _now_iso()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
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

    def save_answers(
        self,
        user_id: str,
        classroom_id: str,
        scene_id: str,
        answers_payload: dict[str, Any],
    ) -> None:
        path = os.path.join(self.classroom_dir(user_id, classroom_id), "answers.json")
        existing: dict[str, Any] = {"scenes": {}}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.setdefault("scenes", {})
        existing["scenes"][scene_id] = answers_payload
        existing["updated_at"] = _now_iso()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def load_answers(self, user_id: str, classroom_id: str) -> dict[str, Any]:
        path = os.path.join(self.classroom_dir(user_id, classroom_id, create=False), "answers.json")
        if not os.path.exists(path):
            return {"scenes": {}}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_report(self, user_id: str, classroom_id: str, payload: dict[str, Any]) -> None:
        path = os.path.join(self.classroom_dir(user_id, classroom_id), "report.json")
        payload["updated_at"] = _now_iso()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

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
