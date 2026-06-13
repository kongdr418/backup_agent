from __future__ import annotations

import json
import os
import queue
import re
import threading
from datetime import datetime
from typing import Any


class ClassroomGenerationJobService:
    def __init__(
        self,
        *,
        jobs_dir: str,
        logger: Any,
        orphan_timeout_seconds: int = 90,
    ) -> None:
        self.jobs_dir = jobs_dir
        self.logger = logger
        self.orphan_timeout_seconds = orphan_timeout_seconds
        self.cancels: dict[str, threading.Event] = {}
        self.jobs: dict[str, dict] = {}
        self.cancels_lock = threading.Lock()
        self.subscribers: dict[str, list[queue.Queue]] = {}
        self.subscribers_lock = threading.Lock()

    @staticmethod
    def is_safe_request_id(value: str) -> bool:
        return bool(re.match(r"^[a-zA-Z0-9_.:-]{1,128}$", value or ""))

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def register(self, request_id: str) -> threading.Event | None:
        if not request_id:
            return None
        with self.cancels_lock:
            event = self.cancels.get(request_id)
            if event is None:
                event = threading.Event()
                self.cancels[request_id] = event
            return event

    def _job_path(self, request_id: str) -> str:
        if not self.is_safe_request_id(request_id):
            return ""
        safe_name = request_id.replace(":", "-")
        return os.path.join(self.jobs_dir, f"{safe_name}.json")

    def _write_job_file(self, request_id: str, job: dict) -> None:
        path = self._job_path(request_id)
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temp_path = f"{path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(job, file, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except Exception:
            self.logger.warning(
                f"[INTERACTIVE-CLASSROOM] 写入生成任务快照失败 request_id={request_id}",
                exc_info=True,
            )

    def _read_job_file(self, request_id: str) -> dict | None:
        path = self._job_path(request_id)
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            if isinstance(payload, dict):
                return payload
        except Exception:
            self.logger.warning(
                f"[INTERACTIVE-CLASSROOM] 读取生成任务快照失败 request_id={request_id}",
                exc_info=True,
            )
        return None

    @staticmethod
    def elapsed_seconds(job: dict, now: datetime | None = None) -> int:
        started_at = job.get("started_at")
        if not started_at:
            return 0
        try:
            start = datetime.fromisoformat(started_at)
            current = now or datetime.now()
            return max(0, int((current - start).total_seconds()))
        except (TypeError, ValueError):
            return 0

    def _mark_orphaned_locked(self, request_id: str, job: dict) -> dict:
        now = self.now()
        try:
            now_dt = datetime.fromisoformat(now)
        except ValueError:
            now_dt = datetime.now()
        next_job = {
            **job,
            "request_id": request_id,
            "status": "error",
            "updated_at": now,
            "error": "课堂生成任务已中断，请重新生成",
        }
        next_job["elapsed_seconds"] = self.elapsed_seconds(next_job, now_dt)
        self.jobs[request_id] = next_job
        self._write_job_file(request_id, next_job)
        return next_job

    def _normalize_locked(self, request_id: str, job: dict) -> dict:
        if job.get("status") not in {"running", "cancelling"} or request_id in self.cancels:
            return job
        timestamp = job.get("updated_at") or job.get("started_at")
        if not timestamp:
            return job
        try:
            age_seconds = (datetime.now() - datetime.fromisoformat(timestamp)).total_seconds()
        except (TypeError, ValueError):
            return job
        if age_seconds >= self.orphan_timeout_seconds:
            return self._mark_orphaned_locked(request_id, job)
        return job

    def _prune_locked(self, max_jobs: int = 80) -> None:
        if len(self.jobs) <= max_jobs:
            return
        removable = [
            (job.get("updated_at") or job.get("started_at") or "", request_id)
            for request_id, job in self.jobs.items()
            if job.get("status") not in {"running", "cancelling"}
        ]
        removable.sort()
        for _, request_id in removable[:max(0, len(self.jobs) - max_jobs)]:
            self.jobs.pop(request_id, None)

    def mark_running(self, request_id: str, topic: str) -> dict | None:
        if not request_id:
            return None
        now = self.now()
        with self.cancels_lock:
            current = self.jobs.get(request_id, {})
            job = {
                **current,
                "request_id": request_id,
                "topic": topic,
                "status": "running",
                "started_at": current.get("started_at") or now,
                "updated_at": now,
                "progress_events": current.get("progress_events") or [],
                "progress_event_count": current.get("progress_event_count") or 0,
                "elapsed_seconds": current.get("elapsed_seconds") or 0,
            }
            self.jobs[request_id] = job
            self._write_job_file(request_id, job)
            self._prune_locked()
            return dict(job)

    def mark_done(self, request_id: str, classroom_id: str, classroom: dict) -> dict | None:
        if not request_id:
            return None
        now = self.now()
        with self.cancels_lock:
            current = self.jobs.get(request_id, {})
            job = {
                **current,
                "request_id": request_id,
                "status": "done",
                "classroom_id": classroom_id,
                "classroom": classroom,
                "scenes_generated": len(classroom.get("scenes", [])),
                "total_scenes": len(classroom.get("scenes", [])),
                "updated_at": now,
            }
            job["elapsed_seconds"] = self.elapsed_seconds(job, datetime.fromisoformat(now))
            self.jobs[request_id] = job
            self._write_job_file(request_id, job)
            self._prune_locked()
            return dict(job)

    def mark_cancelled(self, request_id: str) -> dict | None:
        if not request_id:
            return None
        now = self.now()
        with self.cancels_lock:
            current = self.jobs.get(request_id, {})
            job = {
                **current,
                "request_id": request_id,
                "status": "cancelled",
                "updated_at": now,
                "error": "课堂生成已停止",
            }
            job["elapsed_seconds"] = self.elapsed_seconds(job, datetime.fromisoformat(now))
            self.jobs[request_id] = job
            self._write_job_file(request_id, job)
            self._prune_locked()
            return dict(job)

    def mark_error(self, request_id: str, error: str) -> dict | None:
        if not request_id:
            return None
        now = self.now()
        with self.cancels_lock:
            current = self.jobs.get(request_id, {})
            job = {
                **current,
                "request_id": request_id,
                "status": "error",
                "updated_at": now,
                "error": error,
            }
            job["elapsed_seconds"] = self.elapsed_seconds(job, datetime.fromisoformat(now))
            self.jobs[request_id] = job
            self._write_job_file(request_id, job)
            self._prune_locked()
            return dict(job)

    def get_job(self, request_id: str) -> dict | None:
        if not request_id:
            return None
        with self.cancels_lock:
            job = self.jobs.get(request_id)
            if job:
                job = self._normalize_locked(request_id, job)
                self.jobs[request_id] = job
                return dict(job)
            disk_job = self._read_job_file(request_id)
            if disk_job:
                disk_job = self._normalize_locked(request_id, disk_job)
                self.jobs[request_id] = disk_job
                return dict(disk_job)
            return None

    def get_progress_events(self, request_id: str) -> list[dict]:
        if not request_id:
            return []
        with self.cancels_lock:
            job = self.jobs.get(request_id) or {}
            return [
                dict(event)
                for event in job.get("progress_events", [])
                if isinstance(event, dict)
            ]

    def record_progress(self, request_id: str, event: dict) -> None:
        if not request_id or event.get("type") != "classroom_progress":
            return
        now_text = self.now()
        try:
            now_dt = datetime.fromisoformat(now_text)
        except ValueError:
            now_dt = datetime.now()
        with self.cancels_lock:
            current = self.jobs.get(request_id)
            if not current:
                return
            progress_events = [
                dict(row)
                for row in current.get("progress_events", [])
                if isinstance(row, dict)
            ]
            progress_events.append(dict(event))
            progress_events = progress_events[-80:]

            scene = event.get("scene") if isinstance(event.get("scene"), dict) else None
            generated_scene_count = int(current.get("scenes_generated") or 0)
            if scene:
                generated_scene_count = max(generated_scene_count, int(event.get("scene_index") or 0))

            job = {
                **current,
                "status": current.get("status") or "running",
                "stage": event.get("stage") or "",
                "stage_label": event.get("stage_label") or "",
                "stage_index": int(event.get("stage_index") or 0),
                "stage_total": int(event.get("stage_total") or 0),
                "current_step_done": int(event.get("scene_index") or 0),
                "current_step_total": int(event.get("scene_total") or 0),
                "scene_index": int(event.get("scene_index") or 0),
                "scene_total": int(event.get("scene_total") or 0),
                "scenes_generated": generated_scene_count,
                "progress_events": progress_events,
                "progress_event_count": int(current.get("progress_event_count") or 0) + 1,
                "updated_at": now_text,
            }
            if scene:
                job["last_scene"] = dict(scene)
                job["total_scenes"] = max(
                    int(current.get("total_scenes") or 0),
                    int(event.get("scene_total") or 0),
                )
            elif "total_scenes" not in job:
                job["total_scenes"] = int(current.get("total_scenes") or 0)
            job["elapsed_seconds"] = self.elapsed_seconds(job, now_dt)
            self.jobs[request_id] = job
            self._write_job_file(request_id, job)

    def finish(self, request_id: str) -> None:
        if not request_id:
            return
        with self.cancels_lock:
            self.cancels.pop(request_id, None)

    def cancel(self, request_id: str) -> bool:
        with self.cancels_lock:
            event = self.cancels.get(request_id)
            if event is None:
                return False
            event.set()
            job = self.jobs.get(request_id)
            if job and job.get("status") == "running":
                self.jobs[request_id] = {
                    **job,
                    "status": "cancelling",
                    "updated_at": self.now(),
                }
                self._write_job_file(request_id, self.jobs[request_id])
            return True

    def subscribe(self, request_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=512)
        with self.subscribers_lock:
            self.subscribers.setdefault(request_id, []).append(q)
        return q

    def unsubscribe(self, request_id: str, q: queue.Queue) -> None:
        with self.subscribers_lock:
            subs = self.subscribers.get(request_id)
            if not subs:
                return
            if q in subs:
                subs.remove(q)
            if not subs:
                self.subscribers.pop(request_id, None)

    def emit(self, request_id: str, event: dict) -> None:
        self.record_progress(request_id, event)
        with self.subscribers_lock:
            subs = self.subscribers.get(request_id, [])
            for q in subs:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass

    def close_subscribers(self, request_id: str) -> None:
        with self.subscribers_lock:
            subs = self.subscribers.get(request_id, [])
            for q in subs:
                try:
                    q.put_nowait(None)
                except queue.Full:
                    pass
