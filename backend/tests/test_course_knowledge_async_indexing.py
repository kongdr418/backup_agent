from __future__ import annotations

import os
import sys
import tempfile
import threading
import time


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from course_knowledge.ingest import CourseKnowledgeIngestor
from course_knowledge.storage import CourseKnowledgeStorage
from course_knowledge.vector_index import CourseVectorIndex


def test_course_index_rebuild_schedules_vector_index_without_blocking_upload_path():
    started = threading.Event()
    release = threading.Event()

    class SlowVectorIndex:
        def rebuild(self, user_id, course_id, chunks):
            started.set()
            release.wait(timeout=5)
            return {}

        def delete(self, user_id, course_id):
            return True

    with tempfile.TemporaryDirectory() as tempdir:
        storage = CourseKnowledgeStorage(tempdir, now_provider=lambda: "2026-06-15T11:00:00")
        storage.save_document(
            "user1",
            "doc1",
            {
                "document_id": "doc1",
                "user_id": "user1",
                "course_id": "course_test",
                "title": "课程大纲",
                "doc_kind": "syllabus",
                "original_filename": "outline.docx",
                "updated_at": "2026-06-15T11:00:00",
            },
            {
                "course_id": "course_test",
                "course_name": "测试课程",
                "summary": "测试简介",
                "modules": [{"module_id": "mod1", "title": "模块一"}],
                "lessons": [
                    {
                        "lesson_id": "lesson1",
                        "title": "第一课",
                        "knowledge_points": ["知识点A"],
                    }
                ],
                "knowledge_points": ["知识点A"],
            },
        )
        ingestor = CourseKnowledgeIngestor(
            tempdir,
            storage=storage,
            now_provider=lambda: "2026-06-15T11:00:00",
            vector_index=SlowVectorIndex(),
        )

        started_at = time.perf_counter()
        result = ingestor._rebuild_course_indexes("user1", "course_test")
        elapsed = time.perf_counter() - started_at

        assert result["course_map"]["course_id"] == "course_test"
        assert result["chunks"]
        assert elapsed < 0.5
        assert started.wait(timeout=1)
        release.set()


def test_vector_query_scores_skip_missing_index_instead_of_rebuilding_synchronously():
    class MissingIndexStorage:
        def load_vector_index(self, user_id, course_id):
            return None

    class FailingEmbeddingService:
        model_name = "test-model"

        def encode_documents(self, texts):
            raise AssertionError("query_scores should not rebuild missing indexes")

        def encode_query(self, topic):
            raise AssertionError("query_scores should not encode query without an index")

    index = CourseVectorIndex(
        storage=MissingIndexStorage(),
        embedding_service=FailingEmbeddingService(),
    )

    scores = index.query_scores(
        "user1",
        "course_test",
        [{"chunk_id": "chunk1", "section": "第一课", "text": "知识点A", "keywords": []}],
        "知识点A",
    )

    assert scores == {}
