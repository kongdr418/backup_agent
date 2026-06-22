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
    _extract_svg_highlight_targets,
    _fallback_teaching_segments,
    _sanitize_animation_lab_html,
    _select_teaching_targets,
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

    def test_renumbers_quizzes_when_an_earlier_quiz_generation_fails(self) -> None:
        scenes = [
            _slide(1, "导入", ["学习目标"]),
            _slide(2, "概念 A", ["要点 A1"]),
            _slide(3, "概念 B", ["要点 B1"]),
            _slide(4, "案例分析", ["案例步骤"]),
            _slide(5, "综合应用", ["迁移练习"]),
        ]
        original_build_quiz_scene = self.generator._build_quiz_scene  # noqa: SLF001

        def flaky_build_quiz_scene(**kwargs):  # noqa: ANN001
            if kwargs["quiz_index"] == 1:
                return None
            return original_build_quiz_scene(**kwargs)

        self.generator._build_quiz_scene = flaky_build_quiz_scene  # type: ignore[method-assign]  # noqa: SLF001

        result = self.generator._insert_quiz_scenes("测试主题", scenes)  # noqa: SLF001

        quiz_scenes = [scene for scene in result if scene.type == "quiz"]
        self.assertEqual(1, len(quiz_scenes))
        self.assertEqual("scene_quiz_001", quiz_scenes[0].id)
        self.assertEqual("随堂测验 1：测试主题", quiz_scenes[0].title)
        self.assertEqual(["scene_slide_004", "scene_slide_005"], quiz_scenes[0].content["covered_scene_ids"])
        self.assertTrue(all(q["id"].startswith("q1_") for q in quiz_scenes[0].content["questions"]))

    def test_preserves_inserted_interactive_scene_before_generated_quiz(self) -> None:
        scenes = [
            _slide(1, "导入", ["学习目标"]),
            _slide(2, "概念 A", ["要点 A1"]),
            _slide(3, "概念 B", ["要点 B1"]),
            ClassroomScene(
                id="scene_animation_test",
                type="animation_lab",
                title="概念 B 动画实验",
                order=0,
                knowledge_points=["要点 B1"],
                content={"format": "html", "html": "<!doctype html><html></html>"},
                actions=[],
            ),
            _slide(4, "案例分析", ["案例步骤"]),
        ]

        result = self.generator._insert_quiz_scenes("测试主题", scenes)  # noqa: SLF001

        ordered_ids = [scene.id for scene in result]
        self.assertIn("scene_animation_test", ordered_ids)
        self.assertLess(
            ordered_ids.index("scene_animation_test"),
            ordered_ids.index("scene_quiz_001"),
        )
        self.assertEqual(
            ["scene_slide_001", "scene_slide_002", "scene_slide_003"],
            next(scene for scene in result if scene.id == "scene_quiz_001").content["covered_scene_ids"],
        )

    def test_ordered_ppt_generation_streams_quizzes_in_playback_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = os.path.join(tmpdir, "generated_svg_ppt", "users", "user_1", "job_1")
            svg_dir = os.path.join(job_dir, "svg_final")
            os.makedirs(svg_dir)
            with open(os.path.join(job_dir, "manuscript.md"), "w", encoding="utf-8") as f:
                f.write("\n---\n".join([f"第 {idx} 页讲稿" for idx in range(1, 6)]))
            for idx in range(1, 6):
                with open(os.path.join(svg_dir, f"slide_{idx:03d}.svg"), "w", encoding="utf-8") as f:
                    f.write(
                        f"""
                        <svg viewBox="0 0 1000 562">
                          <text x="80" y="100" font-size="32">概念 {idx}</text>
                          <text x="120" y="210" font-size="24">要点 {idx}</text>
                        </svg>
                        """
                    )

            generator = InteractiveClassroomGenerator(
                backend_dir=tmpdir,
                storage=None,  # type: ignore[arg-type]
                llm_quiz_enabled=False,
            )

            def teaching_segments(**kwargs):  # noqa: ANN001
                page_index = int(kwargs["page_index"])
                return [
                    {
                        "target_id": "hl_001",
                        "mode": "spotlight",
                        "text": f"第 {page_index} 页讲解内容，说明概念 {page_index} 的判断依据。",
                    }
                ], {}

            def mindmap_scene(topic, scenes, student_profile=None, cancel_check=None):  # noqa: ANN001, ARG001
                return ClassroomScene(
                    id="scene_mindmap_test",
                    type="mindmap",
                    title=f"知识结构：{topic}",
                    order=0,
                    knowledge_points=[topic],
                    content={"format": "markmap", "markmap_md": f"# {topic}"},
                    actions=[],
                )

            generator._generate_teaching_segments = teaching_segments  # type: ignore[method-assign]  # noqa: SLF001
            generator._build_mindmap_scene = mindmap_scene  # type: ignore[method-assign]  # noqa: SLF001
            events: list[dict] = []

            scenes = generator._build_ordered_scenes_from_ppt_job(  # noqa: SLF001
                user_id="user_1",
                ppt_job_id="job_1",
                topic="测试主题",
                course="测试课程",
                progress_callback=events.append,
            )

        ordered_ids = [scene.id for scene in scenes]
        self.assertEqual(
            [
                "scene_slide_001",
                "scene_slide_002",
                "scene_slide_003",
                "scene_quiz_001",
                "scene_slide_004",
                "scene_slide_005",
                "scene_quiz_002",
                "scene_mindmap_test",
            ],
            ordered_ids,
        )
        streamed_ids = [
            event["scene_payload"]["id"]
            for event in events
            if event.get("scene_payload")
        ]
        self.assertEqual(ordered_ids, streamed_ids)

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

    def test_selects_teaching_targets_across_full_slide_not_only_front_labels(self) -> None:
        texts = [
            "人工神经元的工作原理",
            "神经元处理流程",
            "输入信号",
            "x₁",
            "x₂",
            "x₃",
            "多个输入",
            "权重",
            "w₁",
            "w₂",
            "w₃",
            "重要性",
            "求和",
            "Σ(xᵢ × wᵢ)",
            "+ 偏置 b",
            "激活函数",
            "σ(z)",
            "输出 y",
            "0 或 1",
            "核心步骤：",
            "1. 接收多个输入信号（x₁, x₂, x₃...）",
            "2. 乘以对应权重，加权求和",
            "3. 通过激活函数判断",
            "4. 输出激活或抑制信号",
            "🎯 生活类比",
            "📐 数学表达",
            "✨ 核心要点",
        ]
        targets = [
            {"id": f"hl_{idx + 1:03d}", "text": text}
            for idx, text in enumerate(texts)
        ]

        selected = _select_teaching_targets(targets, limit=16)
        selected_text = "\n".join(str(target["text"]) for target in selected)

        self.assertIn("求和", selected_text)
        self.assertIn("激活函数", selected_text)
        self.assertIn("输出 y", selected_text)
        self.assertIn("📐 数学表达", selected_text)
        self.assertIn("✨ 核心要点", selected_text)
        self.assertNotIn("w₁", selected_text)

    def test_extracts_highlight_targets_deep_enough_for_full_process_slides(self) -> None:
        svg = """
        <svg>
          <text x="10" y="20">PAGE 03 / 06</text>
          <text x="10" y="40">人工神经元的工作原理</text>
          <text x="10" y="60">神经元处理流程</text>
          <text x="10" y="80">输入信号</text>
          <text x="10" y="100">x₁</text>
          <text x="10" y="120">x₂</text>
          <text x="10" y="140">x₃</text>
          <text x="10" y="160">多个输入</text>
          <text x="10" y="180">权重</text>
          <text x="10" y="200">w₁</text>
          <text x="10" y="220">w₂</text>
          <text x="10" y="240">w₃</text>
          <text x="10" y="260">重要性</text>
          <text x="10" y="280">求和</text>
          <text x="10" y="300">Σ(xᵢ × wᵢ)</text>
          <text x="10" y="320">激活函数</text>
          <text x="10" y="340">输出 y</text>
          <text x="10" y="360">📐 数学表达</text>
          <text x="10" y="380">✨ 核心要点</text>
        </svg>
        """

        target_text = "\n".join(
            str(target["text"])
            for target in _extract_svg_highlight_targets(svg)
        )

        self.assertIn("求和", target_text)
        self.assertIn("激活函数", target_text)
        self.assertIn("输出 y", target_text)
        self.assertIn("📐 数学表达", target_text)
        self.assertIn("✨ 核心要点", target_text)

    def test_fallback_teaching_segments_cover_full_neuron_process(self) -> None:
        svg_texts = [
            "人工神经元的工作原理",
            "神经元处理流程",
            "输入信号",
            "x₁",
            "x₂",
            "x₃",
            "多个输入",
            "权重",
            "重要性",
            "求和",
            "Σ(xᵢ × wᵢ)",
            "偏置 b",
            "激活函数",
            "σ(z)",
            "输出 y",
            "核心步骤：",
            "1. 接收多个输入信号（x₁, x₂, x₃...）",
            "2. 乘以对应权重，加权求和",
            "3. 通过激活函数判断",
            "4. 输出激活或抑制信号",
            "📐 数学表达",
            "z = Σ(xᵢ × wᵢ) + b",
            "y = σ(z) = 1/(1 + e⁻ᶻ)",
            "✨ 核心要点",
        ]
        targets = [
            {"id": f"hl_{idx + 1:03d}", "text": text}
            for idx, text in enumerate(svg_texts)
        ]
        manuscript = (
            "那么，一个人工神经元到底在做什么呢？我们可以把它想象成一个简单的决策单元。"
            "它接收来自其他神经元的多个输入信号，每个信号都有一个重要性权重，就像我们做决定时会综合考虑不同意见的份量。"
            "然后它会对所有加权输入求和，并通过一个“激活函数”来判断这个总和是否足够强，从而决定是否要“激活”并向外传递一个输出信号。"
        )

        segments = _fallback_teaching_segments(
            "人工神经元的工作原理",
            manuscript,
            targets,
            svg_texts,
        )
        speech = "\n".join(str(segment["text"]) for segment in segments)
        target_text = "\n".join(
            next(target["text"] for target in targets if target["id"] == segment["target_id"])
            for segment in segments
        )

        self.assertIn("输入信号", speech)
        self.assertIn("权重", speech)
        self.assertIn("求和", speech)
        self.assertIn("激活函数", speech)
        self.assertIn("输出信号", speech)
        self.assertIn("z = Σ", speech)
        self.assertIn("y = σ", speech)
        self.assertIn("输出 y", target_text)
        self.assertNotIn("最后看“x₁”", speech)

    def test_fallback_teaching_segments_cover_learning_mechanism_svg_cards(self) -> None:
        svg_texts = [
            "核心概念",
            "神经网络的\"学习\"机制",
            "通过反向传播算法，网络自动调整权重，逐步提升准确率",
            "随机初始化",
            "权重随机设置",
            "输出是错的",
            "训练数据",
            "大量标注样本",
            "如猫狗图片",
            "计算误差",
            "对比预测与真实",
            "量化错误程度",
            "反向传播",
            "自动调整权重",
            "梯度下降优化",
            "🔄 反复迭代，直到准确率达标",
            "关键要点",
            "网络开始时权重随机",
            "初始输出完全不准确",
            "这是学习的起点",
            "数据驱动",
            "上万张标注图片作为教材",
            "每张图片告诉网络正确答案",
            "对比预测与真实标签",
            "核心算法自动调整权重",
            "反复迭代持续优化",
            "最终达到高准确率",
        ]
        targets = [
            {"id": f"hl_{idx + 1:03d}", "text": text}
            for idx, text in enumerate(svg_texts)
        ]
        manuscript = (
            "神经网络最关键的部分在于“学习”。一开始，网络内部连接的权重是随机设置的，给出的输出也是错的。"
            "通过向它展示大量的例子（比如上万张标注好的猫和狗的图片），并告诉它每次判断错了多少，网络就能利用一种叫做“反向传播”的算法来自动调整那些权重。"
            "这个过程反复进行，直到它能够做出非常准确的判断。"
        )

        segments = _fallback_teaching_segments(
            "神经网络的学习机制",
            manuscript,
            targets,
            svg_texts,
        )
        speech = "\n".join(str(segment["text"]) for segment in segments)

        self.assertIn("随机初始化", speech)
        self.assertIn("训练数据", speech)
        self.assertIn("计算预测和真实答案之间的误差", speech)
        self.assertIn("反向传播", speech)
        self.assertIn("反复迭代", speech)
        self.assertIn("准确率达标", speech)

    def test_practice_quiz_filters_learning_report_meta_questions(self) -> None:
        class MetaPracticeQuizGenerator:
            def generate_context_quiz_json(self, topic, slide_summaries, question_count, **kwargs):  # noqa: ANN001
                return """
                {
                  "modules": [
                    {
                      "title": "补强练习",
                      "questions": [
                        {
                          "num": "1",
                          "type": "单选题",
                          "text": "根据学习报告的建议，学生被推荐优先复习以下哪些内容？",
                          "options": ["A. 神经网络的起源与灵感", "B. 编程框架", "C. 硬件配置", "D. 历史人物"],
                          "answer": "A",
                          "analysis": "学习报告建议优先复习该内容。",
                          "knowledge_point": "神经网络的起源与灵感"
                        },
                        {
                          "num": "2",
                          "type": "单选题",
                          "text": "人工神经网络的设计灵感主要来源于什么？",
                          "options": ["A. 生物神经网络的结构和工作方式", "B. 数字电路的门逻辑组合", "C. 流体力学规律", "D. 遗传信息编码"],
                          "answer": "A",
                          "analysis": "课堂内容说明人工神经网络受到生物神经网络启发。",
                          "knowledge_point": "神经网络的起源与灵感"
                        }
                      ]
                    }
                  ]
                }
                """

        generator = InteractiveClassroomGenerator(
            backend_dir=BACKEND_DIR,
            storage=None,  # type: ignore[arg-type]
            quiz_generator=MetaPracticeQuizGenerator(),
        )

        scene = generator.build_practice_quiz_scene(
            topic="神经网络",
            knowledge_points=["神经网络的起源与灵感"],
            task_type="practice_weak_points",
            generation_strategy={
                "assessment_strategy": {
                    "practice_diagnostic_notes": ["学习报告建议：优先复习神经网络的起源与灵感"],
                    "practice_evidence": [
                        {
                            "point": "神经网络的起源与灵感",
                            "snippets": ["人工神经网络受到生物神经网络结构和工作方式启发"],
                        }
                    ],
                }
            },
        )
        question_text = "\n".join(q["question"] for q in scene.content["questions"])

        self.assertNotIn("学习报告", question_text)
        self.assertIn("人工神经网络的设计灵感", question_text)

    def test_practice_quiz_context_excludes_diagnostic_notes_from_page_text(self) -> None:
        class CapturingPracticeQuizGenerator:
            def generate_context_quiz_json(self, topic, slide_summaries, question_count, **kwargs):  # noqa: ANN001
                self.slide_summaries = slide_summaries
                return """
                {
                  "modules": [
                    {
                      "questions": [
                        {
                          "type": "单选题",
                          "text": "人工神经网络的设计灵感主要来源于什么？",
                          "options": ["A. 生物神经网络的结构和工作方式", "B. 数字电路", "C. 历史人物", "D. 硬件配置"],
                          "answer": "A",
                          "analysis": "课堂证据说明它受到生物神经网络启发。",
                          "knowledge_point": "神经网络的起源与灵感"
                        }
                      ]
                    }
                  ]
                }
                """

        quiz_generator = CapturingPracticeQuizGenerator()
        generator = InteractiveClassroomGenerator(
            backend_dir=BACKEND_DIR,
            storage=None,  # type: ignore[arg-type]
            quiz_generator=quiz_generator,
        )

        generator.build_practice_quiz_scene(
            topic="神经网络",
            knowledge_points=["神经网络的起源与灵感"],
            task_type="practice_weak_points",
            generation_strategy={
                "assessment_strategy": {
                    "practice_diagnostic_notes": ["学习报告建议：优先复习神经网络的起源与灵感"],
                    "practice_evidence": [
                        {
                            "point": "神经网络的起源与灵感",
                            "snippets": ["人工神经网络受到生物神经网络结构和工作方式启发"],
                        }
                    ],
                }
            },
        )

        page_text = "\n".join(
            text
            for summary in quiz_generator.slide_summaries
            for text in summary.get("extracted_text", [])
        )
        self.assertIn("人工神经网络受到生物神经网络结构和工作方式启发", page_text)
        self.assertNotIn("学习报告建议", page_text)

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

    def test_fallback_quiz_filters_slide_fragments_and_teacher_leadins(self) -> None:
        class BadQuizGenerator:
            def generate_context_quiz_json(self, topic, slide_summaries, question_count):  # noqa: ANN001
                return '{"modules": [{"questions": [{"text": "缺少选项和答案"}]}]}'

        generator = InteractiveClassroomGenerator(
            backend_dir=BACKEND_DIR,
            storage=None,  # type: ignore[arg-type]
            quiz_generator=BadQuizGenerator(),
        )
        scene = ClassroomScene(
            id="scene_slide_005",
            type="slide",
            title="第二种情况：当物体放在一倍焦距和两倍焦距之间",
            order=1,
            knowledge_points=[
                "凸透镜成像规律",
                "—— 情况二：f < u < 2f",
                "光路示意图",
                "主光轴",
            ],
            content={
                "extracted_text": [
                    "光路示意图",
                    "—— 情况二：f < u < 2f",
                    "主光轴",
                ]
            },
            actions=[
                ClassroomAction(
                    id="act_slide_005",
                    type="speech",
                    text=(
                        "同学们，我们来看凸透镜成像的第二种情况。"
                        "当物体位于一倍焦距和两倍焦距之间时，凸透镜会形成倒立、放大的实像。"
                        "这种情况说明物距范围会直接决定像的大小和倒正。"
                    ),
                )
            ],
        )

        quiz_scene = generator._build_quiz_scene(1, 1, "凸透镜成像", [scene])  # noqa: SLF001

        self.assertEqual("slide_text", quiz_scene.content["quiz_source"])
        rows: list[str] = []
        for question in quiz_scene.content["questions"]:
            rows.append(question["question"])
            rows.extend(option["label"] for option in question.get("options", []))
            rows.append(question.get("knowledge_point", ""))
        blob = "\n".join(rows)
        self.assertNotIn("同学们", blob)
        self.assertNotIn("我们来看", blob)
        self.assertNotIn("—— 情况二", blob)
        self.assertNotIn("光路示意图", blob)
        self.assertNotIn("主光轴", blob)
        self.assertIn("倒立、放大的实像", blob)

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

    def test_animation_lab_scene_is_inserted_when_llm_decides_it_is_useful(self) -> None:
        class AnimationLabGenerator(InteractiveClassroomGenerator):
            def _call_content_llm_animation_lab(self, prompt: str) -> str:  # noqa: ARG002
                return """
                {
                  "should_generate": true,
                  "reason": "凸透镜成像涉及物距和像距变化，适合通过滑块观察规律。",
                  "placement_after_scene_id": "scene_slide_002",
                  "title": "凸透镜成像互动实验",
                  "summary": "拖动物距，观察像的位置和性质变化。",
                  "knowledge_points": ["物距", "像距", "实像与虚像"],
                  "video_prompt": "生成凸透镜成像光路动画",
                  "html": "<!doctype html><html><head><style>body{margin:0}canvas{border:1px solid #ddd}</style></head><body><canvas id='c' width='600' height='400'></canvas><input type='range' id='u'><button>播放</button><script>const c=document.getElementById('c');const ctx=c.getContext('2d');function draw(){ctx.fillStyle='#2D5016';ctx.fillRect(20,20,100,80);}draw();</script></body></html>"
                }
                """

        generator = AnimationLabGenerator(
            backend_dir=BACKEND_DIR,
            storage=None,  # type: ignore[arg-type]
            llm_quiz_enabled=True,
        )
        scenes = [
            _slide(1, "导入", ["学习目标"]),
            _slide(2, "凸透镜成像规律", ["物距", "像距"]),
            _slide(3, "像的性质", ["实像", "虚像"]),
        ]

        animation_scene = generator._maybe_build_animation_lab_scene(  # noqa: SLF001
            topic="凸透镜成像",
            course="大学物理",
            scenes=scenes,
        )
        self.assertIsNotNone(animation_scene)
        assert animation_scene is not None
        result = generator._insert_animation_lab_scene(scenes, animation_scene)  # noqa: SLF001

        self.assertEqual("animation_lab", animation_scene.type)
        self.assertEqual("scene_slide_002", result[1].id)
        self.assertEqual(animation_scene.id, result[2].id)
        self.assertIn('width="1200"', animation_scene.content["html"])
        self.assertIn("ai-creator-animation-lab-embed", animation_scene.content["html"])
        self.assertEqual("llm_decision", animation_scene.content["source"])

    def test_animation_lab_html_sanitizer_rejects_external_resources(self) -> None:
        html = "<!doctype html><html><body><script src='https://example.com/a.js'></script></body></html>"
        self.assertEqual("", _sanitize_animation_lab_html(html))

    def test_animation_lab_html_sanitizer_injects_classroom_embed_style(self) -> None:
        html = (
            "<!doctype html><html><head><style>body{padding:20px}</style></head>"
            "<body><canvas width='600' height='400'></canvas><input type='range'></body></html>"
        )

        sanitized = _sanitize_animation_lab_html(html)

        self.assertIn("ai-creator-animation-lab-embed", sanitized)
        self.assertIn("overflow: hidden !important", sanitized)
        self.assertIn('width="1200"', sanitized)


if __name__ == "__main__":
    unittest.main()
