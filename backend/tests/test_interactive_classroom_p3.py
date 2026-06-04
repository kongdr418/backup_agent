from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import asdict


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from interactive_classroom.generator import ClassroomGenerationCancelled, InteractiveClassroomGenerator
from interactive_classroom.generator import _derive_slide_title
from interactive_classroom.quiz_service import evaluate_quiz_scene
from interactive_classroom.report_service import build_classroom_report
from interactive_classroom.schema import ClassroomScene
from interactive_classroom.storage import ClassroomStorage


def _slide(index: int, title: str, points: list[str]) -> ClassroomScene:
    return ClassroomScene(
        id=f"scene_slide_{index:03d}",
        type="slide",
        title=title,
        order=index,
        knowledge_points=points,
        content={"extracted_text": [title, *points]},
        actions=[],
    )


class InteractiveClassroomP3Test(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = InteractiveClassroomGenerator(
            backend_dir=BACKEND_DIR,
            storage=None,  # type: ignore[arg-type]
            llm_quiz_enabled=False,
        )

    def test_inserts_multiple_quizzes_with_covered_slide_ids(self) -> None:
        scenes = [
            _slide(1, "导入", ["学习目标"]),
            _slide(2, "概念 A", ["要点 A1"]),
            _slide(3, "概念 B", ["要点 B1"]),
            _slide(4, "案例分析", ["案例步骤"]),
            _slide(5, "综合应用", ["迁移练习"]),
        ]

        result = self.generator._insert_quiz_scenes("测试主题", scenes)  # noqa: SLF001

        quiz_scenes = [scene for scene in result if scene.type == "quiz"]
        self.assertEqual(["scene_quiz_001", "scene_quiz_002", "scene_quiz_003"], [scene.id for scene in quiz_scenes])
        self.assertEqual(["scene_slide_001", "scene_slide_002"], quiz_scenes[0].content["covered_scene_ids"])
        self.assertEqual(["scene_slide_003", "scene_slide_004"], quiz_scenes[1].content["covered_scene_ids"])
        self.assertEqual(["scene_slide_005"], quiz_scenes[2].content["covered_scene_ids"])
        self.assertTrue(all(scene.knowledge_points for scene in quiz_scenes))
        self.assertTrue(all(scene.content["questions"] for scene in quiz_scenes))

    def test_skips_wrap_up_and_discussion_slides_as_quiz_sources(self) -> None:
        scenes = [
            _slide(1, "Spring Boot 核心价值", ["自动配置", "起步依赖"]),
            _slide(2, "Spring Boot 核心特性", ["嵌入式服务器", "生产监控"]),
            _slide(3, "创建第一个 Spring Boot 应用", ["项目结构", "启动类"]),
            _slide(4, "课程总结", ["复盘清单", "后续学习建议"]),
            _slide(5, "提问与讨论", ["鼓励学生提问", "课堂互动"]),
        ]

        result = self.generator._insert_quiz_scenes("Spring Boot入门课程", scenes)  # noqa: SLF001

        slide_ids = [scene.id for scene in result if scene.type == "slide"]
        quiz_scenes = [scene for scene in result if scene.type == "quiz"]
        covered_ids = [
            scene_id
            for quiz in quiz_scenes
            for scene_id in quiz.content["covered_scene_ids"]
        ]

        self.assertEqual([scene.id for scene in scenes], slide_ids)
        self.assertEqual(["scene_slide_001", "scene_slide_002", "scene_slide_003"], covered_ids)
        self.assertNotIn("scene_slide_004", covered_ids)
        self.assertNotIn("scene_slide_005", covered_ids)

    def test_derives_stable_slide_title_from_svg_filename_before_svg_text(self) -> None:
        title = _derive_slide_title(
            idx=8,
            filename="08_课程总结.svg",
            svg_texts=["Springboot入门课程", "提问与讨论", "课程总结"],
        )

        self.assertEqual("课程总结", title)

    def test_student_profile_guides_quiz_prompt_without_leaking_to_speech(self) -> None:
        profile = {
            "basis": "零基础",
            "goal": "考试通过",
            "style": "图解+案例",
            "difficulty": "基础",
        }
        speech = self.generator._build_speech_text(  # noqa: SLF001
            idx=1,
            title="核心概念",
            svg_texts=["核心概念", "自动配置", "起步依赖"],
            student_profile=profile,
        )
        prompt = self.generator._build_context_quiz_prompt(  # noqa: SLF001
            topic="Spring Boot",
            slide_summaries=[
                {
                    "scene_id": "scene_slide_001",
                    "title": "核心概念",
                    "knowledge_points": ["自动配置"],
                    "extracted_text": ["自动配置", "起步依赖"],
                }
            ],
            question_count=2,
            student_profile=profile,
        )

        self.assertNotIn("零基础", speech)
        self.assertNotIn("图解+案例", speech)
        self.assertNotIn("学生画像", speech)
        self.assertNotIn("请按", speech)
        self.assertIn("零基础", prompt)
        self.assertIn("考试通过", prompt)
        self.assertIn("基础", prompt)

    def test_uses_llm_quiz_json_when_it_validates(self) -> None:
        class StubQuizGenerator:
            def generate_context_quiz_json(self, topic, slide_summaries, question_count):  # noqa: ANN001
                self.topic = topic
                self.slide_summaries = slide_summaries
                self.question_count = question_count
                return """
                {
                  "title": "测试主题",
                  "modules": [
                    {
                      "title": "概念 A",
                      "questions": [
                        {
                          "num": "1",
                          "type": "单选题",
                          "text": "概念 A 最核心的判断是什么？",
                          "options": ["A. 要点 A1", "B. 无关选项", "C. 只看配色", "D. 跳过案例"],
                          "answer": "A",
                          "analysis": "要点 A1 来自概念 A 页面。",
                          "knowledge_point": "概念 A"
                        }
                      ]
                    }
                  ]
                }
                """

        quiz_generator = StubQuizGenerator()
        generator = InteractiveClassroomGenerator(
            backend_dir=BACKEND_DIR,
            storage=None,  # type: ignore[arg-type]
            quiz_generator=quiz_generator,
        )
        scenes = [
            _slide(1, "概念 A", ["要点 A1"]),
            _slide(2, "案例分析", ["案例步骤"]),
        ]

        quiz_scene = generator._build_quiz_scene(1, 3, "测试主题", scenes)  # noqa: SLF001

        self.assertEqual("llm_json", quiz_scene.content["quiz_source"])
        self.assertEqual(["scene_slide_001", "scene_slide_002"], quiz_scene.content["covered_scene_ids"])
        self.assertEqual(3, quiz_generator.question_count)
        self.assertEqual("概念 A 最核心的判断是什么？", quiz_scene.content["questions"][0]["question"])
        self.assertEqual([{"label": "要点 A1", "value": "A"}, {"label": "无关选项", "value": "B"}, {"label": "只看配色", "value": "C"}, {"label": "跳过案例", "value": "D"}], quiz_scene.content["questions"][0]["options"])

    def test_falls_back_to_deterministic_quiz_when_llm_json_is_invalid(self) -> None:
        class BadQuizGenerator:
            def generate_context_quiz_json(self, topic, slide_summaries, question_count):  # noqa: ANN001
                return '{"modules": [{"questions": [{"text": "缺少选项和答案"}]}]}'

        generator = InteractiveClassroomGenerator(
            backend_dir=BACKEND_DIR,
            storage=None,  # type: ignore[arg-type]
            quiz_generator=BadQuizGenerator(),
        )
        scenes = [
            _slide(1, "概念 A", ["要点 A1"]),
            _slide(2, "案例分析", ["案例步骤"]),
        ]

        quiz_scene = generator._build_quiz_scene(1, 3, "测试主题", scenes)  # noqa: SLF001

        self.assertEqual("slide_text", quiz_scene.content["quiz_source"])
        self.assertTrue(quiz_scene.content["questions"])

    def test_report_aggregates_multiple_quiz_scene_answers_independently(self) -> None:
        scenes = [
            _slide(1, "导入", ["学习目标"]),
            _slide(2, "概念 A", ["要点 A1"]),
            _slide(3, "概念 B", ["要点 B1"]),
            _slide(4, "总结", ["复盘清单"]),
        ]
        result = self.generator._insert_quiz_scenes("测试主题", scenes)  # noqa: SLF001
        quiz_scenes = [scene for scene in result if scene.type == "quiz"]

        first_quiz = quiz_scenes[0].__dict__.copy()
        first_quiz["content"] = quiz_scenes[0].content
        second_quiz = quiz_scenes[1].__dict__.copy()
        second_quiz["content"] = quiz_scenes[1].content

        first_answers = {
            question["id"]: question["answer"]
            for question in first_quiz["content"]["questions"]
        }
        second_answers = {
            question["id"]: ["Z"]
            for question in second_quiz["content"]["questions"]
        }

        first_eval = evaluate_quiz_scene(first_quiz, first_answers)
        second_eval = evaluate_quiz_scene(second_quiz, second_answers)
        self.assertEqual(first_eval["correct"], first_eval["total"])
        self.assertEqual(second_eval["correct"], 0)

        classroom = {
            "id": "cls_test",
            "title": "测试课堂",
            "topic": "测试主题",
            "knowledge_points": ["测试主题"],
            "scenes": [
                asdict(scene)
                for scene in result
            ],
        }
        answers_record = {
            "scenes": {
                quiz_scenes[0].id: {"answers": first_answers, "evaluation": first_eval},
                quiz_scenes[1].id: {"answers": second_answers, "evaluation": second_eval},
            }
        }

        report = build_classroom_report(classroom, answers_record)

        self.assertEqual(report["quiz_scene_count"], 2)
        self.assertEqual(report["answered_quiz_count"], 2)
        self.assertGreater(report["total"], 0)
        self.assertLess(report["score"], 100)
        self.assertTrue(report["weak_points"])

    def test_generate_stops_when_cancel_check_is_set_before_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ClassroomStorage(tmpdir)
            generator = InteractiveClassroomGenerator(
                backend_dir=BACKEND_DIR,
                storage=storage,
                llm_quiz_enabled=False,
            )

            with self.assertRaises(ClassroomGenerationCancelled):
                generator.generate(
                    user_id="user_1",
                    topic="测试主题",
                    course="测试课程",
                    tts_config={},
                    cancel_check=lambda: True,
                )

            self.assertEqual([], storage.list_classrooms("user_1"))


if __name__ == "__main__":
    unittest.main()
