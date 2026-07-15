from __future__ import annotations

import json
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, request

from .annotation import annotate_sample
from .logger import AI_ANNOTATION_STREAM, FINAL_ANNOTATION_STREAM, RAW_STREAM, ResearchLogger


def create_research_logging_blueprint(
    *,
    get_user_id: Callable[[], str],
    get_memory_root: Callable[[], str],
    resolve_content_llm_request_config: Callable[[dict], dict],
    logger: Any,
) -> Blueprint:
    bp = Blueprint("research_logging", __name__, url_prefix="/api/research")

    def _research_logger() -> ResearchLogger:
        return ResearchLogger(memory_root=get_memory_root())

    @bp.route("/samples", methods=["GET"])
    def list_samples():
        try:
            limit = int(request.args.get("limit", "100"))
        except ValueError:
            limit = 100
        source = (request.args.get("source") or "").strip()
        records = _research_logger().list_records_all_users(RAW_STREAM, limit=max(limit, 0))
        if source:
            records = [record for record in records if record.get("source") == source]
        return jsonify({"success": True, "samples": records})

    @bp.route("/annotations/ai", methods=["GET"])
    def list_ai_annotations():
        return jsonify({
            "success": True,
            "annotations": _research_logger().list_records_all_users(AI_ANNOTATION_STREAM, limit=0),
        })

    @bp.route("/annotations/final", methods=["GET"])
    def list_final_annotations():
        return jsonify({
            "success": True,
            "annotations": _research_logger().list_records_all_users(FINAL_ANNOTATION_STREAM, limit=0),
        })

    @bp.route("/samples/<output_id>/ai-annotate", methods=["POST"])
    def ai_annotate(output_id):
        data = request.json or {}
        resolved = _research_logger().find_raw_sample_all_users(output_id)
        if resolved is None:
            return jsonify({"success": False, "error": "样本不存在"}), 404
        user_id, sample = resolved
        llm_config = resolve_content_llm_request_config(data)
        try:
            annotation = annotate_sample(sample, llm_config=llm_config)
        except Exception as exc:
            logger.exception("[RESEARCH] AI 标注失败 output_id=%s", output_id)
            return jsonify({"success": False, "error": f"AI 标注失败：{type(exc).__name__}"}), 500
        saved = _research_logger().record_ai_annotation(
            user_id=user_id,
            sample=sample,
            annotation=annotation,
            model_version=llm_config.get("content_model", ""),
            provider_type=llm_config.get("content_provider_type", ""),
        )
        return jsonify({"success": True, "annotation": saved})

    @bp.route("/samples/<output_id>/final-annotation", methods=["POST"])
    def final_annotation(output_id):
        data = request.json or {}
        resolved = _research_logger().find_raw_sample_all_users(output_id)
        if resolved is None:
            return jsonify({"success": False, "error": "样本不存在"}), 404
        user_id, _sample = resolved
        saved = _research_logger().record_final_annotation(
            user_id=user_id,
            output_id=output_id,
            annotation=data,
        )
        return jsonify({"success": True, "annotation": saved})

    @bp.route("/export", methods=["GET"])
    def export_samples():
        fmt = (request.args.get("format") or "csv").strip().lower()
        research_logger = _research_logger()
        if fmt == "json":
            return Response(
                json.dumps(research_logger.list_records_all_users(RAW_STREAM, limit=0), ensure_ascii=False, indent=2),
                mimetype="application/json; charset=utf-8",
            )
        return Response(
            research_logger.export_csv_all_users(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=research_samples.csv"},
        )

    return bp
