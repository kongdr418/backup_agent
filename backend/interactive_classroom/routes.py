from __future__ import annotations

import json
import mimetypes
import os
import re
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, request, send_file

from .discussion_service import (
    generate_discussion_reply,
    generate_discussion_reply_stream,
    generate_multi_agent_discussion_reply_stream,
    generate_multi_agent_discussion_turns,
    normalize_discussion_request,
)


def create_interactive_classroom_blueprint(
    *,
    get_user_id: Callable[[], str],
    get_storage: Callable[[], Any],
    get_generation_service: Callable[[], Any],
    get_runtime_service: Callable[[], Any],
    resolve_content_llm_request_config: Callable[[dict], dict],
    backend_dir: str,
    logger: Any,
) -> Blueprint:
    bp = Blueprint("interactive_classroom", __name__, url_prefix="/api/interactive-classroom")

    def _invalid_classroom_id(classroom_id: str) -> bool:
        return '..' in classroom_id or '/' in classroom_id or '\\' in classroom_id

    def _resolve_discussion_classroom(user_id: str, classroom_id: str):
        classroom_id = (classroom_id or '').strip()
        if _invalid_classroom_id(classroom_id):
            return None, ({'success': False, 'error': '非法 classroom_id'}, 400)

        if get_generation_service().job_service.is_safe_request_id(classroom_id):
            preview = get_generation_service().classroom_from_generation_preview(
                user_id=user_id,
                request_id=classroom_id,
            )
            if preview is not None:
                return preview, None

        try:
            classroom = get_storage().load_classroom(user_id, classroom_id)
        except ValueError:
            return None, ({'success': False, 'error': '非法 classroom_id'}, 400)
        if classroom is None:
            return None, ({'success': False, 'error': '课堂不存在'}, 404)
        return classroom, None

    @bp.route("/generate", methods=["POST"])
    def generate():
        payload, status = get_generation_service().start_generation(
            user_id=get_user_id(),
            data=request.json or {},
        )
        return jsonify(payload), status

    @bp.route("/generate/cancel", methods=["POST"])
    def generate_cancel():
        data = request.json or {}
        payload, status = get_generation_service().cancel_generation(data.get('request_id'))
        return jsonify(payload), status

    @bp.route("/generate/status/<request_id>", methods=["GET"])
    def generate_status(request_id):
        payload, status = get_generation_service().get_generation_status(request_id)
        return jsonify(payload), status

    @bp.route("/generate/stream/<request_id>", methods=["GET"])
    def generate_stream(request_id):
        request_id = (request_id or '').strip()
        if not get_generation_service().job_service.is_safe_request_id(request_id):
            return jsonify({'success': False, 'error': '非法 request_id'}), 400
        if get_generation_service().job_service.get_job(request_id) is None:
            return jsonify({'success': False, 'error': '生成任务不存在'}), 404

        response = Response(
            get_generation_service().build_stream_generator(request_id),
            mimetype='text/event-stream',
        )
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Accel-Buffering'] = 'no'
        response.headers['Connection'] = 'keep-alive'
        return response

    @bp.route("/list", methods=["GET"])
    def list_classrooms():
        rows = get_storage().list_classrooms(get_user_id())
        return jsonify({'classrooms': rows})

    @bp.route("/<classroom_id>", methods=["GET"])
    def get_classroom(classroom_id):
        user_id = get_user_id()
        if _invalid_classroom_id(classroom_id):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        classroom = get_storage().load_classroom(user_id, classroom_id)
        if classroom is None:
            return jsonify({'success': False, 'error': '课堂不存在'}), 404
        classroom['answers_record'] = get_storage().load_answers(user_id, classroom_id)
        return jsonify({'success': True, 'classroom': classroom})

    @bp.route("/<classroom_id>", methods=["PATCH"])
    def update_classroom(classroom_id):
        user_id = get_user_id()
        if _invalid_classroom_id(classroom_id):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        data = request.json or {}
        title = (data.get('title') or '').strip()
        if not title:
            return jsonify({'success': False, 'error': 'title 不能为空'}), 400
        ok = get_storage().rename_classroom(user_id, classroom_id, title)
        if not ok:
            return jsonify({'success': False, 'error': '课堂不存在'}), 404
        classroom = get_storage().load_classroom(user_id, classroom_id)
        return jsonify({'success': True, 'classroom': classroom})

    @bp.route("/<classroom_id>", methods=["DELETE"])
    def delete_classroom(classroom_id):
        user_id = get_user_id()
        if _invalid_classroom_id(classroom_id):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        ok = get_storage().delete_classroom(user_id, classroom_id)
        if not ok:
            return jsonify({'success': False, 'error': '课堂不存在'}), 404
        return jsonify({'success': True})

    @bp.route("/clear", methods=["POST"])
    def clear_classrooms():
        data = request.json or {}
        if not data.get('confirm'):
            return jsonify({'success': False, 'error': '需要 confirm: true'}), 400
        count = get_storage().delete_all_classrooms(get_user_id())
        return jsonify({'success': True, 'deleted': count})

    @bp.route("/<classroom_id>/answer", methods=["POST"])
    def answer(classroom_id):
        user_id = get_user_id()
        if _invalid_classroom_id(classroom_id):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        data = request.json or {}
        scene_id = (data.get('scene_id') or '').strip()
        answers = data.get('answers') or {}
        if not scene_id or not isinstance(answers, dict):
            return jsonify({'success': False, 'error': 'scene_id 或 answers 非法'}), 400

        classroom = get_storage().load_classroom(user_id, classroom_id)
        if classroom is None:
            return jsonify({'success': False, 'error': '课堂不存在'}), 404
        scene = next((s for s in classroom.get('scenes', []) if s.get('id') == scene_id), None)
        if scene is None or scene.get('type') != 'quiz':
            return jsonify({'success': False, 'error': 'quiz scene 不存在'}), 404

        has_short_answer = any(
            str(q.get('type', '')) == 'short_answer'
            for q in scene.get('content', {}).get('questions', [])
        )
        llm_config = resolve_content_llm_request_config(data) if has_short_answer else None
        result = get_runtime_service().submit_answer(
            user_id=user_id,
            classroom_id=classroom_id,
            classroom=classroom,
            scene=scene,
            scene_id=scene_id,
            answers=answers,
            request_data=data,
            llm_config=llm_config,
        )
        return jsonify({'success': True, **result})

    @bp.route("/<classroom_id>/report", methods=["GET"])
    def report(classroom_id):
        user_id = get_user_id()
        if _invalid_classroom_id(classroom_id):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        classroom = get_storage().load_classroom(user_id, classroom_id)
        if classroom is None:
            return jsonify({'success': False, 'error': '课堂不存在'}), 404
        payload = get_runtime_service().build_report_for_classroom(
            user_id=user_id,
            classroom_id=classroom_id,
            classroom=classroom,
        )
        return jsonify({'success': True, 'report': payload})

    @bp.route("/<classroom_id>/practice", methods=["POST"])
    def create_practice(classroom_id):
        user_id = get_user_id()
        if _invalid_classroom_id(classroom_id):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        data = request.get_json(silent=True) or {}
        task_id = (data.get('task_id') or '').strip()
        task_type = (data.get('task_type') or '').strip()
        if not task_id or not task_type:
            return jsonify({'success': False, 'error': 'task_id 和 task_type 不能为空'}), 400
        classroom = get_storage().load_classroom(user_id, classroom_id)
        if classroom is None:
            return jsonify({'success': False, 'error': '课堂不存在'}), 404
        try:
            practice = get_runtime_service().create_practice_from_recommendation(
                user_id=user_id,
                classroom_id=classroom_id,
                classroom=classroom,
                task_id=task_id,
                task_type=task_type,
            )
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        return jsonify({
            'success': True,
            'classroom_id': practice.get('id'),
            'classroom': practice,
        }), 201

    @bp.route("/<classroom_id>/next-lesson-plan", methods=["POST"])
    def next_lesson_plan(classroom_id):
        user_id = get_user_id()
        if _invalid_classroom_id(classroom_id):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        classroom = get_storage().load_classroom(user_id, classroom_id)
        if classroom is None:
            return jsonify({'success': False, 'error': '课堂不存在'}), 404
        plan = get_runtime_service().build_next_lesson_plan_for_classroom(
            user_id=user_id,
            classroom_id=classroom_id,
            classroom=classroom,
            overrides=request.json or {},
        )
        return jsonify({'success': True, 'plan': plan})

    @bp.route("/<classroom_id>/event", methods=["POST"])
    def record_event(classroom_id):
        user_id = get_user_id()
        if (
            not classroom_id
            or _invalid_classroom_id(classroom_id)
            or not re.match(r'^[a-zA-Z0-9_-]{1,128}$', classroom_id)
        ):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        data = request.json or {}
        event_type = (data.get('event_type') or '').strip()
        scene_id = (data.get('scene_id') or '').strip()
        if not event_type:
            return jsonify({'success': False, 'error': 'event_type 不能为空'}), 400
        classroom = get_storage().load_classroom(user_id, classroom_id)
        if classroom is None:
            return jsonify({'success': False, 'error': '课堂不存在'}), 404
        try:
            saved = get_runtime_service().record_learning_event(
                user_id=user_id,
                classroom_id=classroom_id,
                classroom=classroom,
                event_type=event_type,
                scene_id=scene_id,
                payload=data.get('payload') or {},
            )
            return jsonify({'success': True, 'event': saved.to_dict()})
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        except Exception as exc:
            logger.exception('[INTERACTIVE-CLASSROOM] /event 记录失败: %s', exc)
            return jsonify({'success': False, 'error': '事件记录失败'}), 500

    @bp.route("/<classroom_id>/events", methods=["GET"])
    def list_events(classroom_id):
        user_id = get_user_id()
        if _invalid_classroom_id(classroom_id):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        classroom = get_storage().load_classroom(user_id, classroom_id)
        if classroom is None:
            return jsonify({'success': False, 'error': '课堂不存在'}), 404
        events = get_storage().load_events(user_id, classroom_id)
        filter_type = (request.args.get('type') or '').strip()
        if filter_type:
            events = [event for event in events if event.get('type') == filter_type]
        return jsonify({'success': True, 'events': events})

    @bp.route("/<classroom_id>/discuss", methods=["POST"])
    def discuss(classroom_id):
        user_id = get_user_id()
        data = request.json or {}
        discussion, error = normalize_discussion_request(data)
        if error:
            return jsonify({'success': False, 'error': error}), 400
        classroom, error_response = _resolve_discussion_classroom(user_id, classroom_id)
        if error_response is not None:
            payload, status = error_response
            return jsonify(payload), status
        llm_config = resolve_content_llm_request_config(data)
        if discussion['multi_agent']:
            turns = generate_multi_agent_discussion_turns(
                classroom=classroom,
                played_scene_ids=discussion['played_scene_ids'],
                conversation=discussion['messages'],
                trigger=discussion['trigger'],
                quick_action=discussion['quick_action'],
                current_scene_id=discussion['current_scene_id'],
                llm_config=llm_config,
            )
            return jsonify({
                'success': True,
                'assistant_message': turns[-1] if turns else {
                    'role': 'assistant',
                    'content': '',
                    'trigger': discussion['trigger'],
                },
                'assistant_messages': turns,
                'auto_advance_paused': True,
            })
        reply = generate_discussion_reply(
            classroom=classroom,
            played_scene_ids=discussion['played_scene_ids'],
            conversation=discussion['messages'],
            trigger=discussion['trigger'],
            quick_action=discussion['quick_action'],
            current_scene_id=discussion['current_scene_id'],
            llm_config=llm_config,
        )
        return jsonify({
            'success': True,
            'assistant_message': {
                'role': 'assistant',
                'content': reply,
                'trigger': discussion['trigger'],
            },
            'auto_advance_paused': True,
        })

    @bp.route("/<classroom_id>/discuss/stream", methods=["POST"])
    def discuss_stream(classroom_id):
        user_id = get_user_id()
        data = request.json or {}
        discussion, error = normalize_discussion_request(data)
        if error:
            return jsonify({'success': False, 'error': error}), 400
        classroom, error_response = _resolve_discussion_classroom(user_id, classroom_id)
        if error_response is not None:
            payload, status = error_response
            return jsonify(payload), status
        llm_config = resolve_content_llm_request_config(data)

        def generate():
            try:
                if discussion['multi_agent']:
                    for event in generate_multi_agent_discussion_reply_stream(
                        classroom=classroom,
                        played_scene_ids=discussion['played_scene_ids'],
                        conversation=discussion['messages'],
                        trigger=discussion['trigger'],
                        quick_action=discussion['quick_action'],
                        current_scene_id=discussion['current_scene_id'],
                        llm_config=llm_config,
                    ):
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                else:
                    for chunk in generate_discussion_reply_stream(
                        classroom=classroom,
                        played_scene_ids=discussion['played_scene_ids'],
                        conversation=discussion['messages'],
                        trigger=discussion['trigger'],
                        quick_action=discussion['quick_action'],
                        current_scene_id=discussion['current_scene_id'],
                        llm_config=llm_config,
                    ):
                        yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True, 'auto_advance_paused': True}, ensure_ascii=False)}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    @bp.route("/<classroom_id>/audio/<filename>", methods=["GET"])
    def audio(classroom_id, filename):
        user_id = get_user_id()
        if _invalid_classroom_id(classroom_id):
            return jsonify({'success': False, 'error': '非法 classroom_id'}), 400
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'success': False, 'error': '非法 filename'}), 400
        audio_path = os.path.join(
            backend_dir,
            'memory',
            'users',
            user_id,
            'interactive_classrooms',
            classroom_id,
            'audio',
            filename,
        )
        if not os.path.exists(audio_path):
            return jsonify({'success': False, 'error': '音频不存在'}), 404
        guessed_type, _ = mimetypes.guess_type(audio_path)
        return send_file(audio_path, mimetype=guessed_type or 'application/octet-stream')

    return bp
