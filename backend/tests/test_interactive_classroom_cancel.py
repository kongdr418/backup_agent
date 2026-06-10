from __future__ import annotations

import os
import sys
import unittest


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import app as backend_app


class InteractiveClassroomCancelRegistryTest(unittest.TestCase):
    def tearDown(self) -> None:
        with backend_app.CLASSROOM_GENERATION_CANCELS_LOCK:
            backend_app.CLASSROOM_GENERATION_CANCELS.clear()
            backend_app.CLASSROOM_GENERATION_JOBS.clear()
        for request_id in (
            "job-1",
            "job-2",
            "job-progress",
            "job-replay",
            "job-disk",
        ):
            path = backend_app._classroom_generation_job_path(request_id)  # noqa: SLF001
            if path and os.path.exists(path):
                os.remove(path)

    def test_cancel_unknown_request_id_does_not_leave_registry_entry(self) -> None:
        cancelled = backend_app._cancel_classroom_generation("missing-request")  # noqa: SLF001

        self.assertFalse(cancelled)
        with backend_app.CLASSROOM_GENERATION_CANCELS_LOCK:
            self.assertNotIn("missing-request", backend_app.CLASSROOM_GENERATION_CANCELS)

    def test_cancel_registered_request_marks_event(self) -> None:
        event = backend_app._register_classroom_generation("active-request")  # noqa: SLF001

        cancelled = backend_app._cancel_classroom_generation("active-request")  # noqa: SLF001

        self.assertTrue(cancelled)
        self.assertTrue(event.is_set())

    def test_job_status_survives_after_generation_finishes(self) -> None:
        backend_app._mark_classroom_generation_running("job-1", "Python 入门")  # noqa: SLF001
        backend_app._mark_classroom_generation_done("job-1", "cls_001", {"id": "cls_001"})  # noqa: SLF001

        job = backend_app._get_classroom_generation_job("job-1")  # noqa: SLF001

        self.assertEqual("done", job["status"])
        self.assertEqual("cls_001", job["classroom_id"])
        self.assertEqual({"id": "cls_001"}, job["classroom"])

    def test_cancel_marks_running_job_as_cancelling_without_removing_status(self) -> None:
        backend_app._mark_classroom_generation_running("job-2", "Python 入门")  # noqa: SLF001
        backend_app._register_classroom_generation("job-2")  # noqa: SLF001

        cancelled = backend_app._cancel_classroom_generation("job-2")  # noqa: SLF001
        job = backend_app._get_classroom_generation_job("job-2")  # noqa: SLF001

        self.assertTrue(cancelled)
        self.assertEqual("cancelling", job["status"])

    def test_progress_event_updates_generation_job_snapshot(self) -> None:
        backend_app._mark_classroom_generation_running("job-progress", "Python 入门")  # noqa: SLF001

        backend_app._classroom_emit(  # noqa: SLF001
            "job-progress",
            {
                "type": "classroom_progress",
                "stage": "build_scenes",
                "stage_label": "组织课堂",
                "stage_index": 1,
                "stage_total": 5,
                "scene_index": 3,
                "scene_total": 10,
                "scene": {
                    "id": "scene_slide_003",
                    "type": "slide",
                    "title": "第三页",
                    "order": 3,
                },
            },
        )

        job = backend_app._get_classroom_generation_job("job-progress")  # noqa: SLF001

        self.assertEqual("running", job["status"])
        self.assertEqual("build_scenes", job["stage"])
        self.assertEqual("组织课堂", job["stage_label"])
        self.assertEqual(3, job["scenes_generated"])
        self.assertEqual(10, job["total_scenes"])
        self.assertEqual("scene_slide_003", job["last_scene"]["id"])
        self.assertIsInstance(job["elapsed_seconds"], int)

    def test_running_job_replays_recorded_progress_events_to_new_subscribers(self) -> None:
        backend_app._mark_classroom_generation_running("job-replay", "Python 入门")  # noqa: SLF001
        event = {
            "type": "classroom_progress",
            "stage": "insert_quizzes",
            "stage_label": "生成互动",
            "stage_index": 2,
            "stage_total": 5,
            "scene_index": 1,
            "scene_total": 2,
        }

        backend_app._classroom_emit("job-replay", event)  # noqa: SLF001

        replayed = backend_app._get_classroom_generation_progress_events("job-replay")  # noqa: SLF001
        self.assertEqual([event], replayed)

    def test_job_status_can_be_reloaded_from_disk_when_memory_is_empty(self) -> None:
        backend_app._mark_classroom_generation_running("job-disk", "Python 入门")  # noqa: SLF001
        backend_app._mark_classroom_generation_done("job-disk", "cls_disk", {"id": "cls_disk", "scenes": []})  # noqa: SLF001

        with backend_app.CLASSROOM_GENERATION_CANCELS_LOCK:
            backend_app.CLASSROOM_GENERATION_JOBS.clear()

        job = backend_app._get_classroom_generation_job("job-disk")  # noqa: SLF001

        self.assertEqual("done", job["status"])
        self.assertEqual("cls_disk", job["classroom_id"])


if __name__ == "__main__":
    unittest.main()
