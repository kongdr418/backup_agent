from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone


COOKIE_NAME = "ai_creator_device_session"
_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


class DeviceSessionStore:
    def __init__(self, backend_dir: str) -> None:
        self.path = os.path.join(backend_dir, "memory", "device_sessions.json")
        self._lock = threading.RLock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {"sessions": {}}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {"sessions": {}}
        except (OSError, ValueError):
            return {"sessions": {}}

    def _save(self, payload: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        temp = f"{self.path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp, self.path)

    def resolve(self, token: str) -> str | None:
        if not token:
            return None
        with self._lock:
            record = self._load().get("sessions", {}).get(self._digest(token))
            user_id = record.get("user_id") if isinstance(record, dict) else None
            return user_id if isinstance(user_id, str) and _SAFE_ID.fullmatch(user_id) else None

    def create(self, legacy_user_id: str = "") -> tuple[str, str]:
        user_id = legacy_user_id if _SAFE_ID.fullmatch(legacy_user_id or "") else f"device_{secrets.token_hex(16)}"
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            payload = self._load()
            payload.setdefault("sessions", {})[self._digest(token)] = {
                "user_id": user_id, "created_at": now, "last_seen_at": now,
            }
            self._save(payload)
        return token, user_id

    def remove(self, token: str) -> None:
        if not token:
            return
        with self._lock:
            payload = self._load()
            payload.setdefault("sessions", {}).pop(self._digest(token), None)
            self._save(payload)
