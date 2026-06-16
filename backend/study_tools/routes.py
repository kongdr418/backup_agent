"""Study Tools API routes — 错题本 / 闪卡 / 错题集 / 统计."""

from flask import Blueprint, request, jsonify
from .storage import StudyToolsStorage


def create_study_tools_blueprint(
    get_user_id,
    get_storage,
    logger,
):
    bp = Blueprint("study_tools", __name__)

    def _uid():
        return get_user_id(request)

    def _store() -> StudyToolsStorage:
        return get_storage()

    # ─── mistakes ───

    @bp.route("/api/study-tools/mistakes", methods=["GET"])
    def list_mistakes():
        uid = _uid()
        params = request.args
        result = _store().list_mistakes(
            user_id=uid,
            course_id=params.get("course_id"),
            knowledge_point_id=params.get("knowledge_point_id"),
            mastered=_parse_bool(params.get("mastered")),
            source=params.get("source"),
            collection_id=params.get("collection_id"),
            q=params.get("q"),
            page=int(params.get("page", 1)),
            page_size=int(params.get("page_size", 20)),
        )
        return jsonify({"success": True, **result})

    @bp.route("/api/study-tools/mistakes", methods=["POST"])
    def add_mistake():
        uid = _uid()
        payload = _json_body()
        files = request.files.getlist("files") or []
        if files:
            payload = _json_field("payload") or payload
        item = _store().add_mistake(uid, payload)
        if files:
            _store().add_attachments(uid, item["id"], files)
            item = _store().get_mistake(uid, item["id"]) or item
        return jsonify({"success": True, "item": item})

    @bp.route("/api/study-tools/mistakes/bulk", methods=["POST"])
    def bulk_add_mistakes():
        uid = _uid()
        items = request.json.get("items", []) if request.json else []
        return jsonify({"success": True, **_store().bulk_add_mistakes(uid, items)})

    @bp.route("/api/study-tools/mistakes/<mistake_id>", methods=["GET"])
    def get_mistake(mistake_id):
        item = _store().get_mistake(_uid(), mistake_id)
        if not item:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True, "item": item})

    @bp.route("/api/study-tools/mistakes/<mistake_id>", methods=["PATCH"])
    def update_mistake(mistake_id):
        item = _store().update_mistake(_uid(), mistake_id, _json_body())
        if not item:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True, "item": item})

    @bp.route("/api/study-tools/mistakes/<mistake_id>", methods=["DELETE"])
    def delete_mistake(mistake_id):
        ok = _store().delete_mistake(_uid(), mistake_id)
        if not ok:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True})

    # ─── mistake attachments ───

    @bp.route("/api/study-tools/mistakes/<mistake_id>/attachments", methods=["POST"])
    def upload_attachments(mistake_id):
        uid = _uid()
        files = request.files.getlist("files") or []
        if not files:
            return jsonify({"success": False, "error": "NO_FILES"}), 400
        saved, rejected = _store().add_attachments(uid, mistake_id, files)
        item = _store().get_mistake(uid, mistake_id)
        return jsonify({"success": True, "saved": saved, "rejected": rejected, "item": item})

    @bp.route(
        "/api/study-tools/mistakes/<mistake_id>/attachments/<attachment_id>",
        methods=["DELETE"],
    )
    def delete_attachment(mistake_id, attachment_id):
        uid = _uid()
        _store().remove_attachment(uid, mistake_id, attachment_id)
        item = _store().get_mistake(uid, mistake_id)
        return jsonify({"success": True, "item": item})

    # ─── mistake → flashcard ───

    @bp.route("/api/study-tools/mistakes/<mistake_id>/to-flashcard", methods=["POST"])
    def mistake_to_flashcard(mistake_id):
        uid = _uid()
        mistake = _store().get_mistake(uid, mistake_id)
        if not mistake:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        card = _store().add_flashcard(uid, {
            "front": mistake.get("stem", ""),
            "back": mistake.get("correct_answer", "") + (
                "\n\n" + mistake.get("analysis", "") if mistake.get("analysis") else ""
            ),
            "course_id": mistake.get("course_id", ""),
            "course_name": mistake.get("course_name", ""),
            "knowledge_point_name": mistake.get("knowledge_point_name", ""),
            "tags": mistake.get("tags", []),
            "source": "mistake",
            "source_id": mistake_id,
        })
        return jsonify({"success": True, "item": card})

    # ─── flashcards ───

    @bp.route("/api/study-tools/flashcards", methods=["GET"])
    def list_flashcards():
        uid = _uid()
        params = request.args
        result = _store().list_flashcards(
            user_id=uid,
            course_id=params.get("course_id"),
            knowledge_point_id=params.get("knowledge_point_id"),
            source=params.get("source"),
            suspended=_parse_bool(params.get("suspended")),
            q=params.get("q"),
            page=int(params.get("page", 1)),
            page_size=int(params.get("page_size", 20)),
        )
        return jsonify({"success": True, **result})

    @bp.route("/api/study-tools/flashcards", methods=["POST"])
    def add_flashcard():
        item = _store().add_flashcard(_uid(), _json_body())
        return jsonify({"success": True, "item": item})

    @bp.route("/api/study-tools/flashcards/due", methods=["GET"])
    def list_due_flashcards():
        uid = _uid()
        limit = int(request.args.get("limit", 50))
        items = _store().list_due_flashcards(uid, limit=limit)
        return jsonify({"success": True, "items": items, "total": len(items)})

    @bp.route("/api/study-tools/flashcards/<card_id>", methods=["PATCH"])
    def update_flashcard(card_id):
        item = _store().update_flashcard(_uid(), card_id, _json_body())
        if not item:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True, "item": item})

    @bp.route("/api/study-tools/flashcards/<card_id>", methods=["DELETE"])
    def delete_flashcard(card_id):
        ok = _store().delete_flashcard(_uid(), card_id)
        if not ok:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True})

    @bp.route("/api/study-tools/flashcards/<card_id>/review", methods=["POST"])
    def review_flashcard(card_id):
        data = request.json or {}
        grade = data.get("grade", 0)
        item = _store().review_flashcard(_uid(), card_id, grade)
        if not item:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True, "item": item})

    # ─── stats ───

    @bp.route("/api/study-tools/stats", methods=["GET"])
    def get_stats():
        return jsonify({"success": True, **_store().stats(_uid())})

    # ─── mistake collections ───

    @bp.route("/api/study-tools/mistake-collections", methods=["GET"])
    def list_collections():
        result = _store().list_collections(_uid())
        return jsonify({"success": True, **result})

    @bp.route("/api/study-tools/mistake-collections", methods=["POST"])
    def create_collection():
        data = _json_body()
        item = _store().add_collection(
            _uid(),
            name=data.get("name", "未命名"),
            mistake_ids=data.get("mistake_ids", []),
        )
        return jsonify({"success": True, "item": item})

    @bp.route("/api/study-tools/mistake-collections/<collection_id>", methods=["PATCH"])
    def update_collection(collection_id):
        data = _json_body()
        item = _store().update_collection(_uid(), collection_id, data)
        if not item:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True, "item": item})

    @bp.route("/api/study-tools/mistake-collections/<collection_id>", methods=["DELETE"])
    def delete_collection(collection_id):
        ok = _store().delete_collection(_uid(), collection_id)
        if not ok:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True})

    @bp.route(
        "/api/study-tools/mistake-collections/<collection_id>/mistakes",
        methods=["POST"],
    )
    def assign_to_collection(collection_id):
        data = _json_body()
        result = _store().assign_mistakes_to_collection(
            _uid(), collection_id, data.get("mistake_ids", []),
        )
        return jsonify({"success": True, **result})

    @bp.route(
        "/api/study-tools/mistake-collections/<collection_id>/mistakes/<mistake_id>",
        methods=["DELETE"],
    )
    def remove_from_collection(collection_id, mistake_id):
        _store().remove_mistake_from_collection(_uid(), collection_id, mistake_id)
        return jsonify({"success": True})

    # ─── helpers ───

    def _json_body() -> dict:
        if request.is_json:
            return request.get_json(silent=True) or {}
        form_payload = request.form.get("payload")
        if form_payload:
            import json
            return json.loads(form_payload)
        return {}

    def _json_field(name: str):
        raw = (request.form or {}).get(name, "").strip()
        if not raw:
            return None
        import json
        return json.loads(raw)

    return bp


def _parse_bool(val):
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes")
