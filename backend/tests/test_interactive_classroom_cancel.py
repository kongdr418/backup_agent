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
        service = backend_app.CLASSROOM_GENERATION_JOB_SERVICE
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
            path = service._job_path(request_id)  # noqa: SLF001
            if path and os.path.exists(path):
                os.remove(path)

    def test_cancel_unknown_request_id_does_not_leave_registry_entry(self) -> None:
        cancelled = backend_app.CLASSROOM_GENERATION_JOB_SERVICE.cancel("missing-request")

        self.assertFalse(cancelled)
        with backend_app.CLASSROOM_GENERATION_CANCELS_LOCK:
            self.assertNotIn("missing-request", backend_app.CLASSROOM_GENERATION_CANCELS)

    def test_cancel_registered_request_marks_event(self) -> None:
        service = backend_app.CLASSROOM_GENERATION_JOB_SERVICE
        event = service.register("active-request")

        cancelled = service.cancel("active-request")

        self.assertTrue(cancelled)
        self.assertTrue(event.is_set())

    def test_job_status_survives_after_generation_finishes(self) -> None:
        service = backend_app.CLASSROOM_GENERATION_JOB_SERVICE
        service.mark_running("job-1", "Python 入门")
        service.mark_done("job-1", "cls_001", {"id": "cls_001"})

        job = service.get_job("job-1")

        self.assertEqual("done", job["status"])
        self.assertEqual("cls_001", job["classroom_id"])
        self.assertEqual({"id": "cls_001"}, job["classroom"])

    def test_cancel_marks_running_job_as_cancelling_without_removing_status(self) -> None:
        service = backend_app.CLASSROOM_GENERATION_JOB_SERVICE
        service.mark_running("job-2", "Python 入门")
        service.register("job-2")

        cancelled = service.cancel("job-2")
        job = service.get_job("job-2")

        self.assertTrue(cancelled)
        self.assertEqual("cancelling", job["status"])

    def test_progress_event_updates_generation_job_snapshot(self) -> None:
        service = backend_app.CLASSROOM_GENERATION_JOB_SERVICE
        service.mark_running("job-progress", "Python 入门")

        service.emit(
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

        job = service.get_job("job-progress")

        self.assertEqual("running", job["status"])
        self.assertEqual("build_scenes", job["stage"])
        self.assertEqual("组织课堂", job["stage_label"])
        self.assertEqual(3, job["scenes_generated"])
        self.assertEqual(10, job["total_scenes"])
        self.assertEqual("scene_slide_003", job["last_scene"]["id"])
        self.assertIsInstance(job["elapsed_seconds"], int)

    def test_running_job_replays_recorded_progress_events_to_new_subscribers(self) -> None:
        service = backend_app.CLASSROOM_GENERATION_JOB_SERVICE
        service.mark_running("job-replay", "Python 入门")
        event = {
            "type": "classroom_progress",
            "stage": "insert_quizzes",
            "stage_label": "生成互动",
            "stage_index": 2,
            "stage_total": 5,
            "scene_index": 1,
            "scene_total": 2,
        }

        service.emit("job-replay", event)

        replayed = service.get_progress_events("job-replay")
        self.assertEqual([event], replayed)

    def test_job_status_can_be_reloaded_from_disk_when_memory_is_empty(self) -> None:
        service = backend_app.CLASSROOM_GENERATION_JOB_SERVICE
        service.mark_running("job-disk", "Python 入门")
        service.mark_done("job-disk", "cls_disk", {"id": "cls_disk", "scenes": []})

        with backend_app.CLASSROOM_GENERATION_CANCELS_LOCK:
            backend_app.CLASSROOM_GENERATION_JOBS.clear()

        job = service.get_job("job-disk")

        self.assertEqual("done", job["status"])
        self.assertEqual("cls_disk", job["classroom_id"])


if __name__ == "__main__":
    unittest.main()
