from __future__ import annotations

import os
import sys
import tempfile
import unittest


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from learner_profile.storage import LearnerProfileStorage


class LearnerProfileStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = LearnerProfileStorage(
            self.tempdir.name,
            now_provider=lambda: "2026-06-08T10:00:00",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_missing_profile_returns_versioned_default(self) -> None:
        profile = self.storage.load_profile("user_1")

        self.assertEqual(1, profile["profile_version"])
        self.assertEqual("user_1", profile["user_id"])
        self.assertEqual("", profile["basic"]["learning_basis"])
        self.assertEqual([], profile["preferences"]["content_style"])
        self.assertEqual({}, profile["courses"])
        self.assertEqual([], profile["pending_updates"])

    def test_save_migrates_legacy_four_field_profile(self) -> None:
        saved = self.storage.save_profile(
            "user_1",
            {
                "basis": "零基础",
                "goal": "考试通过",
                "style": "图解+案例",
                "difficulty": "基础",
            },
        )

        self.assertEqual("零基础", saved["basic"]["learning_basis"])
        self.assertEqual("考试通过", saved["preferences"]["goal"])
        self.assertEqual(["图解", "案例"], saved["preferences"]["content_style"])
        self.assertEqual("基础", saved["preferences"]["preferred_difficulty"])
        self.assertEqual(saved, self.storage.load_profile("user_1"))

    def test_save_normalizes_supported_fields_and_preserves_created_at(self) -> None:
        first = self.storage.save_profile(
            "user_1",
            {
                "basic": {
                    "display_name": "  小明  ",
                    "learning_stage": " 大二 ",
                    "learning_basis": " 有基础 ",
                    "background": " 软件工程 ",
                    "ignored": "value",
                },
                "preferences": {
                    "goal": " 项目实战 ",
                    "content_style": [" 图解 ", "", "案例", "图解"],
                    "preferred_difficulty": " 中等 ",
                    "tutoring_style": " 引导式 ",
                },
                "courses": {"course_python": {"course_name": "Python"}},
            },
        )
        second = self.storage.save_profile(
            "user_1",
            {
                **first,
                "basic": {**first["basic"], "display_name": "小红"},
            },
        )

        self.assertEqual("小红", second["basic"]["display_name"])
        self.assertEqual(["图解", "案例"], first["preferences"]["content_style"])
        self.assertNotIn("ignored", first["basic"])
        self.assertEqual("2026-06-08T10:00:00", second["created_at"])
        self.assertEqual({"course_python": {"course_name": "Python"}}, second["courses"])

    def test_profiles_are_isolated_by_user(self) -> None:
        self.storage.save_profile("user_1", {"goal": "考试通过"})
        self.storage.save_profile("user_2", {"goal": "项目实战"})

        self.assertEqual("考试通过", self.storage.load_profile("user_1")["preferences"]["goal"])
        self.assertEqual("项目实战", self.storage.load_profile("user_2")["preferences"]["goal"])

    def test_loading_profile_does_not_change_updated_at(self) -> None:
        timestamps = iter(["2026-06-08T10:00:00", "2026-06-08T11:00:00"])
        storage = LearnerProfileStorage(
            self.tempdir.name,
            now_provider=lambda: next(timestamps),
        )
        saved = storage.save_profile("user_1", {"goal": "考试通过"})
        loaded = storage.load_profile("user_1")

        self.assertEqual(saved["updated_at"], loaded["updated_at"])


if __name__ == "__main__":
    unittest.main()
