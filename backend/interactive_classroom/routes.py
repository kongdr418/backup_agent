from __future__ import annotations

from flask import Blueprint


def create_interactive_classroom_blueprint(views: dict[str, object]) -> Blueprint:
    bp = Blueprint("interactive_classroom", __name__, url_prefix="/api/interactive-classroom")

    bp.add_url_rule("/generate", view_func=views["generate"], methods=["POST"])
    bp.add_url_rule("/generate/cancel", view_func=views["generate_cancel"], methods=["POST"])
    bp.add_url_rule("/generate/status/<request_id>", view_func=views["generate_status"], methods=["GET"])
    bp.add_url_rule("/generate/stream/<request_id>", view_func=views["generate_stream"], methods=["GET"])

    bp.add_url_rule("/list", view_func=views["list"], methods=["GET"])
    bp.add_url_rule("/<classroom_id>", view_func=views["get"], methods=["GET"])
    bp.add_url_rule("/<classroom_id>", view_func=views["update"], methods=["PATCH"])
    bp.add_url_rule("/<classroom_id>", view_func=views["delete"], methods=["DELETE"])
    bp.add_url_rule("/clear", view_func=views["clear"], methods=["POST"])

    bp.add_url_rule("/<classroom_id>/answer", view_func=views["answer"], methods=["POST"])
    bp.add_url_rule("/<classroom_id>/report", view_func=views["report"], methods=["GET"])
    bp.add_url_rule("/<classroom_id>/practice", view_func=views["practice"], methods=["POST"])
    bp.add_url_rule("/<classroom_id>/next-lesson-plan", view_func=views["next_lesson_plan"], methods=["POST"])

    bp.add_url_rule("/<classroom_id>/event", view_func=views["record_event"], methods=["POST"])
    bp.add_url_rule("/<classroom_id>/events", view_func=views["list_events"], methods=["GET"])

    bp.add_url_rule("/<classroom_id>/discuss", view_func=views["discuss"], methods=["POST"])
    bp.add_url_rule("/<classroom_id>/discuss/stream", view_func=views["discuss_stream"], methods=["POST"])
    bp.add_url_rule("/<classroom_id>/audio/<filename>", view_func=views["audio"], methods=["GET"])

    return bp
