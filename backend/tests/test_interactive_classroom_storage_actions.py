from __future__ import annotations

import os
import sys
import tempfile
import unittest


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from interactive_classroom.storage import ClassroomStorage


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


if __name__ == "__main__":
    unittest.main()
