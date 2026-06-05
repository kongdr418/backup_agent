from __future__ import annotations

import os
import sys
import tempfile
import unittest


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import app as backend_app
from interactive_classroom.storage import ClassroomStorage


def _quiz_classroom() -> dict:
    return {
        "id": "classroom_answer_001",
        "user_id": "user_1",
        "title": "测试课堂",
        "topic": "测试主题",
        "course": "测试课程",
        "status": "ready",
        "created_at": "2026-06-05T10:00:00",
        "updated_at": "2026-06-05T10:00:00",
        "tts": {},
        "student_profile": {},
        "source": {},
        "agents": [],
        "knowledge_points": ["测试知识点"],
        "scenes": [
            {
                "id": "scene_quiz_001",
                "type": "quiz",
                "title": "随堂测验",
                "order": 1,
                "knowledge_points": ["测试知识点"],
                "content": {
                    "questions": [
                        {
                            "id": "q1",
                            "type": "single",
                            "question": "正确答案是什么？",
                            "options": [
                                {"label": "A 选项", "value": "A"},
                                {"label": "B 选项", "value": "B"},
                            ],
                            "answer": ["A"],
                            "analysis": "A 是正确答案。",
                            "points": 1,
                            "knowledge_point": "测试知识点",
                        }
                    ]
                },
                "actions": [],
            }
        ],
    }


class InteractiveClassroomAnswerPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = ClassroomStorage(self.tempdir.name)
        self.original_storage = backend_app.CLASSROOM_STORAGE
        backend_app.CLASSROOM_STORAGE = self.storage
        self.storage.save_classroom("user_1", "classroom_answer_001", _quiz_classroom())
        self.client = backend_app.app.test_client()

    def tearDown(self) -> None:
        backend_app.CLASSROOM_STORAGE = self.original_storage
        self.tempdir.cleanup()

    def test_get_classroom_includes_saved_answers_record(self) -> None:
        self.storage.save_answers(
            "user_1",
            "classroom_answer_001",
            "scene_quiz_001",
            {
                "answers": {"q1": ["A"]},
                "evaluation": {
                    "score": 100,
                    "correct": 1,
                    "total": 1,
                    "earned_points": 1,
                    "total_points": 1,
                    "results": [
                        {
                            "question_id": "q1",
                            "correct": True,
                            "your_answer": ["A"],
                            "correct_answer": ["A"],
                            "analysis": "A 是正确答案。",
                        }
                    ],
                },
            },
        )

        resp = self.client.get("/api/interactive-classroom/classroom_answer_001", query_string={"user_id": "user_1"})

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["success"])
        self.assertIn("answers_record", payload["classroom"])
        self.assertEqual(
            ["A"],
            payload["classroom"]["answers_record"]["scenes"]["scene_quiz_001"]["answers"]["q1"],
        )


if __name__ == "__main__":
    unittest.main()
