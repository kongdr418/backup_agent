from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import app as backend_app
from interactive_classroom.storage import ClassroomStorage


def _classroom_payload() -> dict:
    return {
        "id": "classroom_discuss_001",
        "user_id": "user_1",
        "title": "Python 循环课堂",
        "topic": "Python 循环",
        "course": "Python 程序设计",
        "status": "ready",
        "created_at": "2026-06-05T10:00:00",
        "updated_at": "2026-06-05T10:00:00",
        "tts": {},
        "student_profile": {},
        "source": {},
        "agents": [],
        "knowledge_points": ["while 循环", "for 循环"],
        "scenes": [
            {
                "id": "scene_slide_001",
                "type": "slide",
                "title": "while 循环",
                "order": 1,
                "knowledge_points": ["while 循环"],
                "content": {
                    "extracted_text": ["循环条件", "循环体", "先判断再执行"],
                    "markdown": "while 会先判断条件，再决定是否进入循环体。",
                },
                "actions": [
                    {
                        "id": "speech_001",
                        "type": "speech",
                        "agent_id": "teacher",
                        "text": "先理解 while 的判断顺序，再看循环体执行。",
                        "audio_url": "",
                    }
                ],
            },
            {
                "id": "scene_quiz_001",
                "type": "quiz",
                "title": "随堂测验",
                "order": 2,
                "knowledge_points": ["while 循环"],
                "content": {
                    "questions": [
                        {
                            "id": "q1",
                            "type": "single",
                            "question": "while 循环执行前会先判断什么？",
                            "options": [
                                {"label": "循环条件", "value": "A"},
                                {"label": "变量名长度", "value": "B"},
                            ],
                            "answer": ["A"],
                            "analysis": "while 会先判断循环条件。",
                        }
                    ]
                },
                "actions": [],
            },
            {
                "id": "scene_slide_002",
                "type": "slide",
                "title": "for 循环",
                "order": 3,
                "knowledge_points": ["for 循环"],
                "content": {
                    "extracted_text": ["遍历序列", "次数明确"],
                },
                "actions": [],
            },
        ],
    }


class InteractiveClassroomDiscussionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = ClassroomStorage(self.tempdir.name)
        self.original_storage = backend_app.CLASSROOM_STORAGE
        backend_app.CLASSROOM_STORAGE = self.storage
        self.storage.save_classroom("user_1", "classroom_discuss_001", _classroom_payload())
        self.client = backend_app.app.test_client()

    def tearDown(self) -> None:
        backend_app.CLASSROOM_STORAGE = self.original_storage
        self.tempdir.cleanup()

    def test_build_discussion_context_uses_only_played_scene_text(self) -> None:
        from interactive_classroom.discussion_service import build_discussion_context

        text = build_discussion_context(
            _classroom_payload(),
            ["scene_slide_001", "scene_quiz_001"],
        )

        self.assertIn("while 循环", text)
        self.assertIn("循环条件", text)
        self.assertIn("先理解 while 的判断顺序", text)
        self.assertIn("while 循环执行前会先判断什么", text)
        self.assertNotIn("for 循环", text)

    def test_build_discussion_messages_keep_current_page_only(self) -> None:
        from interactive_classroom.discussion_service import build_discussion_messages

        messages = build_discussion_messages(
            _classroom_payload(),
            ["scene_slide_001", "scene_quiz_001"],
            [{"role": "user", "content": "这页讲了什么"}],
            trigger="manual",
            current_scene_id="scene_quiz_001",
        )

        prompt = messages[1]["content"]
        # current_position + focus_context 必须在
        self.assertIn("当前位于第 2 / 3 页", prompt)
        self.assertIn("当前页面标题：随堂测验", prompt)
        # 大纲不再发（任何场景都只发当前页）
        self.assertNotIn("整堂课页码与讲稿摘要", prompt)
        self.assertNotIn("第1页｜slide｜while 循环", prompt)
        self.assertNotIn("第2页｜quiz｜随堂测验", prompt)
        # 全量 played context 也不发
        self.assertNotIn("以下是本堂课已经播放过的课堂文本上下文", prompt)
        # current page 焦点内容仍在（scene_quiz_001 的题面 + 解析）
        self.assertIn("while 循环执行前会先判断什么", prompt)
        self.assertIn("while 会先判断循环条件", prompt)
        # scene_slide_001 的内容不应出现（不是 current page）
        self.assertNotIn("先理解 while 的判断顺序", prompt)

    def test_build_discussion_messages_include_page_grounding_constraints(self) -> None:
        from interactive_classroom.discussion_service import build_discussion_messages

        messages = build_discussion_messages(
            _classroom_payload(),
            ["scene_slide_001"],
            [{"role": "user", "content": "能详细解释一下这一页吗"}],
            trigger="manual",
            current_scene_id="scene_slide_001",
        )

        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]
        self.assertIn("默认就是在问当前页，直接讲解，不要先反问", system_prompt)
        self.assertIn("第一句点明当前页在讲什么", system_prompt)
        self.assertIn("一律解释当前页，不要让学生再澄清", user_prompt)
        self.assertIn("不要输出“你是想问概念还是顺序吗”这种脱离页面的泛化追问", user_prompt)

    def test_discussion_route_returns_assistant_message(self) -> None:
        with patch(
            "interactive_classroom.discussion_service.content_llm_call",
            return_value="你先别急着找答案。先说说 while 在执行前先看什么？",
        ):
            resp = self.client.post(
                "/api/interactive-classroom/classroom_discuss_001/discuss",
                json={
                    "user_id": "user_1",
                    "played_scene_ids": ["scene_slide_001"],
                    "messages": [{"role": "user", "content": "这页是什么意思？"}],
                    "trigger": "manual",
                },
            )

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual("assistant", payload["assistant_message"]["role"])
        self.assertIn("while", payload["assistant_message"]["content"])
        self.assertTrue(payload["auto_advance_paused"])

    def test_multi_agent_discussion_generates_fixed_three_turns(self) -> None:
        from interactive_classroom.discussion_service import generate_multi_agent_discussion_turns

        with patch(
            "interactive_classroom.discussion_service.content_llm_call",
            side_effect=[
                "while 循环会先判断条件，再决定是否执行循环体。",
                "如果条件一开始就是 False，那循环体是不是一次都不会执行？",
                "是的，条件一开始为 False 时，while 循环体不会执行。",
            ],
        ):
            turns = generate_multi_agent_discussion_turns(
                classroom=_classroom_payload(),
                played_scene_ids=["scene_slide_001"],
                conversation=[{"role": "user", "content": "这页是什么意思？"}],
                trigger="manual",
                current_scene_id="scene_slide_001",
            )

        self.assertEqual([turn["agent_id"] for turn in turns], ["teacher", "student_peer", "teacher"])
        self.assertEqual([turn["agent_name"] for turn in turns], ["AI 教师", "AI 同学", "AI 教师"])
        self.assertIn("判断条件", turns[0]["content"])
        self.assertIn("False", turns[1]["content"])
        self.assertIn("不会执行", turns[2]["content"])

    def test_multi_agent_final_teacher_prompt_targets_student_peer_question(self) -> None:
        from interactive_classroom.discussion_service import MULTI_AGENT_DISCUSSION_TURNS, build_multi_agent_turn_messages

        messages = build_multi_agent_turn_messages(
            classroom=_classroom_payload(),
            played_scene_ids=["scene_slide_001"],
            conversation=[{"role": "user", "content": "计算机视觉有什么用？"}],
            trigger="manual",
            turn=MULTI_AGENT_DISCUSSION_TURNS[2],
            previous_turns=[
                {
                    "role": "assistant",
                    "agent_id": "teacher",
                    "agent_name": "AI 教师",
                    "content": "计算机视觉可以帮助系统理解图像和视频。",
                },
                {
                    "role": "assistant",
                    "agent_id": "student_peer",
                    "agent_name": "AI 同学",
                    "content": "自动驾驶具体是怎么用到计算机视觉的呢？",
                },
            ],
            current_scene_id="scene_slide_001",
        )

        final_instruction = messages[-1]["content"]
        self.assertIn("请直接回答 AI 同学刚才的追问", final_instruction)
        self.assertIn("自动驾驶具体是怎么用到计算机视觉的呢", final_instruction)
        self.assertNotEqual(messages[-1]["content"], "计算机视觉有什么用？")

    def test_discussion_stream_multi_agent_emits_agent_events(self) -> None:
        with patch(
            "interactive_classroom.discussion_service.content_llm_call_stream",
            side_effect=[
                iter(["教师回答"]),
                iter(["同学追问"]),
                iter(["教师收束"]),
            ],
        ):
            resp = self.client.post(
                "/api/interactive-classroom/classroom_discuss_001/discuss/stream",
                json={
                    "user_id": "user_1",
                    "played_scene_ids": ["scene_slide_001"],
                    "current_scene_id": "scene_slide_001",
                    "messages": [{"role": "user", "content": "这页是什么意思？"}],
                    "trigger": "manual",
                    "multi_agent": True,
                },
            )
            text = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('"type": "agent_start"', text)
        self.assertIn('"type": "agent_chunk"', text)
        self.assertIn('"type": "agent_done"', text)
        self.assertIn('"agent_id": "teacher"', text)
        self.assertIn('"agent_id": "student_peer"', text)
        self.assertIn('"chunk": "同学追问"', text)

    def test_discussion_route_rejects_missing_messages(self) -> None:
        resp = self.client.post(
            "/api/interactive-classroom/classroom_discuss_001/discuss",
            json={
                "user_id": "user_1",
                "played_scene_ids": ["scene_slide_001"],
                "messages": [],
                "trigger": "manual",
            },
        )

        self.assertEqual(resp.status_code, 400)
        payload = resp.get_json()
        self.assertFalse(payload["success"])

    def test_fallback_reply_uses_current_scene_context_instead_of_hardcoded_example(self) -> None:
        from interactive_classroom.discussion_service import generate_discussion_reply

        classroom = {
            **_classroom_payload(),
            "topic": "前后端交互流程",
            "title": "网上购物案例",
            "scenes": [
                {
                    "id": "scene_slide_shop",
                    "type": "slide",
                    "title": "网上购物案例：前后端交互流程",
                    "order": 1,
                    "knowledge_points": ["浏览器", "服务器", "请求响应"],
                    "content": {
                        "extracted_text": ["浏览器发送请求", "服务器返回数据", "前后端通过 HTTP 交互"],
                    },
                    "actions": [
                        {
                            "id": "speech_001",
                            "type": "speech",
                            "agent_id": "teacher",
                            "text": "这一页重点是浏览器和服务器如何来回交互。",
                            "audio_url": "",
                        }
                    ],
                }
            ],
        }

        with patch(
            "interactive_classroom.discussion_service.content_llm_call",
            side_effect=RuntimeError("llm unavailable"),
        ):
            reply = generate_discussion_reply(
                classroom=classroom,
                played_scene_ids=["scene_slide_shop"],
                conversation=[{"role": "user", "content": "换个例子"}],
                trigger="manual",
                quick_action="换个例子",
                current_scene_id="scene_slide_shop",
            )

        self.assertIn("浏览器", reply)
        self.assertNotIn("while", reply)

    # --- 多页上下文分级优化测试 ---

    def _large_classroom_payload(self, total: int = 30) -> dict:
        """构造一个有 total 页的课堂，每页含足量文本以触发分级。"""
        scenes = []
        for i in range(1, total + 1):
            speech = f"第{i}页讲稿：这是第{i}页的核心讲解内容，"
            speech += "它涉及到多个关键概念" + ("。后续是大量展开内容。" * 6)
            scenes.append({
                "id": f"scene_slide_{i:03d}",
                "type": "slide",
                "title": f"第{i}页标题：核心概念 {i}",
                "order": i,
                "knowledge_points": [f"知识点{i}a", f"知识点{i}b", f"知识点{i}c"],
                "content": {
                    "extracted_text": [f"文本{i}-{j}" for j in range(1, 7)],
                    "markdown": f"这是第{i}页的 markdown 摘要，内容很丰富。" * 4,
                },
                "actions": [
                    {
                        "id": f"speech_{i:03d}",
                        "type": "speech",
                        "agent_id": "teacher",
                        "text": speech,
                        "audio_url": "",
                    }
                ],
            })
        return {
            "id": "classroom_large",
            "user_id": "user_1",
            "title": "大型课堂测试",
            "topic": "大型课堂",
            "course": "性能测试",
            "status": "ready",
            "created_at": "2026-06-05T10:00:00",
            "updated_at": "2026-06-05T10:00:00",
            "tts": {},
            "student_profile": {},
            "source": {},
            "agents": [],
            "knowledge_points": [],
            "scenes": scenes,
        }

    def test_classify_context_level_for_various_triggers_and_page_counts(self) -> None:
        from interactive_classroom.discussion_service import _classify_context_level

        # 当前所有场景一律 level 0
        self.assertEqual(_classify_context_level("manual", 1), 0)
        self.assertEqual(_classify_context_level("manual", 6), 0)
        self.assertEqual(_classify_context_level("manual", 100), 0)
        self.assertEqual(_classify_context_level("wrong_answer", 30), 0)
        self.assertEqual(_classify_context_level("key_scene", 50), 0)
        self.assertEqual(_classify_context_level("long_dwell", 100), 0)

    def test_per_scene_budget_scales_with_page_count(self) -> None:
        from interactive_classroom.discussion_service import _per_scene_budget

        # ≤ 6 页：1000 字符/页
        self.assertEqual(_per_scene_budget(1), 1000)
        self.assertEqual(_per_scene_budget(6), 1000)
        # > 6 页：fallback budget（仅 build_discussion_context 在 level=2 之外不再调用，保留作 fallback）
        self.assertEqual(_per_scene_budget(7), 400)
        self.assertEqual(_per_scene_budget(50), 400)

    def test_compact_outline_lists_all_pages_for_small_classroom(self) -> None:
        from interactive_classroom.discussion_service import build_compact_outline

        classroom = self._large_classroom_payload(total=5)
        text = build_compact_outline(classroom, current_scene_id="scene_slide_003")
        # 5 页 ≤ 6：所有页都出现
        for i in range(1, 6):
            self.assertIn(f"第{i}页", text)

    def test_compact_outline_uses_window_for_large_classroom(self) -> None:
        from interactive_classroom.discussion_service import build_compact_outline

        classroom = self._large_classroom_payload(total=30)
        text = build_compact_outline(classroom, current_scene_id="scene_slide_010", window=2)

        # 必须出现：第 1、最后 1、当前 ± 2 = 第 8/9/10/11/12 页
        for required_page in (1, 8, 9, 10, 11, 12, 30):
            self.assertIn(f"第{required_page}页", text)

        # 不能出现：远端页（如第 15、20、25）
        for omitted_page in (15, 20, 25):
            self.assertNotIn(f"第{omitted_page}页", text)

        # 表头必须说明"中间页省略"
        self.assertIn("中间页省略", text)

    def test_discussion_messages_large_classroom_manual_keeps_size_under_budget(self) -> None:
        from interactive_classroom.discussion_service import build_discussion_messages

        classroom = self._large_classroom_payload(total=30)
        messages = build_discussion_messages(
            classroom=classroom,
            played_scene_ids=[f"scene_slide_{i:03d}" for i in range(1, 31)],
            conversation=[{"role": "user", "content": "你好"}],
            trigger="manual",
            current_scene_id="scene_slide_010",
        )

        user_prompt = messages[1]["content"]
        # 30 页 + manual 走 level 0：没有大纲、没有全量 context
        # prompt 必须明显比旧版（12000+ 字符）小
        self.assertLess(len(user_prompt), 2500, f"prompt 仍过大：{len(user_prompt)} 字符")
        # current page 焦点必须保留（这是命脉）
        self.assertIn("第10页标题：核心概念 10", user_prompt)
        # current page 的核心讲解（被 _compact_scene_text 保留在 focus_context 中）必须出现
        self.assertIn("第10页讲稿", user_prompt)
        # 远端页（如第 15 页）不应该以整页形式出现
        self.assertNotIn("第15页讲稿", user_prompt)
        self.assertNotIn("第20页讲稿", user_prompt)

    def test_discussion_messages_wrong_answer_skips_outline_and_context(self) -> None:
        from interactive_classroom.discussion_service import build_discussion_messages

        classroom = self._large_classroom_payload(total=10)
        messages = build_discussion_messages(
            classroom=classroom,
            played_scene_ids=[f"scene_slide_{i:03d}" for i in range(1, 11)],
            conversation=[{"role": "user", "content": "那正确答案是什么？"}],
            trigger="wrong_answer",
            current_scene_id="scene_slide_005",
        )

        user_prompt = messages[1]["content"]
        # wrong_answer 永远 level 0：无 outline、无全量 context
        self.assertNotIn("整堂课页码与讲稿摘要", user_prompt)
        self.assertNotIn("以下是本堂课已经播放过的课堂文本上下文", user_prompt)
        # current page 仍然在
        self.assertIn("第5页标题：核心概念 5", user_prompt)
        # 触发方式提示在
        self.assertIn("学生答错题后追问", user_prompt)

    def test_discussion_messages_small_classroom_keeps_current_page_only(self) -> None:
        from interactive_classroom.discussion_service import build_discussion_messages

        # 3 页 → 仍 level 0：只发当前页
        classroom = self._large_classroom_payload(total=3)
        messages = build_discussion_messages(
            classroom=classroom,
            played_scene_ids=[f"scene_slide_{i:03d}" for i in range(1, 4)],
            conversation=[{"role": "user", "content": "这页什么意思？"}],
            trigger="manual",
            current_scene_id="scene_slide_002",
        )

        user_prompt = messages[1]["content"]
        # 小课堂也不发大纲/全量 context
        self.assertNotIn("整堂课页码与讲稿摘要", user_prompt)
        self.assertNotIn("以下是本堂课已经播放过的课堂文本上下文", user_prompt)
        # current page 焦点保留
        self.assertIn("第2页标题：核心概念 2", user_prompt)
        # 远端页不应出现
        self.assertNotIn("第1页标题：核心概念 1", user_prompt)
        self.assertNotIn("第3页标题：核心概念 3", user_prompt)

    def test_discussion_messages_medium_classroom_keeps_current_page_only(self) -> None:
        from interactive_classroom.discussion_service import build_discussion_messages

        # 10 页 → level 0：只要当前页，没有 outline、没有全量 context
        classroom = self._large_classroom_payload(total=10)
        messages = build_discussion_messages(
            classroom=classroom,
            played_scene_ids=[f"scene_slide_{i:03d}" for i in range(1, 11)],
            conversation=[{"role": "user", "content": "帮我举几个例子"}],
            trigger="manual",
            current_scene_id="scene_slide_005",
        )

        user_prompt = messages[1]["content"]
        # 不应出现大纲或全量 context（10 页 > 6 → 砍掉）
        self.assertNotIn("整堂课页码与讲稿摘要", user_prompt)
        self.assertNotIn("以下是本堂课已经播放过的课堂文本上下文", user_prompt)
        # current page 焦点保留
        self.assertIn("第5页标题：核心概念 5", user_prompt)
        # 远端页不应出现
        self.assertNotIn("第10页标题", user_prompt)

    def test_compact_scene_text_respects_budget(self) -> None:
        from interactive_classroom.discussion_service import _compact_scene_text

        scene = self._large_classroom_payload(total=1)["scenes"][0]
        block = _compact_scene_text(scene, max_chars=200)
        # 必须被截到预算内
        self.assertLessEqual(len(block), 200)
        # 关键字段仍在
        self.assertIn("第1页标题：核心概念 1", block)


if __name__ == "__main__":
    unittest.main()
