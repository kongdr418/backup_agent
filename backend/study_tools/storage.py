"""学习工具存储:错题本 + 闪卡。

单文件 JSON + 原子写盘 + 进程内锁,沿用 learner_profile.storage 模式。
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import date, datetime
from typing import Any

from . import srs


VERSION = 1
_SAFE_USER_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
_SAFE_ID = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")
# 附件 id 收紧到字母数字+下划线(避免与 _SAFE_ID 的 dot/dash 冲突导致 URL 解析歧义)
_SAFE_ATT_ID = re.compile(r"^[A-Za-z0-9_]{1,32}$")

ALLOWED_IMAGE_EXTS: set[str] = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}
ALLOWED_IMAGE_MIMES: set[str] = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/x-ms-bmp",
}
MAX_ATTACHMENTS_PER_MISTAKE = 9
# 图片魔数:用于在保存前做最小白名单嗅探,避免靠扩展名被骗
_IMAGE_MAGIC: dict[bytes, set[str]] = {
    b"\x89PNG\r\n\x1a\n": {"png"},
    b"\xff\xd8\xff": {"jpg", "jpeg"},
    b"GIF87a": {"gif"},
    b"GIF89a": {"gif"},
    b"RIFF": {"webp"},  # RIFF....WEBP 在更靠后位置再校验
    b"BM": {"bmp"},
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today_iso() -> str:
    return date.today().isoformat()


def _clean_text(value: Any, max_length: int = 200) -> str:
    return " ".join(str(value or "").split())[:max_length]


def _clean_list(value: Any, max_items: int = 16, item_len: int = 40) -> list[str]:
    if isinstance(value, str):
        rows = re.split(r"[,，、|/]", value)
    elif isinstance(value, list):
        rows = value
    else:
        rows = []
    out: list[str] = []
    for row in rows:
        text = _clean_text(row, item_len)
        if text and text not in out:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _normalize_options(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        out: list[str] = []
        for v in value:
            if isinstance(v, dict):
                label = v.get("label") or v.get("value") or v.get("text") or ""
                text = _clean_text(label, 500)
            else:
                text = _clean_text(v, 500)
            if text and text not in out:
                out.append(text)
            if len(out) >= 16:
                break
        return out or None
    return None


_ALLOWED_QUESTION_TYPES = {"single", "multiple", "short_answer"}


def _clean_question_type(value: Any) -> str:
    """归一化题型白名单：single/multiple/short_answer，其它值降级为 short_answer。"""
    text = str(value or "").strip().lower()
    if text in _ALLOWED_QUESTION_TYPES:
        return text
    if text in {"单选", "单选题"}:
        return "single"
    if text in {"多选", "多选题"}:
        return "multiple"
    if text in {"简答", "简答题", "问答", "问答题", "essay", "open"}:
        return "short_answer"
    return ""


def _normalize_collection_ids(value: Any) -> list[str]:
    """归一化错题集 ID 列表:去重、白名单校验。"""
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        text = _clean_text(raw, 64)
        if not text or not _SAFE_ID.fullmatch(text) or text in seen:
            continue
        out.append(text)
        seen.add(text)
        if len(out) >= 32:
            break
    return out


def _normalize_attachments(value: Any) -> list[dict[str, Any]]:
    """归一化错题附件列表:剔除非法项、去重、限长。

    期望每项形如 {id, name, url, mime, size, uploaded_at}。
    """
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            continue
        att_id = _clean_text(raw.get("id"), 32)
        if not att_id or not _SAFE_ATT_ID.fullmatch(att_id) or att_id in seen:
            continue
        name = _clean_text(raw.get("name"), 180) or att_id
        url = _clean_text(raw.get("url"), 240)
        mime = _clean_text(raw.get("mime"), 64) or "application/octet-stream"
        try:
            size = int(raw.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        size = max(0, min(size, 50 * 1024 * 1024))
        uploaded_at = _clean_text(raw.get("uploaded_at"), 40) or _now_iso()
        out.append({
            "id": att_id,
            "name": name,
            "url": url,
            "mime": mime,
            "size": size,
            "uploaded_at": uploaded_at,
        })
        seen.add(att_id)
        if len(out) >= MAX_ATTACHMENTS_PER_MISTAKE:
            break
    return out


def _guess_image_ext(filename: str, mime: str | None) -> str | None:
    """根据文件名 / mime 推回允许的图片后缀。返回 None 表示不可信。"""
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in ALLOWED_IMAGE_EXTS:
            return "jpg" if ext == "jpeg" else ext
    if mime:
        m = mime.lower().split(";", 1)[0].strip()
        if m == "image/png":
            return "png"
        if m in ("image/jpeg", "image/jpg"):
            return "jpg"
        if m == "image/gif":
            return "gif"
        if m == "image/webp":
            return "webp"
        if m in ("image/bmp", "image/x-ms-bmp"):
            return "bmp"
    return None


def _sniff_image_ext(head: bytes) -> str | None:
    """基于文件头魔数嗅探图片格式。head 至少 16 字节。

    返回归一化后缀(png/jpg/gif/webp/bmp),不匹配返回 None。
    注意:为与 _guess_image_ext 保持一致,JPEG 一律归一化为 "jpg"。
    """
    if not head:
        return None
    for magic, exts in _IMAGE_MAGIC.items():
        if head.startswith(magic):
            if "webp" in exts:
                # RIFF 容器:需确认 8..11 是 WEBP
                if len(head) >= 12 and head[8:12] == b"WEBP":
                    return "webp"
                continue
            ext = next(iter(exts))
            return "jpg" if ext == "jpeg" else ext
    return None


def _normalize_mistake(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    now = _now_iso()
    base = existing or {}
    collection_ids = _normalize_collection_ids(
        payload.get("collection_ids") if "collection_ids" in payload else base.get("collection_ids")
    )
    attachments = _normalize_attachments(
        payload.get("attachments") if "attachments" in payload else base.get("attachments")
    )
    return {
        "id": _clean_text(base.get("id") or payload.get("id"), 64) or f"mk_{uuid.uuid4().hex[:16]}",
        "source": _clean_text(payload.get("source") or base.get("source") or "manual", 32) or "manual",
        "source_evidence_id": _clean_text(
            payload.get("source_evidence_id") or base.get("source_evidence_id"),
            180,
        ) or None,
        "source_ref": {
            "classroom_id": _clean_text(
                (payload.get("source_ref") or {}).get("classroom_id")
                if isinstance(payload.get("source_ref"), dict)
                else (base.get("source_ref") or {}).get("classroom_id"),
                80,
            ),
            "scene_id": _clean_text(
                (payload.get("source_ref") or {}).get("scene_id")
                if isinstance(payload.get("source_ref"), dict)
                else (base.get("source_ref") or {}).get("scene_id"),
                120,
            ),
            "question_id": _clean_text(
                (payload.get("source_ref") or {}).get("question_id")
                if isinstance(payload.get("source_ref"), dict)
                else (base.get("source_ref") or {}).get("question_id"),
                120,
            ),
        },
        "course_id": _clean_text(payload.get("course_id") or base.get("course_id"), 80),
        "course_name": _clean_text(payload.get("course_name") or base.get("course_name"), 120),
        "knowledge_point_id": _clean_text(
            payload.get("knowledge_point_id") or base.get("knowledge_point_id"),
            80,
        ) or None,
        "knowledge_point_name": _clean_text(
            payload.get("knowledge_point_name") or base.get("knowledge_point_name"),
            80,
        ),
        "stem": _clean_text(payload.get("stem") or base.get("stem"), 4000),
        "question_type": _clean_question_type(
            payload.get("question_type") if "question_type" in payload else base.get("question_type")
        ),
        "options": _normalize_options(
            payload.get("options") if payload.get("options") is not None else base.get("options")
        ),
        "correct_answer": _clean_text(
            payload.get("correct_answer") or base.get("correct_answer"),
            2000,
        ),
        "user_answer": _clean_text(
            payload.get("user_answer") if "user_answer" in payload else base.get("user_answer"),
            2000,
        ) or None,
        "analysis": _clean_text(
            payload.get("analysis") if "analysis" in payload else base.get("analysis"),
            4000,
        ),
        "tags": _clean_list(payload.get("tags") if "tags" in payload else base.get("tags")),
        "collection_ids": collection_ids,
        "attachments": attachments,
        "mastered": _coerce_bool(
            payload.get("mastered") if "mastered" in payload else base.get("mastered"),
            False,
        ),
        "review_count": int(
            payload.get("review_count")
            if "review_count" in payload
            else base.get("review_count") or 0
        ),
        "first_added_at": _clean_text(base.get("first_added_at") or now, 40),
        "last_reviewed_at": _clean_text(
            payload.get("last_reviewed_at")
            if "last_reviewed_at" in payload
            else base.get("last_reviewed_at"),
            40,
        ) or None,
        "mastered_at": _clean_text(
            payload.get("mastered_at")
            if "mastered_at" in payload
            else base.get("mastered_at"),
            40,
        ) or None,
        "updated_at": now,
    }


def _normalize_collection(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    now = _now_iso()
    base = existing or {}
    name = _clean_text(
        payload.get("name") if "name" in payload else base.get("name"),
        32,
    )
    return {
        "id": _clean_text(base.get("id") or payload.get("id"), 64) or f"mc_{uuid.uuid4().hex[:16]}",
        "name": name,
        "created_at": _clean_text(base.get("created_at") or now, 40),
        "updated_at": now,
    }


def _normalize_flashcard(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    now = _now_iso()
    base = existing or {}

    sm2_existing = base.get("sm2") if isinstance(base.get("sm2"), dict) else {}
    sm2_payload = payload.get("sm2") if isinstance(payload.get("sm2"), dict) else {}

    # 注意:不能直接 `payload or existing or default`,因为 0 是合法值(grade<3 时 reps=0 / interval=1 但 EF 可能回退)
    # 用 "in" 区分 "字段缺失" vs "显式给值"
    def _pick_int(field: str, default: int) -> int:
        if field in sm2_payload and sm2_payload[field] is not None:
            return int(sm2_payload[field])
        if field in sm2_existing and sm2_existing[field] is not None:
            return int(sm2_existing[field])
        return default

    def _pick_float(field: str, default: float) -> float:
        if field in sm2_payload and sm2_payload[field] is not None:
            return float(sm2_payload[field])
        if field in sm2_existing and sm2_existing[field] is not None:
            return float(sm2_existing[field])
        return default

    def _pick_str(field: str, default: str) -> str:
        v = sm2_payload.get(field) or sm2_existing.get(field) or default
        return _clean_text(v, 16) if field == "due_date" else _clean_text(v, 16)

    sm2 = {
        "repetitions": _pick_int("repetitions", 0),
        "ease_factor": _pick_float("ease_factor", 2.5),
        "interval_days": _pick_int("interval_days", 0),
        "due_date": _pick_str("due_date", _today_iso()),
        "last_grade": sm2_payload.get("last_grade") if "last_grade" in sm2_payload else sm2_existing.get("last_grade"),
    }

    return {
        "id": _clean_text(base.get("id") or payload.get("id"), 64) or f"fc_{uuid.uuid4().hex[:16]}",
        "source": _clean_text(payload.get("source") or base.get("source") or "manual", 32) or "manual",
        "source_id": _clean_text(payload.get("source_id") or base.get("source_id"), 180) or None,
        "front": _clean_text(payload.get("front") or base.get("front"), 4000),
        "back": _clean_text(payload.get("back") or base.get("back"), 4000),
        "course_id": _clean_text(payload.get("course_id") or base.get("course_id"), 80),
        "course_name": _clean_text(payload.get("course_name") or base.get("course_name"), 120),
        "knowledge_point_id": _clean_text(
            payload.get("knowledge_point_id") or base.get("knowledge_point_id"),
            80,
        ) or None,
        "knowledge_point_name": _clean_text(
            payload.get("knowledge_point_name") or base.get("knowledge_point_name"),
            80,
        ),
        "tags": _clean_list(payload.get("tags") if "tags" in payload else base.get("tags")),
        "sm2": sm2,
        "suspended": _coerce_bool(
            payload.get("suspended") if "suspended" in payload else base.get("suspended"),
            False,
        ),
        "created_at": _clean_text(base.get("created_at") or now, 40),
        "last_reviewed_at": _clean_text(
            payload.get("last_reviewed_at")
            if "last_reviewed_at" in payload
            else base.get("last_reviewed_at"),
            40,
        ) or None,
        "updated_at": now,
    }


class StudyToolsStorage:
    def __init__(self, backend_dir: str) -> None:
        self.root = os.path.join(backend_dir, "study_tools", "users")
        self._lock = threading.RLock()

    # ───────────── 路径与 I/O ─────────────

    def _user_dir(self, user_id: str) -> str:
        uid = user_id if (user_id and _SAFE_USER_ID.fullmatch(user_id)) else "anonymous"
        path = os.path.join(self.root, uid)
        os.makedirs(path, exist_ok=True)
        return path

    def _mistakes_path(self, user_id: str) -> str:
        return os.path.join(self._user_dir(user_id), "mistakes.json")

    def _flashcards_path(self, user_id: str) -> str:
        return os.path.join(self._user_dir(user_id), "flashcards.json")

    def _collections_path(self, user_id: str) -> str:
        return os.path.join(self._user_dir(user_id), "mistake_collections.json")

    def _load(self, path: str) -> dict[str, Any]:
        if not os.path.exists(path):
            return {"version": VERSION, "items": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"version": VERSION, "items": []}
        if not isinstance(payload, dict):
            return {"version": VERSION, "items": []}
        items = payload.get("items")
        if not isinstance(items, list):
            items = []
        return {"version": VERSION, "items": [it for it in items if isinstance(it, dict)]}

    def _save(self, path: str, payload: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    # ───────────── 错题本 ─────────────

    def list_mistakes(
        self,
        user_id: str,
        course_id: str | None = None,
        knowledge_point_id: str | None = None,
        mastered: bool | None = None,
        source: str | None = None,
        collection_id: str | None = None,
        query: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._load(self._mistakes_path(user_id))
        items = data["items"]

        if course_id:
            items = [it for it in items if it.get("course_id") == course_id]
        if knowledge_point_id:
            items = [it for it in items if it.get("knowledge_point_id") == knowledge_point_id]
        if mastered is not None:
            items = [it for it in items if bool(it.get("mastered")) == mastered]
        if source:
            items = [it for it in items if it.get("source") == source]
        if collection_id:
            items = [it for it in items if collection_id in (it.get("collection_ids") or [])]
        if query:
            q = query.lower()
            items = [
                it for it in items
                if q in (it.get("stem") or "").lower()
                or q in (it.get("knowledge_point_name") or "").lower()
                or q in (it.get("course_name") or "").lower()
            ]

        items_sorted = sorted(
            items,
            key=lambda it: it.get("first_added_at") or "",
            reverse=True,
        )
        total = len(items_sorted)
        page = max(1, int(page or 1))
        page_size = max(1, min(200, int(page_size or 50)))
        start = (page - 1) * page_size
        return {
            "items": items_sorted[start:start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_mistake(self, user_id: str, mistake_id: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._load(self._mistakes_path(user_id))
        for it in data["items"]:
            if it.get("id") == mistake_id:
                return it
        return None

    def add_mistake(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = _normalize_mistake(payload)
        with self._lock:
            path = self._mistakes_path(user_id)
            data = self._load(path)
            data["items"].insert(0, item)
            self._save(path, data)
        return item

    def bulk_add_mistakes(
        self,
        user_id: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        added: list[dict[str, Any]] = []
        deduped = 0
        with self._lock:
            path = self._mistakes_path(user_id)
            data = self._load(path)
            existing_keys = {
                it.get("source_evidence_id")
                for it in data["items"]
                if it.get("source_evidence_id")
            }
            for payload in items or []:
                if not isinstance(payload, dict):
                    continue
                ev_id = (payload.get("source_evidence_id") or "").strip() or None
                if ev_id and ev_id in existing_keys:
                    deduped += 1
                    continue
                normalized = _normalize_mistake(payload)
                normalized["source"] = normalized.get("source") or "classroom"
                added.append(normalized)
                if ev_id:
                    existing_keys.add(ev_id)
            if added:
                data["items"] = added + data["items"]
                self._save(path, data)
        return {"added": added, "added_count": len(added), "deduped_count": deduped}

    def update_mistake(
        self,
        user_id: str,
        mistake_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self._lock:
            path = self._mistakes_path(user_id)
            data = self._load(path)
            for idx, it in enumerate(data["items"]):
                if it.get("id") == mistake_id:
                    merged = {**it, **(patch or {})}
                    # 标记为掌握时,记录时间
                    if patch and bool(patch.get("mastered")) and not it.get("mastered"):
                        merged["mastered_at"] = _now_iso()
                    item = _normalize_mistake(merged, it)
                    item["id"] = it["id"]
                    item["first_added_at"] = it.get("first_added_at") or item["first_added_at"]
                    data["items"][idx] = item
                    self._save(path, data)
                    return item
        return None

    def delete_mistake(self, user_id: str, mistake_id: str) -> bool:
        with self._lock:
            path = self._mistakes_path(user_id)
            data = self._load(path)
            new_items = [it for it in data["items"] if it.get("id") != mistake_id]
            if len(new_items) == len(data["items"]):
                return False
            data["items"] = new_items
            self._save(path, data)
        # 同步删除磁盘上的附件目录(不在锁内,避免锁外 os 阻塞)
        att_dir = self._attachments_dir(user_id, mistake_id)
        if os.path.isdir(att_dir):
            try:
                import shutil
                shutil.rmtree(att_dir, ignore_errors=True)
            except OSError:
                pass
        return True

    # ───────────── 错题附件 ─────────────

    def _attachments_dir(self, user_id: str, mistake_id: str) -> str:
        """附件目录绝对路径。mistake_id 必须已经在 self._load 中存在并通过 _SAFE_ID 校验。"""
        return os.path.join(
            self._user_dir(user_id),
            "attachments",
            mistake_id,
        )

    def list_attachments(self, user_id: str, mistake_id: str) -> list[dict[str, Any]]:
        with self._lock:
            data = self._load(self._mistakes_path(user_id))
        for it in data["items"]:
            if it.get("id") == mistake_id:
                return list(it.get("attachments") or [])
        return []

    def add_attachments(
        self,
        user_id: str,
        mistake_id: str,
        files: list[tuple[str, bytes, str | None]],
    ) -> list[dict[str, Any]]:
        """批量追加图片附件。

        files: [(filename, content_bytes, mime)]。每个文件经过白名单+魔数嗅探。
        返回本次新增的附件列表(已写入 JSON),失败的文件被跳过。
        """
        saved: list[dict[str, Any]] = []
        if not files:
            return saved
        with self._lock:
            path = self._mistakes_path(user_id)
            data = self._load(path)
            for idx, it in enumerate(data["items"]):
                if it.get("id") != mistake_id:
                    continue
                current = list(it.get("attachments") or [])
                if len(current) >= MAX_ATTACHMENTS_PER_MISTAKE:
                    # 已达上限,整体回滚
                    return saved
                att_dir = self._attachments_dir(user_id, mistake_id)
                os.makedirs(att_dir, exist_ok=True)
                for filename, content, mime in files:
                    if len(current) + len(saved) >= MAX_ATTACHMENTS_PER_MISTAKE:
                        break
                    if not content:
                        continue
                    ext = _guess_image_ext(filename or "", mime)
                    if ext is None:
                        continue
                    sniffed = _sniff_image_ext(content[:16])
                    if sniffed != ext:
                        # 客户端声称的扩展名与实际魔数不一致,丢弃
                        continue
                    att_id = f"att_{uuid.uuid4().hex[:12]}"
                    on_disk = f"{att_id}.{ext}"
                    full_path = os.path.join(att_dir, on_disk)
                    with open(full_path, "wb") as f:
                        f.write(content)
                    att = {
                        "id": att_id,
                        "name": filename or on_disk,
                        "url": f"/api/study-tools/mistakes/{mistake_id}/attachments/{att_id}?user_id={user_id}",
                        "mime": mime or f"image/{ext}",
                        "size": len(content),
                        "uploaded_at": _now_iso(),
                    }
                    saved.append(att)
                    current.append(att)
                data["items"][idx]["attachments"] = current
                data["items"][idx]["updated_at"] = _now_iso()
                self._save(path, data)
                break
        return saved

    def remove_attachment(
        self,
        user_id: str,
        mistake_id: str,
        att_id: str,
    ) -> bool:
        if not att_id or not _SAFE_ATT_ID.fullmatch(att_id):
            return False
        with self._lock:
            path = self._mistakes_path(user_id)
            data = self._load(path)
            for idx, it in enumerate(data["items"]):
                if it.get("id") != mistake_id:
                    continue
                current = list(it.get("attachments") or [])
                target = next((a for a in current if a.get("id") == att_id), None)
                if target is None:
                    return False
                current = [a for a in current if a.get("id") != att_id]
                data["items"][idx]["attachments"] = current
                data["items"][idx]["updated_at"] = _now_iso()
                self._save(path, data)
                # 删文件(锁外做 IO)
                ext = _guess_image_ext(target.get("name") or "", target.get("mime"))
                # 真实磁盘文件后缀未知,做一次枚举兜底
                att_dir = self._attachments_dir(user_id, mistake_id)
                for candidate in (f"{att_id}.{ext}" if ext else None,):
                    if not candidate:
                        continue
                    p = os.path.join(att_dir, candidate)
                    if os.path.isfile(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
                        break
                else:
                    # 后缀不确定,扫一遍
                    try:
                        for name in os.listdir(att_dir):
                            if name.startswith(att_id + "."):
                                try:
                                    os.remove(os.path.join(att_dir, name))
                                except OSError:
                                    pass
                    except OSError:
                        pass
                return True
        return False

    def resolve_attachment(
        self,
        user_id: str,
        mistake_id: str,
        att_id: str,
    ) -> dict[str, Any] | None:
        """校验 att_id 存在并返回其在磁盘上的路径元信息。"""
        if not att_id or not _SAFE_ATT_ID.fullmatch(att_id):
            return None
        if not mistake_id or not _SAFE_ID.fullmatch(mistake_id):
            return None
        with self._lock:
            data = self._load(self._mistakes_path(user_id))
        for it in data["items"]:
            if it.get("id") != mistake_id:
                continue
            for a in it.get("attachments") or []:
                if a.get("id") == att_id:
                    att_dir = self._attachments_dir(user_id, mistake_id)
                    # 找磁盘文件(后缀以附件记录为准,找不到再扫)
                    for ext in ("png", "jpg", "gif", "webp", "bmp"):
                        p = os.path.join(att_dir, f"{att_id}.{ext}")
                        if os.path.isfile(p):
                            return {
                                "path": p,
                                "mime": a.get("mime") or f"image/{ext}",
                                "name": a.get("name") or f"{att_id}.{ext}",
                            }
                    return None
        return None

    # ───────────── 错题集 ─────────────

    def _collection_name_exists(
        self,
        items: list[dict[str, Any]],
        name: str,
        exclude_id: str | None = None,
    ) -> bool:
        target = name.strip().lower()
        for it in items:
            if exclude_id and it.get("id") == exclude_id:
                continue
            if (it.get("name") or "").strip().lower() == target:
                return True
        return False

    def list_collections(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            collections_data = self._load(self._collections_path(user_id))
            mistakes_data = self._load(self._mistakes_path(user_id))
        items = collections_data["items"]
        # 实时统计:每个集合的错题数 + 未掌握数
        counter: dict[str, int] = {}
        unmastered_counter: dict[str, int] = {}
        for m in mistakes_data["items"]:
            for cid in (m.get("collection_ids") or []):
                if not isinstance(cid, str) or not _SAFE_ID.fullmatch(cid):
                    continue
                counter[cid] = counter.get(cid, 0) + 1
                if not m.get("mastered"):
                    unmastered_counter[cid] = unmastered_counter.get(cid, 0) + 1
        items_sorted = sorted(items, key=lambda it: it.get("created_at") or "", reverse=True)
        enriched = [
            {**it, "count": counter.get(it.get("id"), 0), "unmastered_count": unmastered_counter.get(it.get("id"), 0)}
            for it in items_sorted
        ]
        return {"items": enriched, "total": len(enriched)}

    def get_collection(self, user_id: str, collection_id: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._load(self._collections_path(user_id))
        for it in data["items"]:
            if it.get("id") == collection_id:
                return it
        return None

    def add_collection(
        self,
        user_id: str,
        payload: dict[str, Any],
        mistake_ids: list[str] | None = None,
    ) -> dict[str, Any] | None:
        item = _normalize_collection(payload)
        if not item["name"]:
            return None
        with self._lock:
            cpath = self._collections_path(user_id)
            cdata = self._load(cpath)
            if self._collection_name_exists(cdata["items"], item["name"]):
                return {"_error": "duplicate_name", "name": item["name"]}
            cdata["items"].insert(0, item)
            self._save(cpath, cdata)
            # 初始错题关联
            ids = _normalize_collection_ids(mistake_ids or [])
            if ids:
                mpath = self._mistakes_path(user_id)
                mdata = self._load(mpath)
                idset = set(ids)
                changed = False
                for m in mdata["items"]:
                    if m.get("id") in idset and item["id"] not in (m.get("collection_ids") or []):
                        m["collection_ids"] = [item["id"], *(m.get("collection_ids") or [])]
                        m["updated_at"] = _now_iso()
                        changed = True
                if changed:
                    self._save(mpath, mdata)
        return item

    def update_collection(
        self,
        user_id: str,
        collection_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self._lock:
            cpath = self._collections_path(user_id)
            cdata = self._load(cpath)
            for idx, it in enumerate(cdata["items"]):
                if it.get("id") == collection_id:
                    merged = {**it, **(patch or {})}
                    item = _normalize_collection(merged, it)
                    if not item["name"]:
                        return {"_error": "empty_name"}
                    if self._collection_name_exists(cdata["items"], item["name"], exclude_id=collection_id):
                        return {"_error": "duplicate_name", "name": item["name"]}
                    item["id"] = it["id"]
                    item["created_at"] = it.get("created_at") or item["created_at"]
                    cdata["items"][idx] = item
                    self._save(cpath, cdata)
                    return item
        return None

    def delete_collection(self, user_id: str, collection_id: str) -> bool:
        with self._lock:
            cpath = self._collections_path(user_id)
            cdata = self._load(cpath)
            new_items = [it for it in cdata["items"] if it.get("id") != collection_id]
            if len(new_items) == len(cdata["items"]):
                return False
            cdata["items"] = new_items
            self._save(cpath, cdata)
            # 同步清空错题中的反向引用(同一把锁里)
            mpath = self._mistakes_path(user_id)
            mdata = self._load(mpath)
            changed = False
            for m in mdata["items"]:
                cids = m.get("collection_ids") or []
                if collection_id in cids:
                    m["collection_ids"] = [c for c in cids if c != collection_id]
                    m["updated_at"] = _now_iso()
                    changed = True
            if changed:
                self._save(mpath, mdata)
        return True

    def assign_mistakes_to_collection(
        self,
        user_id: str,
        collection_id: str,
        mistake_ids: list[str],
    ) -> dict[str, Any]:
        ids = _normalize_collection_ids(mistake_ids)
        with self._lock:
            cpath = self._collections_path(user_id)
            cdata = self._load(cpath)
            if not any(it.get("id") == collection_id for it in cdata["items"]):
                return {"_error": "collection_not_found"}
            mpath = self._mistakes_path(user_id)
            mdata = self._load(mpath)
            idset = set(ids)
            added = 0
            not_found: list[str] = []
            for m in mdata["items"]:
                if m.get("id") not in idset:
                    continue
                cids = m.get("collection_ids") or []
                if collection_id not in cids:
                    m["collection_ids"] = [collection_id, *cids]
                    m["updated_at"] = _now_iso()
                    added += 1
            if added:
                self._save(mpath, mdata)
            for mid in ids:
                if not any(m.get("id") == mid for m in mdata["items"]):
                    not_found.append(mid)
        return {"added": added, "not_found": not_found}

    def remove_mistake_from_collection(
        self,
        user_id: str,
        collection_id: str,
        mistake_id: str,
    ) -> bool:
        with self._lock:
            mpath = self._mistakes_path(user_id)
            mdata = self._load(mpath)
            changed = False
            for m in mdata["items"]:
                if m.get("id") != mistake_id:
                    continue
                cids = m.get("collection_ids") or []
                if collection_id in cids:
                    m["collection_ids"] = [c for c in cids if c != collection_id]
                    m["updated_at"] = _now_iso()
                    changed = True
                break
            if changed:
                self._save(mpath, mdata)
        return changed

    # ───────────── 闪卡 ─────────────

    def list_flashcards(
        self,
        user_id: str,
        course_id: str | None = None,
        knowledge_point_id: str | None = None,
        source: str | None = None,
        suspended: bool | None = None,
        query: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._load(self._flashcards_path(user_id))
        items = data["items"]
        if course_id:
            items = [it for it in items if it.get("course_id") == course_id]
        if knowledge_point_id:
            items = [it for it in items if it.get("knowledge_point_id") == knowledge_point_id]
        if source:
            items = [it for it in items if it.get("source") == source]
        if suspended is not None:
            items = [it for it in items if bool(it.get("suspended")) == suspended]
        if query:
            q = query.lower()
            items = [
                it for it in items
                if q in (it.get("front") or "").lower()
                or q in (it.get("back") or "").lower()
                or q in (it.get("knowledge_point_name") or "").lower()
            ]
        items_sorted = sorted(items, key=lambda it: it.get("created_at") or "", reverse=True)
        total = len(items_sorted)
        page = max(1, int(page or 1))
        page_size = max(1, min(200, int(page_size or 50)))
        start = (page - 1) * page_size
        return {
            "items": items_sorted[start:start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_flashcard(self, user_id: str, card_id: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._load(self._flashcards_path(user_id))
        for it in data["items"]:
            if it.get("id") == card_id:
                return it
        return None

    def add_flashcard(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = _normalize_flashcard(payload)
        if not item["sm2"].get("due_date"):
            item["sm2"]["due_date"] = _today_iso()
        with self._lock:
            path = self._flashcards_path(user_id)
            data = self._load(path)
            data["items"].insert(0, item)
            self._save(path, data)
        return item

    def bulk_add_flashcards(
        self,
        user_id: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        added: list[dict[str, Any]] = []
        with self._lock:
            path = self._flashcards_path(user_id)
            data = self._load(path)
            for payload in items or []:
                if not isinstance(payload, dict):
                    continue
                normalized = _normalize_flashcard(payload)
                if not normalized["sm2"].get("due_date"):
                    normalized["sm2"]["due_date"] = _today_iso()
                added.append(normalized)
            if added:
                data["items"] = added + data["items"]
                self._save(path, data)
        return {"added": added, "added_count": len(added)}

    def update_flashcard(
        self,
        user_id: str,
        card_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any] | None:
        with self._lock:
            path = self._flashcards_path(user_id)
            data = self._load(path)
            for idx, it in enumerate(data["items"]):
                if it.get("id") == card_id:
                    merged = {**it, **(patch or {})}
                    item = _normalize_flashcard(merged, it)
                    item["id"] = it["id"]
                    item["created_at"] = it.get("created_at") or item["created_at"]
                    data["items"][idx] = item
                    self._save(path, data)
                    return item
        return None

    def delete_flashcard(self, user_id: str, card_id: str) -> bool:
        with self._lock:
            path = self._flashcards_path(user_id)
            data = self._load(path)
            new_items = [it for it in data["items"] if it.get("id") != card_id]
            if len(new_items) == len(data["items"]):
                return False
            data["items"] = new_items
            self._save(path, data)
            return True

    def review_flashcard(
        self,
        user_id: str,
        card_id: str,
        grade: int,
        today: date | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            path = self._flashcards_path(user_id)
            data = self._load(path)
            for idx, it in enumerate(data["items"]):
                if it.get("id") == card_id:
                    new_sm2 = srs.compute_next_review(it.get("sm2") or {}, grade, today)
                    updated = {**it, "sm2": new_sm2, "last_reviewed_at": _now_iso()}
                    item = _normalize_flashcard(updated, it)
                    item["id"] = it["id"]
                    item["created_at"] = it.get("created_at") or item["created_at"]
                    data["items"][idx] = item
                    self._save(path, data)
                    return item
        return None

    def list_due_flashcards(
        self,
        user_id: str,
        today: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        today_str = today or _today_iso()
        with self._lock:
            data = self._load(self._flashcards_path(user_id))
        due = [
            it for it in data["items"]
            if not it.get("suspended")
            and (it.get("sm2") or {}).get("due_date", "") <= today_str
        ]
        due.sort(key=lambda it: (it.get("sm2") or {}).get("due_date") or "")
        return due[: max(1, min(500, int(limit or 50)))]

    # ───────────── 统计 ─────────────

    def stats(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            mistakes = self._load(self._mistakes_path(user_id))["items"]
            cards = self._load(self._flashcards_path(user_id))["items"]
        today = _today_iso()
        mistakes_total = len(mistakes)
        mistakes_mastered = sum(1 for it in mistakes if it.get("mastered"))
        kp_counter: dict[str, int] = {}
        for it in mistakes:
            if it.get("mastered"):
                continue
            name = it.get("knowledge_point_name") or "未分类"
            kp_counter[name] = kp_counter.get(name, 0) + 1
        top_kp = sorted(kp_counter.items(), key=lambda kv: -kv[1])[:5]

        cards_total = len(cards)
        cards_due = sum(
            1 for it in cards
            if not it.get("suspended")
            and (it.get("sm2") or {}).get("due_date", "") <= today
        )
        cards_mastered = sum(
            1 for it in cards
            if (it.get("sm2") or {}).get("repetitions", 0) >= 3
            and (it.get("sm2") or {}).get("ease_factor", 0) >= 2.5
        )

        # 连续复习天数:统计 last_reviewed_at 中独立日期连续段
        review_dates = sorted({
            (it.get("last_reviewed_at") or "")[:10]
            for it in cards
            if it.get("last_reviewed_at")
        }, reverse=True)
        streak = 0
        if review_dates:
            cursor = date.fromisoformat(today)
            for d in review_dates:
                try:
                    dt = date.fromisoformat(d)
                except ValueError:
                    continue
                if (cursor - dt).days <= 1:
                    streak += 1
                    cursor = dt
                else:
                    break

        return {
            "mistakes": {
                "total": mistakes_total,
                "mastered": mistakes_mastered,
                "unmastered": mistakes_total - mistakes_mastered,
                "top_knowledge_points": [{"name": n, "count": c} for n, c in top_kp],
            },
            "flashcards": {
                "total": cards_total,
                "due_today": cards_due,
                "mastered": cards_mastered,
                "streak_days": streak,
            },
        }
