from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, request


def create_course_knowledge_blueprint(
    *,
    get_user_id: Callable[[], str],
    get_ingestor: Callable[[], Any],
    logger: Any,
) -> Blueprint:
    bp = Blueprint("course_knowledge", __name__, url_prefix="/api/course-knowledge")

    @bp.post("/upload")
    def upload_course_knowledge():
        user_id = get_user_id()
        file = request.files.get("file")
        if file is None or not (file.filename or "").strip():
            return jsonify({"success": False, "error": "file is required"}), 400

        try:
            result = get_ingestor().ingest_upload(
                user_id=user_id,
                filename=file.filename,
                stream=file.stream,
                content_type=file.mimetype or "",
            )
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        except Exception as exc:
            logger.warning("[COURSE-KNOWLEDGE] upload failed", exc_info=True)
            return jsonify({"success": False, "error": str(exc)}), 500

        return jsonify(
            {
                "success": True,
                "document": result["document"],
                "course_map": result["course_map"],
            }
        )

    @bp.get("/list")
    def list_course_knowledge():
        user_id = get_user_id()
        return jsonify(
            {
                "success": True,
                "items": get_ingestor().list_documents(user_id),
            }
        )

    @bp.delete("/<document_id>")
    def delete_course_knowledge(document_id: str):
        user_id = get_user_id()
        try:
            result = get_ingestor().delete_document(user_id, document_id)
            return jsonify({"success": True, **result})
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"success": False, "error": str(exc)}), 500

    @bp.get("/course-map")
    def get_course_knowledge_course_map():
        user_id = get_user_id()
        return jsonify(
            {
                "success": True,
                "courses": get_ingestor().list_courses(user_id),
            }
        )

    return bp
