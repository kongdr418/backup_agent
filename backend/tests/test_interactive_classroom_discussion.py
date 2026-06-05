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

    def test_build_discussion_messages_include_course_outline_and_current_page(self) -> None:
        from interactive_classroom.discussion_service import build_discussion_messages

        messages = build_discussion_messages(
            _classroom_payload(),
            ["scene_slide_001", "scene_quiz_001"],
            [{"role": "user", "content": "这页讲了什么"}],
            trigger="manual",
            current_scene_id="scene_quiz_001",
        )

        prompt = messages[1]["content"]
        self.assertIn("当前位于第 2 / 3 页", prompt)
        self.assertIn("当前页面标题：随堂测验", prompt)
        self.assertIn("整堂课页码与讲稿摘要", prompt)
        self.assertIn("第1页｜slide｜while 循环", prompt)
        self.assertIn("第2页｜quiz｜随堂测验", prompt)
        self.assertIn("先理解 while 的判断顺序", prompt)

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
        self.assertIn("默认就是在问当前页，不要先反问他哪里不会", system_prompt)
        self.assertIn("第一句先点明当前页在讲什么", system_prompt)
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


if __name__ == "__main__":
    unittest.main()
