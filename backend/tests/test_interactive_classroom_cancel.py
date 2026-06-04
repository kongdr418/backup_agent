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


if __name__ == "__main__":
    unittest.main()
