from __future__ import annotations

import os
import sys
import tempfile
import unittest


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import app as backend_app
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
        backend_app.LEARNER_PROFILE_STORAGE = self.storage
        self.client = backend_app.app.test_client()

    def tearDown(self) -> None:
        backend_app.LEARNER_PROFILE_STORAGE = self.original_storage
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
        self.assertEqual(1, payload["profile"]["profile_version"])

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


if __name__ == "__main__":
    unittest.main()
