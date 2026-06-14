from __future__ import annotations

import os
import sys
import tempfile
import unittest


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import app as backend_app
from course_knowledge import CourseKnowledgeRetriever, CourseKnowledgeStorage
from learner_profile.schemas import PROFILE_VERSION
from learner_profile.storage import PPT_LEARNING_STRATEGY_TITLE
from learner_profile.storage import LearnerProfileStorage


class LearnerProfileApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = LearnerProfileStorage(
            self.tempdir.name,
            now_provider=lambda: "2026-06-08T11:00:00",
        )
        self.original_storage = backend_app.LEARNER_PROFILE_STORAGE
        self.original_course_knowledge_retriever = backend_app.COURSE_KNOWLEDGE_RETRIEVER
        backend_app.LEARNER_PROFILE_STORAGE = self.storage
        self.course_knowledge_storage = CourseKnowledgeStorage(
            self.tempdir.name,
            now_provider=lambda: "2026-06-08T11:00:00",
        )
        backend_app.COURSE_KNOWLEDGE_RETRIEVER = CourseKnowledgeRetriever(
            self.tempdir.name,
            storage=self.course_knowledge_storage,
        )
        self.client = backend_app.app.test_client()

    def tearDown(self) -> None:
        backend_app.LEARNER_PROFILE_STORAGE = self.original_storage
        backend_app.COURSE_KNOWLEDGE_RETRIEVER = self.original_course_knowledge_retriever
        self.tempdir.cleanup()

    def test_get_returns_default_profile_for_current_user(self) -> None:
        response = self.client.get(
            "/api/learner-profile",
            query_string={"user_id": "user_1"},
        )

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual("user_1", payload["profile"]["user_id"])
        self.assertEqual(PROFILE_VERSION, payload["profile"]["profile_version"])

    def test_put_persists_normalized_profile(self) -> None:
        response = self.client.put(
            "/api/learner-profile",
            json={
                "user_id": "user_1",
                "profile": {
                    "basic": {
                        "display_name": " 小明 ",
                        "learning_basis": "有基础",
                    },
                    "preferences": {
                        "goal": "项目实战",
                        "content_style": ["案例", "图解"],
                        "preferred_difficulty": "中等",
                        "tutoring_style": "引导式",
                    },
                },
            },
        )

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("小明", payload["profile"]["basic"]["display_name"])
        loaded = self.storage.load_profile("user_1")
        self.assertEqual("项目实战", loaded["preferences"]["goal"])

    def test_put_accepts_legacy_four_field_profile(self) -> None:
        response = self.client.put(
            "/api/learner-profile",
            json={
                "user_id": "user_1",
                "profile": {
                    "basis": "零基础",
                    "goal": "考试通过",
                    "style": "图解+案例",
                    "difficulty": "基础",
                },
            },
        )

        self.assertEqual(200, response.status_code)
        profile = response.get_json()["profile"]
        self.assertEqual("零基础", profile["basic"]["learning_basis"])
        self.assertEqual(["图解", "案例"], profile["preferences"]["content_style"])

    def test_put_rejects_non_object_profile(self) -> None:
        response = self.client.put(
            "/api/learner-profile",
            json={"user_id": "user_1", "profile": []},
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual("profile must be an object", response.get_json()["error"])

    def test_ppt_generation_notes_include_learning_strategy_by_default(self) -> None:
        self.storage.save_profile(
            "user_1",
            {
                "basic": {"learning_stage": "大二", "learning_basis": "有基础"},
                "preferences": {
                    "goal": "项目实战",
                    "content_style": ["案例"],
                    "preferred_difficulty": "中等",
                    "tutoring_style": "引导式",
                },
            },
        )

        notes = backend_app._resolve_ppt_generation_notes(
            {"notes": "请强调实验"},
            "user_1",
        )

        self.assertIn("请强调实验", notes)
        self.assertIn(PPT_LEARNING_STRATEGY_TITLE, notes)
        self.assertIn("学习目标：项目实战", notes)

    def test_ppt_generation_notes_do_not_duplicate_learning_strategy(self) -> None:
        notes = backend_app._resolve_ppt_generation_notes(
            {"notes": f"已有说明\n{PPT_LEARNING_STRATEGY_TITLE}\n学习目标：项目实战"},
            "user_1",
        )

        self.assertEqual(1, notes.count(PPT_LEARNING_STRATEGY_TITLE))

    def test_ppt_generation_notes_match_course_from_topic_when_course_missing(self) -> None:
        course_id = "course_cloud"
        self.course_knowledge_storage.save_course_map(
            "user_1",
            {
                "courses": [
                    {
                        "course_id": course_id,
                        "course_name": "云计算与大数据技术",
                        "summary": "课程要求学生掌握云计算和大数据分析的基础能力。",
                        "lessons": [
                            {"lesson_id": "lesson_hadoop", "title": "Hadoop 安装与配置"},
                        ],
                        "knowledge_points": [
                            {"knowledge_point_id": "kp_cloud", "label": "云计算"},
                            {"knowledge_point_id": "kp_hadoop", "label": "Hadoop"},
                        ],
                    }
                ]
            },
        )
        self.course_knowledge_storage.save_course_catalog(
            "user_1",
            course_id,
            {
                "course_id": course_id,
                "course_name": "云计算与大数据技术",
            },
        )
        self.course_knowledge_storage.save_chunk_index(
            "user_1",
            course_id,
            [
                {
                    "chunk_id": "chunk_cloud",
                    "chunk_type": "lesson",
                    "section": "云计算与大数据技术",
                    "text": "云计算与大数据技术包括云计算、Hadoop 和大数据分析。",
                    "keywords": ["云计算", "Hadoop"],
                    "knowledge_point_ids": ["kp_cloud", "kp_hadoop"],
                    "evidence_label": "云计算与大数据技术",
                }
            ],
        )

        notes = backend_app._resolve_ppt_generation_notes(
            {"topic": "云计算与大数据技术"},
            "user_1",
        )

        self.assertIn("## 课程知识库参考", notes)
        self.assertIn("课程名称：云计算与大数据技术", notes)
        self.assertIn("云计算", notes)
        self.assertIn("Hadoop", notes)

    def test_ppt_generation_notes_ignore_unrelated_vector_only_course_match(self) -> None:
        class OvereagerVectorIndex:
            def query_scores(self, user_id, course_id, chunks, topic):  # noqa: ANN001
                return {chunk["chunk_id"]: 0.99 for chunk in chunks}

        course_id = "course_cloud"
        self.course_knowledge_storage.save_course_map(
            "user_1",
            {
                "courses": [
                    {
                        "course_id": course_id,
                        "course_name": "云计算与大数据技术",
                        "summary": "课程要求学生掌握云计算和大数据分析。",
                        "lessons": [
                            {"lesson_id": "lesson_cloud", "title": "云计算概述"},
                            {"lesson_id": "lesson_vm", "title": "虚拟化技术"},
                        ],
                        "knowledge_points": [
                            {"knowledge_point_id": "kp_cloud", "label": "云计算"},
                            {"knowledge_point_id": "kp_hadoop", "label": "Hadoop"},
                        ],
                    }
                ]
            },
        )
        self.course_knowledge_storage.save_chunk_index(
            "user_1",
            course_id,
            [
                {
                    "chunk_id": "chunk_cloud",
                    "chunk_type": "lesson",
                    "section": "云计算与大数据技术",
                    "text": "云计算平台、虚拟化、Hadoop 和大数据处理。",
                    "keywords": ["云计算", "虚拟化", "Hadoop"],
                    "knowledge_point_ids": ["kp_cloud", "kp_hadoop"],
                    "evidence_label": "云计算与大数据技术",
                }
            ],
        )
        backend_app.COURSE_KNOWLEDGE_RETRIEVER = CourseKnowledgeRetriever(
            self.tempdir.name,
            storage=self.course_knowledge_storage,
            vector_index=OvereagerVectorIndex(),
        )

        notes = backend_app._resolve_ppt_generation_notes(
            {"topic": "神经网络"},
            "user_1",
        )

        self.assertNotIn("## 课程知识库参考", notes)
        self.assertNotIn("云计算", notes)
        self.assertNotIn("虚拟化技术", notes)


if __name__ == "__main__":
    unittest.main()
