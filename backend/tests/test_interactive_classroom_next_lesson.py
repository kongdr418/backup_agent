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
from interactive_classroom.next_lesson_service import build_next_lesson_plan
from interactive_classroom.schema import ClassroomAction, ClassroomScene
from interactive_classroom.practice_service import ClassroomPracticeService
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
        self.original_practice_service = backend_app.CLASSROOM_PRACTICE_SERVICE
        backend_app.CLASSROOM_STORAGE = self.storage
        backend_app.LEARNER_PROFILE_STORAGE = self.profile_storage
        practice_generator = InteractiveClassroomGenerator(
            backend_dir=self.tempdir.name,
            storage=self.storage,
            llm_quiz_enabled=False,
        )
        backend_app.CLASSROOM_PRACTICE_SERVICE = ClassroomPracticeService(
            self.storage,
            practice_generator,
        )
        self.client = backend_app.app.test_client()

    def tearDown(self) -> None:
        backend_app.CLASSROOM_STORAGE = self.original_classroom_storage
        backend_app.LEARNER_PROFILE_STORAGE = self.original_profile_storage
        backend_app.CLASSROOM_PRACTICE_SERVICE = self.original_practice_service
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

    def test_next_lesson_ignores_unrelated_course_knowledge_context(self) -> None:
        classroom = {
            "id": "cls_nn",
            "topic": "神经网络",
            "course": "神经网络",
            "lesson_index": 1,
            "lesson_depth": 0,
        }
        report = {
            "score": 90,
            "weak_points": [],
            "strong_points": ["前向传播"],
            "learned_points": ["神经元", "激活函数"],
        }
        cloud_context = {
            "course_name": "云计算与大数据技术",
            "summary": "介绍云计算平台与大数据处理。",
            "lessons": [
                {"lesson_id": "l1", "title": "云计算概述"},
                {"lesson_id": "l2", "title": "虚拟化技术"},
            ],
            "knowledge_points": [
                {"knowledge_point_id": "kp_cloud", "label": "云计算"},
                {"knowledge_point_id": "kp_vm", "label": "虚拟化"},
            ],
        }

        plan = build_next_lesson_plan(classroom, report, {}, cloud_context, {})

        self.assertEqual("神经网络进阶应用", plan["topic"])
        self.assertEqual([], plan["course_knowledge_points"])
        self.assertNotIn("云计算概述", plan["ppt_notes"])
        self.assertNotIn("虚拟化技术", plan["ppt_notes"])
        self.assertNotIn("课程简介：介绍云计算平台与大数据处理。", plan["ppt_notes"])

    def test_next_lesson_uses_matching_course_outline(self) -> None:
        classroom = {
            "id": "cls_cloud",
            "topic": "云计算概述",
            "course": "云计算与大数据技术",
            "lesson_index": 1,
            "lesson_depth": 0,
        }
        report = {
            "score": 88,
            "weak_points": [],
            "strong_points": ["云服务模型"],
            "learned_points": ["IaaS", "PaaS"],
        }
        cloud_context = {
            "course_name": "云计算与大数据技术",
            "summary": "介绍云计算平台与大数据处理。",
            "lessons": [
                {"lesson_id": "l1", "title": "云计算概述"},
                {"lesson_id": "l2", "title": "虚拟化技术"},
            ],
            "knowledge_points": [
                {"knowledge_point_id": "kp_cloud", "label": "云计算"},
                {"knowledge_point_id": "kp_vm", "label": "虚拟化"},
            ],
        }

        plan = build_next_lesson_plan(classroom, report, {}, cloud_context, {})

        self.assertEqual("虚拟化技术", plan["topic"])
        self.assertEqual("虚拟化技术", plan["course_lesson_title"])
        self.assertIn("课程大纲相关课次：云计算概述、虚拟化技术", plan["ppt_notes"])

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

    def test_quiz_fallback_asks_understanding_questions_not_scene_index(self) -> None:
        generator = InteractiveClassroomGenerator(
            backend_dir=self.tempdir.name,
            storage=self.storage,
            llm_quiz_enabled=False,
        )
        scenes = [
            ClassroomScene(
                id="scene_slide_001",
                type="slide",
                title="场景干扰",
                order=1,
                knowledge_points=["光照变化", "遮挡", "背景噪声"],
                content={
                    "extracted_text": [
                        "场景干扰会导致模型误检或漏检，需要通过数据增强和鲁棒特征降低影响。",
                    ]
                },
                actions=[
                    ClassroomAction(
                        id="act_001",
                        type="speech",
                        text="识别干扰来源后，应选择更稳健的数据和模型策略。",
                    )
                ],
            ),
            ClassroomScene(
                id="scene_slide_002",
                type="slide",
                title="计算机视觉挑战",
                order=2,
                knowledge_points=["尺度变化", "类间相似", "实时性"],
                content={
                    "extracted_text": [
                        "计算机视觉挑战包括尺度变化、类间相似和实时性约束。",
                    ]
                },
            ),
        ]

        questions = generator._build_quiz_questions(
            "计算机视觉",
            scenes,
            max_questions=4,
            qid_prefix="q",
        )

        self.assertTrue(questions)
        question_text = "\n".join(q["question"] for q in questions)
        self.assertNotIn("第 1 个讲解场景主要围绕", question_text)
        self.assertNotIn("第 2 个讲解场景主要围绕", question_text)
        self.assertTrue(
            any(
                token in question_text
                for token in ["最能说明", "判断依据", "应用步骤", "应该优先"]
            )
        )

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

    def test_create_practice_refreshes_parent_report_path_status(self) -> None:
        self.storage.save_classroom(
            "user_1",
            "cls_source",
            {
                "id": "cls_source",
                "title": "Java 面向对象课堂",
                "topic": "Java 面向对象",
                "course": "Java 程序设计",
                "status": "ready",
                "created_at": "2026-06-09T09:00:00",
                "updated_at": "2026-06-09T09:00:00",
                "tts": {},
                "course_root_id": "cls_source",
                "parent_classroom_id": "",
                "lesson_depth": 0,
                "lesson_index": 1,
                "lesson_kind": "root",
                "source": {},
                "knowledge_points": ["封装"],
                "scenes": [],
            },
        )
        self.storage.save_report(
            "user_1",
            "cls_source",
            {
                "classroom_id": "cls_source",
                "topic": "Java 面向对象",
                "score": 60,
                "weak_points": ["封装"],
                "strong_points": [],
                "learned_points": ["封装"],
                "next_recommendation": "建议补强封装。",
                "knowledge_summary": {"封装": {"mastery": 50}},
                "recommended_tasks": [
                    {
                        "id": "task_practice_weak_points",
                        "type": "practice_weak_points",
                        "title": "完成补强练习",
                        "description": "围绕薄弱点再做一轮同类题。",
                        "priority": "high",
                        "knowledge_points": ["封装"],
                        "target_scene_ids": [],
                        "action_label": "生成练习",
                        "reason": "本次课堂报告首次识别到这些薄弱点。",
                        "evidence_ids": [],
                    }
                ],
            },
        )

        response = self.client.post(
            "/api/interactive-classroom/cls_source/practice",
            query_string={"user_id": "user_1"},
            json={
                "task_id": "task_practice_weak_points",
                "task_type": "practice_weak_points",
            },
        )

        self.assertEqual(201, response.status_code)
        practice_id = response.get_json()["classroom_id"]
        events = self.storage.load_events("user_1", "cls_source")
        self.assertTrue(
            any(
                event.get("type") == "recommended_task_completed"
                and event.get("payload", {}).get("task_id") == "task_practice_weak_points"
                and event.get("payload", {}).get("result", {}).get("status") == "practice_created"
                for event in events
            )
        )
        report = self.storage.load_report("user_1", "cls_source")
        practice_stage = next(
            stage for stage in report["learning_path"] if stage["type"] == "practice"
        )
        self.assertEqual("completed", practice_stage["status"])
        self.assertEqual("已生成", practice_stage["metric"])
        self.assertEqual(practice_id, practice_stage["generated_classroom_id"])
        self.assertEqual("查看练习", practice_stage["action_label"])
        review_stage = next(
            stage for stage in report["learning_path"] if stage["type"] == "review"
        )
        next_stage = next(
            stage for stage in report["learning_path"] if stage["type"] == "next_lesson"
        )
        diagnose_stage = next(
            stage for stage in report["learning_path"] if stage["type"] == "diagnose"
        )
        self.assertEqual("completed", diagnose_stage["status"])
        self.assertEqual("completed", review_stage["status"])
        self.assertEqual("active", next_stage["status"])

    def test_practice_fallback_uses_report_points_without_scene_index_questions(self) -> None:
        self.storage.save_classroom(
            "user_1",
            "cls_source",
            {
                "id": "cls_source",
                "title": "计算机视觉课堂",
                "topic": "计算机视觉",
                "course": "人工智能导论",
                "status": "ready",
                "created_at": "2026-06-09T09:00:00",
                "updated_at": "2026-06-09T09:00:00",
                "tts": {},
                "course_root_id": "cls_source",
                "parent_classroom_id": "",
                "lesson_depth": 0,
                "lesson_index": 1,
                "lesson_kind": "root",
                "source": {},
                "knowledge_points": ["场景干扰"],
                "scenes": [],
            },
        )
        self.storage.save_report(
            "user_1",
            "cls_source",
            {
                "classroom_id": "cls_source",
                "topic": "计算机视觉",
                "score": 50,
                "weak_points": ["场景干扰", "计算机视觉挑战"],
                "strong_points": [],
                "learned_points": ["计算机视觉核心任务"],
                "next_recommendation": "建议补强干扰场景和挑战识别。",
                "knowledge_summary": {"场景干扰": {"mastery": 40}},
                "recommended_tasks": [
                    {
                        "id": "task_practice_weak_points",
                        "type": "practice_weak_points",
                        "title": "完成补强练习",
                        "description": "围绕薄弱点再做一轮同类题。",
                        "priority": "high",
                        "knowledge_points": ["场景干扰", "计算机视觉挑战"],
                        "target_scene_ids": [],
                        "action_label": "生成练习",
                        "reason": "本次课堂报告识别到这些薄弱点。",
                        "evidence_ids": [],
                    }
                ],
            },
        )

        response = self.client.post(
            "/api/interactive-classroom/cls_source/practice",
            query_string={"user_id": "user_1"},
            json={
                "task_id": "task_practice_weak_points",
                "task_type": "practice_weak_points",
            },
        )

        self.assertEqual(201, response.status_code)
        practice = response.get_json()["classroom"]
        questions = practice["scenes"][0]["content"]["questions"]
        self.assertTrue(questions)
        question_text = "\n".join(q["question"] for q in questions)
        self.assertNotIn("第 1 个讲解场景主要围绕", question_text)
        self.assertIn("场景干扰", "\n".join(q.get("knowledge_point", "") for q in questions))

    def test_report_backfills_existing_practice_child_as_generated(self) -> None:
        self.storage.save_classroom(
            "user_1",
            "cls_source",
            {
                "id": "cls_source",
                "title": "Java 面向对象课堂",
                "topic": "Java 面向对象",
                "course": "Java 程序设计",
                "status": "ready",
                "created_at": "2026-06-09T09:00:00",
                "updated_at": "2026-06-09T09:00:00",
                "tts": {},
                "course_root_id": "cls_source",
                "parent_classroom_id": "",
                "lesson_depth": 0,
                "lesson_index": 1,
                "lesson_kind": "root",
                "source": {},
                "knowledge_points": ["封装"],
                "scenes": [],
            },
        )
        self.storage.save_classroom(
            "user_1",
            "cls_practice",
            {
                "id": "cls_practice",
                "title": "Java 面向对象补强练习",
                "topic": "Java 面向对象",
                "course": "Java 程序设计",
                "status": "ready",
                "created_at": "2026-06-09T10:00:00",
                "updated_at": "2026-06-09T10:00:00",
                "tts": {},
                "course_root_id": "cls_source",
                "parent_classroom_id": "cls_source",
                "lesson_depth": 1,
                "lesson_index": 2,
                "lesson_kind": "practice",
                "source": {
                    "type": "recommended_practice",
                    "parent_classroom_id": "cls_source",
                    "recommendation_task_id": "task_practice_weak_points",
                    "recommendation_task_type": "practice_weak_points",
                },
                "knowledge_points": ["封装"],
                "scenes": [],
            },
        )
        self.storage.save_report(
            "user_1",
            "cls_source",
            {
                "classroom_id": "cls_source",
                "status": "needs_review",
                "topic": "Java 面向对象",
                "score": 60,
                "weak_points": ["封装"],
                "strong_points": [],
                "learned_points": ["封装"],
                "next_recommendation": "建议补强封装。",
                "knowledge_summary": {"封装": {"mastery": 50}},
                "recommended_tasks": [
                    {
                        "id": "task_practice_weak_points",
                        "type": "practice_weak_points",
                        "title": "完成补强练习",
                        "description": "围绕薄弱点再做一轮同类题。",
                        "priority": "high",
                        "knowledge_points": ["封装"],
                        "target_scene_ids": [],
                        "action_label": "生成练习",
                        "reason": "本次课堂报告首次识别到这些薄弱点。",
                        "evidence_ids": [],
                    }
                ],
            },
        )

        response = self.client.get(
            "/api/interactive-classroom/cls_source/report",
            query_string={"user_id": "user_1"},
        )

        self.assertEqual(200, response.status_code)
        report = response.get_json()["report"]
        practice_stage = next(
            stage for stage in report["learning_path"] if stage["type"] == "practice"
        )
        self.assertEqual("completed", practice_stage["status"])
        self.assertEqual("已生成", practice_stage["metric"])
        self.assertEqual("cls_practice", practice_stage["generated_classroom_id"])
        self.assertEqual("查看练习", practice_stage["action_label"])
        review_stage = next(
            stage for stage in report["learning_path"] if stage["type"] == "review"
        )
        next_stage = next(
            stage for stage in report["learning_path"] if stage["type"] == "next_lesson"
        )
        diagnose_stage = next(
            stage for stage in report["learning_path"] if stage["type"] == "diagnose"
        )
        self.assertEqual("completed", diagnose_stage["status"])
        self.assertEqual("completed", review_stage["status"])
        self.assertEqual("active", next_stage["status"])


if __name__ == "__main__":
    unittest.main()
