from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from interactive_classroom.storage import ClassroomStorage
from interactive_classroom.event_service import create_scene_reviewed_event, record_event


class ClassroomStorageActionsTest(unittest.TestCase):
    def test_rename_updates_title_and_delete_removes_classroom(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ClassroomStorage(tmpdir)
            payload = {
                "id": "cls_test",
                "title": "旧标题",
                "topic": "Spring Boot",
                "course": "Java",
                "status": "ready",
                "created_at": "2026-06-03T00:00:00",
                "updated_at": "2026-06-03T00:00:00",
                "tts": {},
                "source": {},
                "scenes": [],
            }
            storage.save_classroom("user_1", "cls_test", payload)

            renamed = storage.rename_classroom("user_1", "cls_test", "新标题")
            loaded = storage.load_classroom("user_1", "cls_test")

            self.assertTrue(renamed)
            self.assertEqual("新标题", loaded["title"])
            self.assertTrue(storage.delete_classroom("user_1", "cls_test"))
            self.assertIsNone(storage.load_classroom("user_1", "cls_test"))

    def test_concurrent_learning_events_are_deduped_and_keep_json_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ClassroomStorage(tmpdir)
            payload = {
                "id": "cls_test",
                "title": "课堂",
                "topic": "Spring Boot",
                "course": "Java",
                "status": "ready",
                "created_at": "2026-06-03T00:00:00",
                "updated_at": "2026-06-03T00:00:00",
                "tts": {},
                "source": {},
                "scenes": [],
            }
            storage.save_classroom("user_1", "cls_test", payload)
            barrier = threading.Barrier(2)
            errors: list[Exception] = []

            def worker() -> None:
                try:
                    event = create_scene_reviewed_event(
                        user_id="user_1",
                        classroom_id="cls_test",
                        scene_id="scene_slide_001",
                        course_id="Java",
                        knowledge_points=["自动配置"],
                    )
                    barrier.wait(timeout=2)
                    record_event(storage, event)
                except Exception as exc:  # pragma: no cover - surfaced by assertion
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual([], errors)
            events = storage.load_events("user_1", "cls_test")
            self.assertEqual(1, len(events))
            self.assertEqual("scene_reviewed", events[0]["type"])


if __name__ == "__main__":
    unittest.main()
