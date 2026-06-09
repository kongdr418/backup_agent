from __future__ import annotations

import os
import sys
import tempfile
import unittest


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import app as backend_app
from interactive_classroom.generator import InteractiveClassroomGenerator
from interactive_classroom.storage import ClassroomStorage
from learner_profile.storage import LearnerProfileStorage


class InteractiveClassroomNextLessonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = ClassroomStorage(self.tempdir.name)
        self.profile_storage = LearnerProfileStorage(
            self.tempdir.name,
            now_provider=lambda: "2026-06-09T10:00:00",
        )
        self.original_classroom_storage = backend_app.CLASSROOM_STORAGE
        self.original_profile_storage = backend_app.LEARNER_PROFILE_STORAGE
        backend_app.CLASSROOM_STORAGE = self.storage
        backend_app.LEARNER_PROFILE_STORAGE = self.profile_storage
        self.client = backend_app.app.test_client()

    def tearDown(self) -> None:
        backend_app.CLASSROOM_STORAGE = self.original_classroom_storage
        backend_app.LEARNER_PROFILE_STORAGE = self.original_profile_storage
        self.tempdir.cleanup()

    def test_next_lesson_plan_uses_report_and_allows_user_overrides(self) -> None:
        self.storage.save_classroom(
            "user_1",
            "cls_source",
            {
                "id": "cls_source",
                "title": "Python 循环交互式课堂",
                "topic": "Python 循环",
                "course": "Python 程序设计",
                "status": "ready",
                "created_at": "2026-06-09T09:00:00",
                "updated_at": "2026-06-09T09:00:00",
                "tts": {},
                "source": {"type": "ppt_svg_job", "job_id": "ppt_job_1"},
                "scenes": [],
            },
        )
        self.storage.save_report(
            "user_1",
            "cls_source",
            {
                "classroom_id": "cls_source",
                "topic": "Python 循环",
                "score": 66,
                "weak_points": ["for 循环边界", "range 参数"],
                "strong_points": ["循环概念"],
                "next_recommendation": "建议补足循环边界，再进入嵌套循环应用。",
                "knowledge_summary": {},
                "recommended_tasks": [],
            },
        )

        response = self.client.post(
            "/api/interactive-classroom/cls_source/next-lesson-plan",
            query_string={"user_id": "user_1"},
            json={
                "topic": "嵌套循环与图形打印",
                "learning_goal": "能用嵌套循环打印简单图形",
            },
        )

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        plan = payload["plan"]
        self.assertEqual("嵌套循环与图形打印", plan["topic"])
        self.assertEqual("Python 程序设计", plan["course"])
        self.assertEqual("能用嵌套循环打印简单图形", plan["learning_goal"])
        self.assertIn("Python 循环", plan["review_points"][0])
        self.assertIn("for 循环边界", plan["focus_points"])
        self.assertIn("range 参数", plan["focus_points"])
        self.assertIn("上一课回顾", plan["ppt_notes"])
        self.assertIn("本课目标", plan["ppt_notes"])
        self.assertEqual("cls_source", plan["course_root_id"])
        self.assertEqual("cls_source", plan["parent_classroom_id"])
        self.assertEqual(1, plan["lesson_depth"])
        self.assertEqual(2, plan["lesson_index"])
        self.assertEqual("next_lesson", plan["lesson_kind"])

    def test_next_lesson_plan_returns_404_for_missing_classroom(self) -> None:
        response = self.client.post(
            "/api/interactive-classroom/missing/next-lesson-plan",
            query_string={"user_id": "user_1"},
            json={},
        )

        self.assertEqual(404, response.status_code)

    def test_generator_accepts_next_lesson_lineage(self) -> None:
        generator = InteractiveClassroomGenerator(
            backend_dir=self.tempdir.name,
            storage=self.storage,
            llm_quiz_enabled=False,
        )

        classroom = generator.generate(
            user_id="user_1",
            topic="K 近邻",
            course="机器学习",
            tts_config={},
            lineage={
                "course_root_id": "cls_root",
                "parent_classroom_id": "cls_parent",
                "lesson_depth": 1,
                "lesson_index": 2,
                "lesson_kind": "next_lesson",
            },
        )

        self.assertEqual("cls_root", classroom["course_root_id"])
        self.assertEqual("cls_parent", classroom["parent_classroom_id"])
        self.assertEqual(1, classroom["lesson_depth"])
        self.assertEqual(2, classroom["lesson_index"])
        self.assertEqual("next_lesson", classroom["lesson_kind"])

    def test_generate_endpoint_inherits_lineage_from_parent_classroom(self) -> None:
        self.storage.save_classroom(
            "user_1",
            "cls_root",
            {
                "id": "cls_root",
                "title": "深度学习基础交互式课堂",
                "topic": "深度学习基础",
                "course": "深度学习",
                "status": "ready",
                "created_at": "2026-06-09T09:00:00",
                "updated_at": "2026-06-09T09:00:00",
                "tts": {},
                "course_root_id": "cls_root",
                "parent_classroom_id": "",
                "lesson_depth": 0,
                "lesson_index": 1,
                "lesson_kind": "root",
                "source": {},
                "scenes": [],
            },
        )

        response = self.client.post(
            "/api/interactive-classroom/generate",
            query_string={"user_id": "user_1"},
            json={
                "topic": "神经网络",
                "course": "通用课程",
                "parent_classroom_id": "cls_root",
                "lesson_kind": "next_lesson",
            },
        )

        self.assertEqual(200, response.status_code)
        classroom = response.get_json()["classroom"]
        self.assertEqual("cls_root", classroom["course_root_id"])
        self.assertEqual("cls_root", classroom["parent_classroom_id"])
        self.assertEqual("深度学习", classroom["course"])
        self.assertEqual(1, classroom["lesson_depth"])
        self.assertEqual(2, classroom["lesson_index"])


if __name__ == "__main__":
    unittest.main()
