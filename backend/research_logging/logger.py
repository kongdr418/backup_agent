from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import threading
import uuid
from datetime import datetime
from typing import Any


SCHEMA_VERSION = "research_logging_v1"
RAW_STREAM = "raw_samples"
AI_ANNOTATION_STREAM = "ai_annotations"
FINAL_ANNOTATION_STREAM = "final_annotations"

_PATH_LOCKS: dict[str, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_id(value: str, field_name: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", value or ""):
        raise ValueError(f"invalid {field_name}")
    return value


def _stable_hash(value: Any, length: int = 12) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def learner_id_for_user(user_id: str) -> str:
    return f"S{_stable_hash(user_id, 6).upper()}"


def _path_lock(path: str) -> threading.Lock:
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(path)
        if lock is None:
            lock = threading.Lock()
            _PATH_LOCKS[path] = lock
        return lock


def _truncate_text(value: Any, limit: int = 4000) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _redact_llm_config(config: dict[str, Any] | None) -> dict[str, str]:
    config = config or {}
    return {
        "model_version": str(config.get("content_model") or config.get("model") or ""),
        "provider_type": str(config.get("content_provider_type") or config.get("provider_type") or ""),
    }


def _last_user_message(conversation: list[dict[str, Any]]) -> str:
    for item in reversed(conversation or []):
        if item.get("role") == "user" and str(item.get("content") or "").strip():
            return str(item.get("content") or "").strip()
    return ""


def _current_scene(classroom: dict[str, Any], scene_id: str) -> dict[str, Any]:
    for scene in classroom.get("scenes") or []:
        if scene.get("id") == scene_id:
            return scene
    return {}


def _scene_context(scene: dict[str, Any]) -> dict[str, Any]:
    if not scene:
        return {}
    content = scene.get("content") or {}
    text_parts: list[str] = []
    for value in content.get("extracted_text") or []:
        if value:
            text_parts.append(str(value))
    if content.get("markdown"):
        text_parts.append(str(content.get("markdown")))
    for question in content.get("questions") or []:
        if question.get("question"):
            text_parts.append(str(question.get("question")))
        if question.get("analysis"):
            text_parts.append(str(question.get("analysis")))
    for action in scene.get("actions") or []:
        if action.get("text"):
            text_parts.append(str(action.get("text")))
    return {
        "scene_id": scene.get("id", ""),
        "scene_type": scene.get("type", ""),
        "scene_title": scene.get("title", ""),
        "knowledge_points": scene.get("knowledge_points") or [],
        "text_excerpt": _truncate_text("\n".join(text_parts), 2000),
    }


def _conversation_window(conversation: list[dict[str, Any]], limit: int = 8) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in (conversation or [])[-limit:]:
        role = str(item.get("role") or "")
        content = _truncate_text(item.get("content"), 1200)
        if role in {"user", "assistant"} and content:
            rows.append({"role": role, "content": content})
    return rows


def _memory_entries_from_classroom(classroom: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for memory_type, field_name in (
        ("progress", "student_profile"),
        ("progress", "generation_strategy"),
        ("knowledge", "knowledge_points"),
    ):
        value = classroom.get(field_name)
        if value:
            entries.append(
                {
                    "memory_id": f"mem_{field_name}_{_stable_hash(value)}",
                    "memory_type": memory_type,
                    "source_field": field_name,
                    "memory_text": _truncate_text(value, 2500),
                    "evidence_quality": "inferred" if field_name != "knowledge_points" else "direct",
                    "status": "active",
                }
            )
    return entries


def _knowledge_evidence_from_context(knowledge_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(knowledge_context, dict):
        return []
    evidence_rows: list[dict[str, Any]] = []
    for idx, item in enumerate(knowledge_context.get("evidence") or []):
        evidence_id = str(item.get("chunk_id") or item.get("id") or f"evidence_{idx}")
        evidence_rows.append(
            {
                "evidence_id": evidence_id,
                "knowledge_point_ids": item.get("knowledge_point_ids") or [],
                "evidence_label": item.get("evidence_label") or "",
                "source_name": item.get("source_name") or "",
                "relevance_score": item.get("relevance_score"),
                "text_excerpt": _truncate_text(item.get("text"), 800),
            }
        )
    return evidence_rows


class ResearchLogger:
    """Append-only JSONL logger aligned with the paper's experiment tables."""

    def __init__(
        self,
        *,
        memory_root: str,
        enabled: bool | None = None,
        now_provider: Any | None = None,
        id_provider: Any | None = None,
    ) -> None:
        self.memory_root = memory_root
        self.enabled = enabled
        self.now_provider = now_provider or _now_iso
        self.id_provider = id_provider or (lambda: uuid.uuid4().hex)

    def is_enabled(self) -> bool:
        if self.enabled is not None:
            return self.enabled
        return os.environ.get("RESEARCH_LOGGING_ENABLED", "true").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    def research_dir(self, user_id: str) -> str:
        safe_user_id = _safe_id(user_id or "anonymous", "user_id")
        return os.path.join(self.memory_root, safe_user_id, "research_logs")

    def stream_path(self, user_id: str, stream: str) -> str:
        if stream not in {RAW_STREAM, AI_ANNOTATION_STREAM, FINAL_ANNOTATION_STREAM}:
            raise ValueError("invalid research stream")
        return os.path.join(self.research_dir(user_id), f"{stream}.jsonl")

    def list_research_user_ids(self, stream: str = RAW_STREAM) -> list[str]:
        if stream not in {RAW_STREAM, AI_ANNOTATION_STREAM, FINAL_ANNOTATION_STREAM}:
            raise ValueError("invalid research stream")
        if not os.path.isdir(self.memory_root):
            return []
        user_ids: list[str] = []
        for name in os.listdir(self.memory_root):
            try:
                safe_name = _safe_id(name, "user_id")
            except ValueError:
                continue
            path = self.stream_path(safe_name, stream)
            if os.path.exists(path):
                user_ids.append(safe_name)
        return sorted(user_ids)

    def append(self, user_id: str, stream: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.is_enabled():
            return None
        payload = dict(payload)
        payload.setdefault("schema_version", SCHEMA_VERSION)
        payload.setdefault("event_id", f"evt_{self.id_provider()}")
        payload.setdefault("created_at", self.now_provider())
        payload.setdefault("user_id", user_id)
        payload.setdefault("learner_id", learner_id_for_user(user_id))

        path = self.stream_path(user_id, stream)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with _path_lock(path):
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                f.write("\n")
        return payload

    def list_records(self, user_id: str, stream: str = RAW_STREAM, limit: int = 100) -> list[dict[str, Any]]:
        path = self.stream_path(user_id, stream)
        if not os.path.exists(path):
            return []
        records: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if limit > 0:
            return records[-limit:]
        return records

    def _research_label(self, user_id: str) -> str:
        profile_path = os.path.join(self.memory_root, user_id, "learner_profile.json")
        if not os.path.exists(profile_path):
            return user_id
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except (OSError, json.JSONDecodeError):
            return user_id
        basic = profile.get("basic") if isinstance(profile, dict) else {}
        display_name = basic.get("display_name") if isinstance(basic, dict) else ""
        return str(display_name or user_id)

    def list_records_all_users(self, stream: str = RAW_STREAM, limit: int = 100) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for user_id in self.list_research_user_ids(stream):
            label = self._research_label(user_id)
            for record in self.list_records(user_id, stream, limit=0):
                row = dict(record)
                row["research_user_id"] = user_id
                row["research_label"] = label
                records.append(row)
        records.sort(key=lambda item: str(item.get("created_at") or item.get("timestamp") or ""))
        if limit > 0:
            return records[-limit:]
        return records

    def find_raw_sample(self, user_id: str, output_id: str) -> dict[str, Any] | None:
        for record in reversed(self.list_records(user_id, RAW_STREAM, limit=0)):
            if record.get("output_id") == output_id:
                return record
        return None

    def find_raw_sample_all_users(self, output_id: str) -> tuple[str, dict[str, Any]] | None:
        for user_id in self.list_research_user_ids(RAW_STREAM):
            sample = self.find_raw_sample(user_id, output_id)
            if sample is not None:
                row = dict(sample)
                row["research_user_id"] = user_id
                row["research_label"] = self._research_label(user_id)
                return user_id, row
        return None

    def record_discussion_sample(
        self,
        *,
        user_id: str,
        classroom: dict[str, Any],
        discussion: dict[str, Any],
        response: str,
        llm_config: dict[str, Any] | None,
        streaming: bool,
        assistant_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        output_id = f"out_{self.id_provider()}"
        conversation = discussion.get("messages") or []
        scene_id = discussion.get("current_scene_id") or ""
        scene = _current_scene(classroom, scene_id)
        memory_entries = _memory_entries_from_classroom(classroom)
        llm_meta = _redact_llm_config(llm_config)
        payload = {
            "event_type": "interaction_log",
            "output_id": output_id,
            "source": "classroom_discussion",
            "session_id": classroom.get("id", ""),
            "classroom_id": classroom.get("id", ""),
            "task_id": classroom.get("topic", "") or classroom.get("title", ""),
            "turn_id": len(conversation),
            "prompt": _truncate_text(_last_user_message(conversation), 4000),
            "response": _truncate_text(response, 8000),
            "task_context": _scene_context(scene),
            "current_code_or_submission": "",
            "code_before": "",
            "code_after": "",
            "timestamp": self.now_provider(),
            "original_condition": "memory-aware",
            "memory_ids": [item["memory_id"] for item in memory_entries],
            "memory_context": memory_entries,
            "memory_evidence": memory_entries,
            "knowledge_evidence_ids": [],
            "model_version": llm_meta["model_version"],
            "provider_type": llm_meta["provider_type"],
            "prompt_template_version": "classroom_discussion_v1",
            "played_scene_ids": discussion.get("played_scene_ids") or [],
            "conversation_window": _conversation_window(conversation),
            "trigger": discussion.get("trigger") or "",
            "quick_action": discussion.get("quick_action") or "",
            "multi_agent": bool(discussion.get("multi_agent")),
            "streaming": streaming,
            "assistant_messages": assistant_messages or [],
        }
        return self.append(user_id, RAW_STREAM, payload)

    def record_generation_context(
        self,
        *,
        user_id: str,
        request_id: str,
        topic: str,
        course: str,
        generation_kwargs: dict[str, Any],
        classroom_payload: dict[str, Any] | None,
        status: str,
    ) -> dict[str, Any] | None:
        knowledge_context = generation_kwargs.get("knowledge_context")
        knowledge_evidence = _knowledge_evidence_from_context(knowledge_context)
        student_profile = generation_kwargs.get("student_profile") or {}
        generation_strategy = generation_kwargs.get("generation_strategy") or {}
        memory_entries = []
        for field_name, value in (
            ("student_profile", student_profile),
            ("generation_strategy", generation_strategy),
        ):
            if value:
                memory_entries.append(
                    {
                        "memory_id": f"mem_{field_name}_{_stable_hash(value)}",
                        "memory_type": "progress",
                        "source_field": field_name,
                        "memory_text": _truncate_text(value, 3000),
                        "evidence_quality": "inferred",
                        "status": "active",
                    }
                )
        payload = {
            "event_type": "generation_context",
            "source": "classroom_generation",
            "output_id": f"gen_{self.id_provider()}",
            "request_id": request_id,
            "classroom_id": (classroom_payload or {}).get("id", ""),
            "session_id": (classroom_payload or {}).get("id", request_id),
            "task_id": topic,
            "course": course,
            "topic": topic,
            "status": status,
            "timestamp": self.now_provider(),
            "original_condition": "memory-aware",
            "memory_ids": [item["memory_id"] for item in memory_entries],
            "memory_context": memory_entries,
            "memory_evidence": memory_entries,
            "knowledge_evidence_ids": [item["evidence_id"] for item in knowledge_evidence],
            "knowledge_evidence": knowledge_evidence,
            "knowledge_context_summary": {
                "course_id": (knowledge_context or {}).get("course_id", "") if isinstance(knowledge_context, dict) else "",
                "course_name": (knowledge_context or {}).get("course_name", "") if isinstance(knowledge_context, dict) else "",
                "knowledge_points": (knowledge_context or {}).get("knowledge_points", []) if isinstance(knowledge_context, dict) else [],
                "lesson_count": len((knowledge_context or {}).get("lessons", [])) if isinstance(knowledge_context, dict) else 0,
            },
            "prompt_template_version": "classroom_generation_v1",
        }
        return self.append(user_id, RAW_STREAM, payload)

    def record_ai_annotation(
        self,
        *,
        user_id: str,
        sample: dict[str, Any],
        annotation: dict[str, Any],
        model_version: str = "",
        provider_type: str = "",
    ) -> dict[str, Any] | None:
        payload = {
            "event_type": "risk_annotation",
            "annotation_id": f"ann_ai_{self.id_provider()}",
            "output_id_or_replay_id": sample.get("output_id", ""),
            "annotation_scope": "output",
            "annotator": "llm",
            "rater_id": "LLM",
            "model_version": model_version,
            "provider_type": provider_type,
            **annotation,
        }
        return self.append(user_id, AI_ANNOTATION_STREAM, payload)

    def record_final_annotation(
        self,
        *,
        user_id: str,
        output_id: str,
        annotation: dict[str, Any],
    ) -> dict[str, Any] | None:
        payload = {
            "event_type": "risk_annotation",
            "annotation_id": f"ann_final_{self.id_provider()}",
            "output_id_or_replay_id": output_id,
            "annotation_scope": annotation.get("annotation_scope") or "output",
            "annotator": annotation.get("annotator") or "human",
            "rater_id": annotation.get("rater_id") or "R1",
            **annotation,
        }
        return self.append(user_id, FINAL_ANNOTATION_STREAM, payload)

    def _records_to_csv(self, records: list[dict[str, Any]]) -> str:
        fields = [
            "research_user_id",
            "research_label",
            "output_id",
            "learner_id",
            "session_id",
            "task_id",
            "turn_id",
            "prompt",
            "response",
            "timestamp",
            "original_condition",
            "memory_ids",
            "memory_context",
            "memory_evidence",
            "model_version",
            "prompt_template_version",
            "source",
            "classroom_id",
            "trigger",
            "quick_action",
        ]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            for key in ("memory_ids", "memory_context", "memory_evidence"):
                row[key] = json.dumps(row.get(key) or [], ensure_ascii=False)
            writer.writerow(row)
        return buffer.getvalue()

    def export_csv(self, user_id: str) -> str:
        records = self.list_records(user_id, RAW_STREAM, limit=0)
        return self._records_to_csv(records)

    def export_csv_all_users(self) -> str:
        return self._records_to_csv(self.list_records_all_users(RAW_STREAM, limit=0))
