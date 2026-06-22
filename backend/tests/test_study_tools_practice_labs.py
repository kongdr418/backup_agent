from __future__ import annotations

import os
import sys
import tempfile
import unittest

from flask import Flask


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from study_tools.storage import StudyToolsStorage
from study_tools.routes import create_study_tools_blueprint, _build_llm_lab_payload, _repair_lab_html_for_display


class StudyToolsPracticeLabsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = StudyToolsStorage(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_add_and_list_animation_lab(self) -> None:
        item = self.storage.add_lab(
            "user_1",
            {
                "type": "animation",
                "title": "梯度下降动画",
                "course": "人工智能导论",
                "topic": "梯度下降",
                "knowledge_points": ["损失函数", "学习率"],
                "summary": "观察学习率变化。",
                "content": {
                    "html": "<!doctype html><html></html>",
                    "video_prompt": "生成梯度下降教学动画",
                },
            },
        )

        result = self.storage.list_labs("user_1", lab_type="animation")

        self.assertEqual(item["id"], result["items"][0]["id"])
        self.assertEqual("animation", result["items"][0]["type"])
        self.assertEqual(["损失函数", "学习率"], result["items"][0]["knowledge_points"])
        self.assertIn("video_prompt", result["items"][0]["content"])

    def test_update_and_delete_code_lab(self) -> None:
        item = self.storage.add_lab(
            "user_1",
            {
                "type": "code",
                "title": "二分查找实操",
                "topic": "二分查找",
                "content": {
                    "html": "<!doctype html><html></html>",
                    "language": "javascript",
                    "test_cases": [{"input": "5", "expected": "2"}],
                },
            },
        )

        updated = self.storage.update_lab(
            "user_1",
            item["id"],
            {"title": "二分查找练习"},
        )
        deleted = self.storage.delete_lab("user_1", item["id"])
        result = self.storage.list_labs("user_1")

        self.assertIsNotNone(updated)
        self.assertEqual("二分查找练习", updated["title"])
        self.assertTrue(deleted)
        self.assertEqual([], result["items"])

    def test_add_flashcard_initializes_sm2_when_missing_or_null(self) -> None:
        item = self.storage.add_flashcard(
            "user_1",
            {
                "front": "凸透镜成像中，u > 2f 时像有什么特点？",
                "back": "倒立、缩小的实像。",
                "source": "mistake",
                "source_id": "mk_demo",
                "sm2": None,
            },
        )

        self.assertTrue(item["id"].startswith("fc_"))
        self.assertEqual("mistake", item["source"])
        self.assertIsInstance(item["sm2"], dict)
        self.assertEqual(0, item["sm2"]["repetitions"])
        self.assertEqual(2.5, item["sm2"]["ease_factor"])
        self.assertTrue(item["sm2"]["due_date"])

    def test_llm_animation_payload_uses_model_html(self) -> None:
        def fake_llm(messages, **kwargs):  # noqa: ANN001
            return """
            {
              "title": "二分查找动画实验",
              "summary": "用左右边界移动解释二分查找。",
              "knowledge_points": ["有序数组", "左右边界"],
              "video_prompt": "生成二分查找指针移动动画",
              "storyboard": [
                {"shot": 1, "title": "设定边界", "description": "展示 low 和 high"},
                {"shot": 2, "title": "移动指针", "description": "根据比较结果收缩区间"}
              ],
              "html": "<!doctype html><html><head><title>二分查找</title></head><body><canvas id='c'></canvas><script>let x=1;</script></body></html>"
            }
            """

        payload = _build_llm_lab_payload(
            {"type": "animation", "topic": "二分查找", "course": "算法"},
            lab_type="animation",
            llm_call=fake_llm,
            llm_config={},
            logger=_NullLogger(),
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("animation", payload["type"])
        self.assertEqual("llm", payload["content"]["generation_mode"])
        self.assertIn("二分查找", payload["content"]["html"])

    def test_llm_code_payload_uses_dynamic_tests(self) -> None:
        def fake_llm(messages, **kwargs):  # noqa: ANN001
            return """
            {
              "title": "阶乘练习",
              "summary": "实现阶乘函数。",
              "knowledge_points": ["循环", "累乘"],
              "task_description": "输入 n，返回 n 的阶乘。",
              "starter_code": "function solve(input) {\\n  const n = Number(input);\\n  return n;\\n}",
              "test_cases": [
                {"input": "3", "expected": "6", "description": "3!"},
                {"input": "5", "expected": "120", "description": "5!"},
                {"input": "1", "expected": "1", "description": "1!"}
              ],
              "hints": ["从 1 乘到 n"],
              "solution": "function solve(input) { const n = Number(input); let ans = 1; for (let i = 2; i <= n; i++) ans *= i; return ans; }"
            }
            """

        payload = _build_llm_lab_payload(
            {"type": "code", "topic": "阶乘", "course": "程序设计"},
            lab_type="code",
            llm_call=fake_llm,
            llm_config={},
            logger=_NullLogger(),
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("code", payload["type"])
        self.assertEqual("llm", payload["content"]["generation_mode"])
        self.assertEqual("120", payload["content"]["test_cases"][1]["expected"])
        self.assertIn("阶乘", payload["content"]["html"])

    def test_repairs_one_line_script_comments_from_llm_html(self) -> None:
        html = (
            "<!doctype html><html><body><canvas id='c'></canvas><script>"
            "const f = 10; // 焦距固定function draw() {ctx.clearRect(0,0,1,1);}"
            "slider.addEventListener('input', draw);draw();"
            "</script></body></html>"
        )

        repaired = _repair_lab_html_for_display(html)

        self.assertIn("/* 焦距固定 */function draw()", repaired)
        self.assertIn("slider.addEventListener", repaired)

    def test_llm_animation_payload_rejects_generic_topic_mismatch(self) -> None:
        def fake_llm(messages, **kwargs):  # noqa: ANN001
            return """
            {
              "title": "冒泡排序 动画演示",
              "summary": "观察变量变化。",
              "knowledge_points": ["变量变化"],
              "video_prompt": "生成变量曲线",
              "storyboard": [],
              "html": "<!doctype html><html><body><canvas id='c' width='1200' height='720'></canvas><label>变量强度</label><script>let x=1;</script></body></html>"
            }
            """

        payload = _build_llm_lab_payload(
            {"type": "animation", "topic": "冒泡排序", "course": "算法"},
            lab_type="animation",
            llm_call=fake_llm,
            llm_config={},
            logger=_NullLogger(),
        )

        self.assertIsNone(payload)

    def test_llm_animation_payload_accepts_raw_topic_html(self) -> None:
        def fake_llm(messages, **kwargs):  # noqa: ANN001
            return """
            <!doctype html>
            <html><body>
              <canvas id="stage" width="1200" height="720"></canvas>
              <button>播放比较</button>
              <script>
                const steps = ['数组元素', '比较相邻元素', '交换', '已排序区'];
              </script>
            </body></html>
            """

        payload = _build_llm_lab_payload(
            {"type": "animation", "topic": "冒泡排序", "course": "算法"},
            lab_type="animation",
            llm_call=fake_llm,
            llm_config={},
            logger=_NullLogger(),
        )

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("llm", payload["content"]["generation_mode"])
        self.assertIn("比较相邻元素", payload["content"]["html"])

    def test_animation_route_does_not_save_invalid_fallback(self) -> None:
        def fake_llm(messages, **kwargs):  # noqa: ANN001
            return "not json"

        app = Flask(__name__)
        app.register_blueprint(create_study_tools_blueprint(
            get_user_id=lambda: "user_1",
            get_storage=lambda: self.storage,
            logger=_NullLogger(),
            llm_call=fake_llm,
        ))
        resp = app.test_client().post(
            "/api/study-tools/practice-labs",
            json={"type": "animation", "topic": "凸透镜成像", "course": "物理"},
        )

        self.assertEqual(502, resp.status_code)
        self.assertEqual("ANIMATION_GENERATION_INVALID", resp.get_json()["error"])
        self.assertEqual(0, self.storage.list_labs("user_1")["total"])


class _NullLogger:
    def warning(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


if __name__ == "__main__":
    unittest.main()
