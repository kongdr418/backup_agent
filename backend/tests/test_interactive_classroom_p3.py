from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import asdict


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from interactive_classroom.generator import (
    ClassroomGenerationCancelled,
    InteractiveClassroomGenerator,
    _emit_ordered_ready_scenes,
    _emit_progress,
    _synthesize_scene_speech_actions,
)
from interactive_classroom.generator import _derive_slide_title
from interactive_classroom.quiz_service import evaluate_quiz_scene
from interactive_classroom.report_service import build_classroom_report
from interactive_classroom.schema import ClassroomAction, ClassroomScene
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
        # 密度调整：3 张讲解 → 1 个 mid 测验 + 末尾 1 个 final
        # 5 张 slide → 2 个 quiz（mid 在 slide 1-3，final 在 slide 4-5）
        scenes = [
            _slide(1, "导入", ["学习目标"]),
            _slide(2, "概念 A", ["要点 A1"]),
            _slide(3, "概念 B", ["要点 B1"]),
            _slide(4, "案例分析", ["案例步骤"]),
            _slide(5, "综合应用", ["迁移练习"]),
        ]

        result = self.generator._insert_quiz_scenes("测试主题", scenes)  # noqa: SLF001

        quiz_scenes = [scene for scene in result if scene.type == "quiz"]
        self.assertEqual(["scene_quiz_001", "scene_quiz_002"], [scene.id for scene in quiz_scenes])
        self.assertEqual(["scene_slide_001", "scene_slide_002", "scene_slide_003"], quiz_scenes[0].content["covered_scene_ids"])
        self.assertEqual(["scene_slide_004", "scene_slide_005"], quiz_scenes[1].content["covered_scene_ids"])
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

    def test_skips_cover_slide_decorative_text_as_quiz_source(self) -> None:
        scenes = [
            _slide(
                1,
                "今天我们将一起探索化...",
                ["CHEMISTRY EXPLORATION", "探索元素周期表", "化学家的地图，物质世界的钥匙", "2023年10月"],
            ),
            _slide(2, "周期表的基本结构", ["周期", "族", "原子序数"]),
            _slide(3, "元素性质的周期性", ["金属性", "非金属性", "原子半径"]),
        ]

        result = self.generator._insert_quiz_scenes("元素周期表", scenes)  # noqa: SLF001

        quiz_scenes = [scene for scene in result if scene.type == "quiz"]
        covered_ids = [
            scene_id
            for quiz in quiz_scenes
            for scene_id in quiz.content["covered_scene_ids"]
        ]
        question_blob = "\n".join(
            question["question"]
            for quiz in quiz_scenes
            for question in quiz.content["questions"]
        )

        self.assertNotIn("scene_slide_001", covered_ids)
        self.assertIn("scene_slide_002", covered_ids)
        self.assertNotIn("CHEMISTRY EXPLORATION", question_blob)
        self.assertNotIn("探索元素周期表", question_blob)

    def test_derives_stable_slide_title_from_svg_filename_before_svg_text(self) -> None:
        title = _derive_slide_title(
            idx=8,
            filename="08_课程总结.svg",
            svg_texts=["Springboot入门课程", "提问与讨论", "课程总结"],
        )

        self.assertEqual("课程总结", title)

    def test_derives_slide_title_without_markdown_heading_marks(self) -> None:
        title = _derive_slide_title(
            idx=1,
            filename="01.svg",
            svg_texts=["世界地理"],
            manuscript_note="# 世界地理\n本节课我们将从宏观角度认识地球。",
        )

        self.assertEqual("世界地理 本节课我们将从宏观角度认识地球", title)

    def test_progress_event_includes_renderable_scene_payload(self) -> None:
        events: list[dict] = []
        scene = ClassroomScene(
            id="scene_slide_001",
            type="slide",
            title="世界地理",
            order=1,
            knowledge_points=["七大洲"],
            content={"format": "markdown", "markdown": "## 世界地理"},
            actions=[],
        )

        _emit_progress(
            events.append,
            stage="build_scenes",
            stage_index=1,
            scene_index=1,
            scene_total=10,
            scene=scene,
        )

        self.assertEqual("scene_slide_001", events[0]["scene"]["id"])
        self.assertEqual("世界地理", events[0]["scene_payload"]["title"])
        self.assertEqual("## 世界地理", events[0]["scene_payload"]["content"]["markdown"])

    def test_emits_ready_slide_scenes_in_original_order_only(self) -> None:
        events: list[dict] = []
        ready = {
            2: _slide(2, "第二页", ["B"]),
        }

        next_index = _emit_ordered_ready_scenes(
            events.append,
            stage="build_scenes",
            stage_index=1,
            ready_scenes=ready,
            next_emit_index=1,
            scene_total=3,
        )

        self.assertEqual(1, next_index)
        self.assertEqual([], events)

        ready[1] = _slide(1, "第一页", ["A"])
        ready[3] = _slide(3, "第三页", ["C"])
        next_index = _emit_ordered_ready_scenes(
            events.append,
            stage="build_scenes",
            stage_index=1,
            ready_scenes=ready,
            next_emit_index=next_index,
            scene_total=3,
        )

        self.assertEqual(4, next_index)
        self.assertEqual(["scene_slide_001", "scene_slide_002", "scene_slide_003"], [
            event["scene_payload"]["id"] for event in events
        ])

    def test_quiz_progress_event_uses_final_order(self) -> None:
        events: list[dict] = []
        scenes = [
            _slide(1, "导入", ["学习目标"]),
            _slide(2, "概念 A", ["要点 A1"]),
            _slide(3, "概念 B", ["要点 B1"]),
        ]

        self.generator._insert_quiz_scenes(  # noqa: SLF001
            "测试主题",
            scenes,
            progress_callback=events.append,
        )

        quiz_events = [
            event for event in events
            if event.get("scene_payload", {}).get("type") == "quiz"
        ]
        self.assertTrue(quiz_events)
        self.assertGreater(quiz_events[0]["scene_payload"]["order"], 0)

    def test_tts_progress_can_update_scene_payload_with_audio_url(self) -> None:
        events: list[dict] = []
        scene = ClassroomScene(
            id="scene_slide_001",
            type="slide",
            title="世界地理",
            order=1,
            actions=[],
        )
        scene.actions.append(
            ClassroomAction(
                id="act_slide_001",
                type="speech",
                text="欢迎进入课堂",
                audio_url="/api/interactive-classroom/cls_001/audio/act_slide_001.mp3",
            )
        )

        _emit_progress(
            events.append,
            stage="synthesize_tts",
            stage_index=3,
            scene_index=1,
            scene_total=1,
            scene=scene,
        )

        self.assertEqual(
            "/api/interactive-classroom/cls_001/audio/act_slide_001.mp3",
            events[0]["scene_payload"]["actions"][0]["audio_url"],
        )

    def test_synthesizes_single_slide_before_streaming_scene(self) -> None:
        class StubTTS:
            def synthesize_action(self, action_id, text, output_dir):  # noqa: ANN001
                self.called_with = (action_id, text, output_dir)
                return f"{action_id}.wav"

        scene = ClassroomScene(
            id="scene_slide_001",
            type="slide",
            title="世界地理",
            order=1,
            actions=[ClassroomAction(id="act_slide_001", type="speech", text="欢迎进入课堂")],
        )
        service = StubTTS()

        _synthesize_scene_speech_actions(
            service=service,  # type: ignore[arg-type]
            scene=scene,
            audio_dir="/tmp/classroom-audio",
            classroom_id="cls_001",
        )

        self.assertEqual(("act_slide_001", "欢迎进入课堂", "/tmp/classroom-audio"), service.called_with)
        self.assertEqual(
            "/api/interactive-classroom/cls_001/audio/act_slide_001.wav",
            scene.actions[0].audio_url,
        )

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

    def test_rejects_llm_quiz_about_cover_decoration_terms(self) -> None:
        class CoverDecorationQuizGenerator:
            def generate_context_quiz_json(self, topic, slide_summaries, question_count):  # noqa: ANN001
                return """
                {
                  "modules": [
                    {
                      "title": "CHEMISTRY EXPLORATION",
                      "questions": [
                        {
                          "num": "1",
                          "type": "单选题",
                          "text": "关于“CHEMISTRY EXPLORATION”，以下哪一项最能说明本节要求掌握的判断依据？",
                          "options": ["A. 化学家的地图，物质世界的钥匙", "B. 理解物质世界构成的钥匙", "C. CHEMISTRY EXPLORATION", "D. 探索元素周期表"],
                          "answer": "B",
                          "analysis": "应关注知识点而不是封面标签。",
                          "knowledge_point": "CHEMISTRY EXPLORATION"
                        }
                      ]
                    }
                  ]
                }
                """

        generator = InteractiveClassroomGenerator(
            backend_dir=BACKEND_DIR,
            storage=None,  # type: ignore[arg-type]
            quiz_generator=CoverDecorationQuizGenerator(),
        )
        scenes = [
            _slide(1, "今天我们将一起探索化...", ["CHEMISTRY EXPLORATION", "探索元素周期表"]),
            _slide(2, "周期表的基本结构", ["周期", "族", "原子序数"]),
        ]

        quiz_scene = generator._build_quiz_scene(1, 2, "元素周期表", scenes)  # noqa: SLF001

        self.assertEqual("slide_text", quiz_scene.content["quiz_source"])
        question_blob = "\n".join(q["question"] for q in quiz_scene.content["questions"])
        self.assertNotIn("CHEMISTRY EXPLORATION", question_blob)

    def test_preserves_html_tag_literals_in_llm_quiz_options(self) -> None:
        class HtmlTagQuizGenerator:
            def generate_context_quiz_json(self, topic, slide_summaries, question_count):  # noqa: ANN001
                return """
                {
                  "modules": [
                    {
                      "title": "HTML 标签",
                      "questions": [
                        {
                          "num": "1",
                          "type": "单选题",
                          "text": "以下哪个标签通常用于定义段落？",
                          "options": ["A. <p>", "B. <h1>", "C. <a>", "D. <img>"],
                          "answer": "A",
                          "analysis": "<p> 用于定义段落，<h1> 用于标题。",
                          "knowledge_point": "HTML 标签"
                        }
                      ]
                    }
                  ]
                }
                """

        generator = InteractiveClassroomGenerator(
            backend_dir=BACKEND_DIR,
            storage=None,  # type: ignore[arg-type]
            quiz_generator=HtmlTagQuizGenerator(),
        )

        quiz_scene = generator._build_quiz_scene(1, 1, "HTML 基础", [_slide(1, "HTML 标签", ["段落标签"])])  # noqa: SLF001
        question = quiz_scene.content["questions"][0]

        self.assertEqual("<p>", question["options"][0]["label"])
        self.assertEqual("<h1>", question["options"][1]["label"])
        self.assertIn("<p>", question["analysis"])

    def test_report_aggregates_multiple_quiz_scene_answers_independently(self) -> None:
        # 密度调整后：3 张讲解 → 1 mid 测验 + 末尾 1 个 final
        # 4 张 slide（全部 quiz source）→ 2 个 quiz
        # 注意 slide 标题要避开 QUIZ_SOURCE_SKIP_KEYWORDS（"总结"/"复盘"等）
        # 否则那张 slide 不计入 quiz_source 序列，新阈值下可能只产 1 个 quiz
        scenes = [
            _slide(1, "导入", ["学习目标"]),
            _slide(2, "概念 A", ["要点 A1"]),
            _slide(3, "概念 B", ["要点 B1"]),
            _slide(4, "应用演练", ["动手练习"]),
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
        self.assertEqual([quiz_scenes[0].id, quiz_scenes[1].id], report["answered_scene_ids"])
        self.assertGreater(report["total"], 0)
        self.assertLess(report["score"], 100)
        self.assertTrue(report["weak_points"])
        self.assertEqual("review_weak_points", report["recommended_tasks"][0]["type"])
        self.assertEqual(report["weak_points"][:3], report["recommended_tasks"][0]["knowledge_points"])
        # 4 张 slide + 3 张 → 1 mid 阈值 → quiz 2（final）覆盖 slide_004
        # 第一 quiz 全对（不计入 weak_points），所以 target_scene_ids 指向错答的 quiz 2
        self.assertIn("scene_slide_004", report["recommended_tasks"][0]["target_scene_ids"])
        self.assertEqual("practice_weak_points", report["recommended_tasks"][1]["type"])
        self.assertEqual("high", report["recommended_tasks"][0]["priority"])
        self.assertEqual(
            ["diagnose", "review", "practice", "next_lesson"],
            [stage["type"] for stage in report["learning_path"]],
        )
        self.assertEqual("评估 Agent", report["learning_path"][0]["agent_name"])
        self.assertEqual("路径规划 Agent", report["learning_path"][1]["agent_name"])
        self.assertEqual(report["recommended_tasks"][0]["id"], report["learning_path"][1]["task_id"])
        self.assertEqual(report["recommended_tasks"][1]["id"], report["learning_path"][2]["task_id"])
        self.assertEqual("active", report["learning_path"][1]["status"])

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
