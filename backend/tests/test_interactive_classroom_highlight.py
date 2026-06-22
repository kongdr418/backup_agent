from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from interactive_classroom.generator import (  # noqa: E402
    _build_highlight_cues_from_teaching_segments,
    InteractiveClassroomGenerator,
    _build_highlight_cues,
    _extract_svg_highlight_targets,
    _split_speech_segments,
    _speech_text_from_manuscript,
)
from interactive_classroom.storage import ClassroomStorage  # noqa: E402


class InteractiveClassroomHighlightTest(unittest.TestCase):
    def test_split_speech_segments_keeps_meaningful_manuscript_sentences(self) -> None:
        manuscript = "这一页先看核心概念：依赖注入。然后关注 Bean 的创建流程；最后注意自动装配的入口。"

        self.assertEqual(
            _split_speech_segments(manuscript),
            [
                "这一页先看核心概念：依赖注入。",
                "然后关注 Bean 的创建流程；",
                "最后注意自动装配的入口。",
            ],
        )

    def test_speech_text_from_manuscript_preserves_more_than_brief_excerpt(self) -> None:
        manuscript = "第一句说明背景。" + "第二句补充细节。" * 30

        speech = _speech_text_from_manuscript(manuscript)

        self.assertGreater(len(speech), 220)
        self.assertLessEqual(len(speech), 900)

    def test_speech_text_from_manuscript_softens_repetitive_classroom_opening(self) -> None:
        manuscript = "同学们，今天我们来聊聊化学元素周期表为什么这么重要。它藏着一套规律。"

        speech = _speech_text_from_manuscript(manuscript)

        self.assertEqual("这一页我们聊聊化学元素周期表为什么这么重要。它藏着一套规律。", speech)

    def test_extract_svg_highlight_targets_reads_text_bboxes(self) -> None:
        svg = """
        <svg viewBox="0 0 1000 562">
          <text x="80" y="100" font-size="32">依赖注入</text>
          <text x="120" y="210" font-size="24">Bean 创建流程</text>
        </svg>
        """

        targets = _extract_svg_highlight_targets(svg)

        self.assertEqual([item["text"] for item in targets], ["依赖注入", "Bean 创建流程"])
        self.assertEqual(targets[0]["id"], "hl_001")
        self.assertEqual(targets[0]["bbox"]["x"], 80)
        self.assertLess(targets[0]["bbox"]["y"], 100)
        self.assertGreater(targets[1]["bbox"]["width"], 100)

    def test_build_highlight_cues_matches_segments_to_targets(self) -> None:
        segments = ["这一页先看依赖注入。", "然后关注 Bean 的创建流程。", "最后总结核心概念。"]
        targets = [
            {"id": "hl_001", "text": "依赖注入", "bbox": {"x": 80, "y": 80, "width": 120, "height": 36}},
            {"id": "hl_002", "text": "Bean 创建流程", "bbox": {"x": 120, "y": 190, "width": 180, "height": 30}},
        ]

        cues = _build_highlight_cues(segments, targets)

        self.assertEqual([item["target_id"] for item in cues], ["hl_001", "hl_002", "hl_001"])
        self.assertEqual(cues[0]["start_ratio"], 0)
        self.assertAlmostEqual(cues[0]["end_ratio"], 1 / 3, places=3)
        self.assertEqual(cues[0]["mode"], "spotlight")
        self.assertEqual(cues[1]["mode"], "outline")

    def test_teaching_segment_cues_are_weighted_by_speech_length(self) -> None:
        cues = _build_highlight_cues_from_teaching_segments(
            [
                {"target_id": "hl_001", "mode": "spotlight", "text": "短句。"},
                {"target_id": "hl_002", "mode": "outline", "text": "这一段讲解明显更长，需要占用更长的播放时间，避免高亮提前跳走。"},
            ]
        )

        self.assertLess(cues[0]["end_ratio"], 0.2)
        self.assertEqual(cues[1]["start_ratio"], cues[0]["end_ratio"])
        self.assertEqual(cues[1]["end_ratio"], 1)

    def test_ppt_job_scenes_include_highlight_metadata_from_manuscript(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = os.path.join(tmpdir, "generated_svg_ppt", "users", "user_1", "job_1")
            svg_dir = os.path.join(job_dir, "svg_final")
            os.makedirs(svg_dir)
            with open(os.path.join(job_dir, "manuscript.md"), "w", encoding="utf-8") as f:
                f.write("这一页先看依赖注入。然后关注 Bean 的创建流程。")
            with open(os.path.join(svg_dir, "slide_001.svg"), "w", encoding="utf-8") as f:
                f.write(
                    """
                    <svg viewBox="0 0 1000 562">
                      <text x="80" y="100" font-size="32">依赖注入</text>
                      <text x="120" y="210" font-size="24">Bean 创建流程</text>
                    </svg>
                    """
                )

            generator = InteractiveClassroomGenerator(tmpdir, ClassroomStorage(tmpdir))
            scenes = generator._build_slide_scenes_from_ppt_job("user_1", "job_1")

        self.assertEqual(len(scenes), 1)
        scene = scenes[0]
        self.assertEqual(scene.content["speech_source"], "manuscript")
        self.assertGreater(len(scene.content["speech_segments"][0]), len("这一页先看依赖注入。"))
        self.assertEqual([item["text"] for item in scene.content["highlight_targets"]], ["依赖注入", "Bean 创建流程"])
        self.assertEqual(
            [item["target_id"] for item in scene.actions[0].payload["highlight_cues"]],
            ["hl_001", "hl_002"],
        )

    def test_ppt_job_uses_llm_teaching_segments_for_longer_aligned_speech(self) -> None:
        class FakeQuizGenerator:
            def _call_llm(self, _prompt: str) -> str:
                return """
                {
                  "segments": [
                    {
                      "target_id": "hl_001",
                      "mode": "spotlight",
                      "text": "先把视线放到依赖注入这个词上。它不是一个单纯的语法点，而是在解决对象之间如何协作的问题。"
                    },
                    {
                      "target_id": "hl_002",
                      "mode": "outline",
                      "text": "接着看 Bean 创建流程。容器会先读取配置，再创建对象，最后把依赖关系装配进去。"
                    }
                  ]
                }
                """

        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = os.path.join(tmpdir, "generated_svg_ppt", "users", "user_1", "job_1")
            svg_dir = os.path.join(job_dir, "svg_final")
            os.makedirs(svg_dir)
            with open(os.path.join(job_dir, "manuscript.md"), "w", encoding="utf-8") as f:
                f.write("这一页介绍依赖注入和 Bean 创建流程。")
            with open(os.path.join(svg_dir, "slide_001.svg"), "w", encoding="utf-8") as f:
                f.write(
                    """
                    <svg viewBox="0 0 1000 562">
                      <text x="80" y="100" font-size="32">依赖注入</text>
                      <text x="120" y="210" font-size="24">Bean 创建流程</text>
                    </svg>
                    """
                )

            generator = InteractiveClassroomGenerator(
                tmpdir,
                ClassroomStorage(tmpdir),
                quiz_generator=FakeQuizGenerator(),
            )
            scenes = generator._build_slide_scenes_from_ppt_job("user_1", "job_1")

        action = scenes[0].actions[0]
        self.assertIn("对象之间如何协作", action.text)
        self.assertIn("容器会先读取配置", action.text)
        self.assertEqual(
            [item["target_id"] for item in action.payload["highlight_cues"]],
            ["hl_001", "hl_002"],
        )
        self.assertEqual(action.payload["highlight_cues"][0]["mode"], "spotlight")

    def test_ppt_job_builds_slide_scenes_serially_in_page_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = os.path.join(tmpdir, "generated_svg_ppt", "users", "user_1", "job_1")
            svg_dir = os.path.join(job_dir, "svg_final")
            os.makedirs(svg_dir)
            with open(os.path.join(job_dir, "manuscript.md"), "w", encoding="utf-8") as f:
                f.write("\n---\n".join(["第一页讲稿", "第二页讲稿", "第三页讲稿"]))
            for idx in range(1, 4):
                with open(os.path.join(svg_dir, f"slide_{idx:03d}.svg"), "w", encoding="utf-8") as f:
                    f.write(
                        f"""
                        <svg viewBox="0 0 1000 562">
                          <text x="80" y="100" font-size="32">第 {idx} 页标题</text>
                          <text x="120" y="210" font-size="24">第 {idx} 页要点</text>
                        </svg>
                        """
                    )

            generator = InteractiveClassroomGenerator(tmpdir, ClassroomStorage(tmpdir))
            starts: list[tuple[int, float]] = []

            def slow_segments(**kwargs):
                page_index = int(kwargs["page_index"])
                starts.append((page_index, time.perf_counter()))
                time.sleep(0.2)
                return [
                    {
                        "target_id": "hl_001",
                        "mode": "spotlight",
                        "text": f"第 {page_index} 页讲解内容，说明这一页的核心标题和重点。",
                    }
                ]

            generator._generate_teaching_segments = slow_segments  # type: ignore[method-assign]

            start = time.perf_counter()
            scenes = generator._build_slide_scenes_from_ppt_job("user_1", "job_1")
            elapsed = time.perf_counter() - start

        self.assertGreaterEqual(elapsed, 0.55)
        self.assertEqual([page_index for page_index, _ in starts], [1, 2, 3])
        self.assertEqual([scene.id for scene in scenes], ["scene_slide_001", "scene_slide_002", "scene_slide_003"])
        self.assertEqual([scene.actions[0].text for scene in scenes], [
            "第 1 页讲解内容，说明这一页的核心标题和重点。",
            "第 2 页讲解内容，说明这一页的核心标题和重点。",
            "第 3 页讲解内容，说明这一页的核心标题和重点。",
        ])

    def test_ppt_job_fallback_expands_short_notes_around_svg_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = os.path.join(tmpdir, "generated_svg_ppt", "users", "user_1", "job_1")
            svg_dir = os.path.join(job_dir, "svg_final")
            os.makedirs(svg_dir)
            with open(os.path.join(job_dir, "manuscript.md"), "w", encoding="utf-8") as f:
                f.write("这一页介绍计算机视觉。")
            with open(os.path.join(svg_dir, "slide_001.svg"), "w", encoding="utf-8") as f:
                f.write(
                    """
                    <svg viewBox="0 0 1000 562">
                      <text x="80" y="100" font-size="32">计算机视觉</text>
                      <text x="120" y="210" font-size="24">图像分类</text>
                      <text x="120" y="280" font-size="24">目标检测</text>
                    </svg>
                    """
                )

            generator = InteractiveClassroomGenerator(tmpdir, ClassroomStorage(tmpdir))
            scenes = generator._build_slide_scenes_from_ppt_job("user_1", "job_1")

        action = scenes[0].actions[0]
        self.assertGreater(len(action.text), 180)
        self.assertIn("图像分类", action.text)
        self.assertIn("目标检测", action.text)
        self.assertGreaterEqual(len(action.payload["highlight_cues"]), 3)


if __name__ == "__main__":
    unittest.main()
