"""Study Tools API routes — 错题本 / 闪卡 / 错题集 / 实操实验 / 统计."""

import json
import re
from html import escape
from flask import Blueprint, request, jsonify, send_file
from interactive_classroom.event_service import (
    create_flashcard_reviewed_event,
    create_mistake_mastered_event,
    record_event,
)
from .storage import StudyToolsStorage


def create_study_tools_blueprint(
    get_user_id,
    get_storage,
    logger,
    get_classroom_storage=None,
    llm_call=None,
    resolve_content_llm_request_config=None,
):
    bp = Blueprint("study_tools", __name__)

    def _uid():
        try:
            return get_user_id(request)
        except TypeError:
            return get_user_id()

    def _store() -> StudyToolsStorage:
        return get_storage()

    def _classroom_store():
        return get_classroom_storage() if get_classroom_storage is not None else None

    def _resolve_llm_config(data: dict) -> dict:
        if resolve_content_llm_request_config is None:
            return {}
        try:
            return resolve_content_llm_request_config(data)
        except Exception:
            logger.warning("[STUDY-TOOLS] practice_lab_llm_config_failed", exc_info=True)
            return {}

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
            query=params.get("q"),
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
            _store().add_attachments(uid, item["id"], _files_payload(files))
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
        uid = _uid()
        before = _store().get_mistake(uid, mistake_id)
        item = _store().update_mistake(uid, mistake_id, _json_body())
        if not item:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        if item.get("mastered") and not (before or {}).get("mastered"):
            _record_mistake_mastered(uid, item)
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
        saved = _store().add_attachments(uid, mistake_id, _files_payload(files))
        item = _store().get_mistake(uid, mistake_id)
        return jsonify({"success": True, "saved": saved, "rejected": [], "item": item})

    @bp.route(
        "/api/study-tools/mistakes/<mistake_id>/attachments/<attachment_id>",
        methods=["GET"],
    )
    def get_attachment(mistake_id, attachment_id):
        resolved = _store().resolve_attachment(_uid(), mistake_id, attachment_id)
        if not resolved:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return send_file(
            resolved["path"],
            mimetype=resolved.get("mime") or "application/octet-stream",
            download_name=resolved.get("name") or attachment_id,
        )

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
            query=params.get("q"),
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
        uid = _uid()
        grade = int(data.get("grade", 0) or 0)
        item = _store().review_flashcard(uid, card_id, grade)
        if not item:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        _record_flashcard_reviewed(uid, item, grade)
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

    # ─── practice labs ───

    @bp.route("/api/study-tools/practice-labs", methods=["GET"])
    def list_practice_labs():
        uid = _uid()
        params = request.args
        result = _store().list_labs(
            user_id=uid,
            lab_type=params.get("type"),
            query=params.get("q"),
            page=int(params.get("page", 1)),
            page_size=int(params.get("page_size", 30)),
        )
        result["items"] = [_prepare_lab_for_response(item) for item in result.get("items", [])]
        return jsonify({"success": True, **result})

    @bp.route("/api/study-tools/practice-labs", methods=["POST"])
    def create_practice_lab():
        uid = _uid()
        data = _json_body()
        lab_type = str(data.get("type") or "animation").strip().lower()
        if lab_type not in {"animation", "code"}:
            return jsonify({"success": False, "error": "INVALID_TYPE"}), 400
        topic = _clean_route_text(data.get("topic"), 160)
        if not topic:
            return jsonify({"success": False, "error": "TOPIC_REQUIRED"}), 400
        payload = _build_llm_lab_payload(
            data,
            lab_type=lab_type,
            llm_call=llm_call,
            llm_config=_resolve_llm_config(data),
            logger=logger,
        )
        if payload is None:
            if lab_type == "animation":
                return jsonify({
                    "success": False,
                    "error": "ANIMATION_GENERATION_INVALID",
                    "message": "动画生成结果不完整或与主题不匹配，请重试或更换内容模型。",
                }), 502
            payload = _build_code_lab_payload(data)
        item = _store().add_lab(uid, payload)
        return jsonify({"success": True, "item": _prepare_lab_for_response(item)})

    @bp.route("/api/study-tools/practice-labs/<lab_id>", methods=["GET"])
    def get_practice_lab(lab_id):
        item = _store().get_lab(_uid(), lab_id)
        if not item:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True, "item": _prepare_lab_for_response(item)})

    @bp.route("/api/study-tools/practice-labs/<lab_id>", methods=["PATCH"])
    def update_practice_lab(lab_id):
        item = _store().update_lab(_uid(), lab_id, _json_body())
        if not item:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return jsonify({"success": True, "item": item})

    @bp.route("/api/study-tools/practice-labs/<lab_id>", methods=["DELETE"])
    def delete_practice_lab(lab_id):
        ok = _store().delete_lab(_uid(), lab_id)
        if not ok:
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
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

    def _files_payload(files) -> list[tuple[str, bytes, str | None]]:
        payload: list[tuple[str, bytes, str | None]] = []
        for file in files or []:
            try:
                payload.append((file.filename or "", file.read(), file.mimetype))
            except Exception:
                logger.warning("[STUDY-TOOLS] attachment_read_failed", exc_info=True)
        return payload

    def _record_mistake_mastered(uid: str, mistake: dict) -> None:
        classroom_storage = _classroom_store()
        source_ref = mistake.get("source_ref") if isinstance(mistake.get("source_ref"), dict) else {}
        classroom_id = (source_ref.get("classroom_id") or "").strip()
        if not classroom_storage or not classroom_id:
            return
        try:
            event = create_mistake_mastered_event(
                user_id=uid,
                classroom_id=classroom_id,
                scene_id=(source_ref.get("scene_id") or "").strip(),
                course_id=mistake.get("course_id") or mistake.get("course_name") or "",
                mistake=mistake,
            )
            record_event(classroom_storage, event)
        except Exception:
            logger.warning("[STUDY-TOOLS] mistake_mastered_event_failed", exc_info=True)

    def _record_flashcard_reviewed(uid: str, flashcard: dict, grade: int) -> None:
        classroom_storage = _classroom_store()
        if not classroom_storage:
            return
        source_ref: dict = {}
        if flashcard.get("source") == "mistake" and flashcard.get("source_id"):
            mistake = _store().get_mistake(uid, str(flashcard.get("source_id"))) or {}
            if isinstance(mistake.get("source_ref"), dict):
                source_ref = mistake["source_ref"]
        classroom_id = (source_ref.get("classroom_id") or "").strip()
        if not classroom_id:
            return
        try:
            event = create_flashcard_reviewed_event(
                user_id=uid,
                classroom_id=classroom_id,
                scene_id=(source_ref.get("scene_id") or "").strip(),
                course_id=flashcard.get("course_id") or flashcard.get("course_name") or "",
                flashcard=flashcard,
                grade=grade,
            )
            record_event(classroom_storage, event)
        except Exception:
            logger.warning("[STUDY-TOOLS] flashcard_reviewed_event_failed", exc_info=True)

    return bp


def _clean_route_text(value, max_length: int = 200) -> str:
    return " ".join(str(value or "").split())[:max_length]


def _clean_route_list(value, max_items: int = 10) -> list[str]:
    if isinstance(value, str):
        rows = [x.strip() for x in value.replace("，", ",").replace("、", ",").split(",")]
    elif isinstance(value, list):
        rows = value
    else:
        rows = []
    out: list[str] = []
    for row in rows:
        text = _clean_route_text(row, 60)
        if text and text not in out:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def _clean_code_text(value, max_length: int = 6000) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return text[:max_length]


def _animation_domain_profile(topic: str, points: list[str] | None = None) -> dict:
    text = f"{topic} {' '.join(points or [])}".lower()
    compact = re.sub(r"\s+", "", text)
    profiles = [
        {
            "matches": ("排序", "sort"),
            "required": ("数组", "元素", "比较", "交换", "指针", "轮次", "已排序"),
            "prompt": "当前主题属于排序算法，动画必须展示数组元素、比较位置、交换过程、轮次推进和已排序区。",
        },
        {
            "matches": ("查找", "search", "二分", "binary"),
            "required": ("数组", "目标", "区间", "指针", "low", "high", "mid", "中点"),
            "prompt": "当前主题属于查找算法，动画必须展示数据集合、目标值、指针或区间边界，以及每一步如何缩小搜索范围。",
        },
        {
            "matches": ("透镜", "成像", "光路", "焦距", "凸透镜", "凹透镜", "lens", "optics"),
            "required": ("透镜", "光线", "焦点", "焦距", "物距", "像距", "主光轴", "实像", "虚像"),
            "prompt": "当前主题属于光学成像，动画必须展示透镜、主光轴、焦点、物体、像、光线传播路径，以及物距变化对成像的影响。",
        },
        {
            "matches": ("化学", "反应", "实验", "溶液", "沉淀", "滴定", "酸碱", "氧化", "还原", "chem"),
            "required": ("反应", "试剂", "烧杯", "溶液", "分子", "沉淀", "气体", "颜色", "温度", "滴定"),
            "prompt": "当前主题属于化学实验或反应过程，动画必须展示实验器材、试剂/粒子、反应现象、变量控制和结果变化。",
        },
        {
            "matches": ("电路", "电流", "电压", "电阻", "欧姆", "circuit"),
            "required": ("电路", "电流", "电压", "电阻", "开关", "导线", "灯泡", "仪表"),
            "prompt": "当前主题属于电学过程，动画必须展示电路元件、连接关系、电流方向和参数变化对结果的影响。",
        },
    ]
    for profile in profiles:
        if any(token in compact for token in profile["matches"]):
            return profile
    return {
        "matches": (),
        "required": (),
        "prompt": "请先识别主题里的真实可视化对象，再围绕这些对象设计动画；禁止生成与主题无关的通用曲线、粒子或占位图。",
    }


def _animation_payload_matches_topic(payload: dict, topic: str, points: list[str] | None = None) -> bool:
    if not isinstance(payload, dict):
        return False
    content = payload.get("content")
    if not isinstance(content, dict):
        return False
    html = str(content.get("html") or "")
    if not html:
        return False
    semantic_fields = json.dumps({
        "title": payload.get("title"),
        "summary": payload.get("summary"),
        "knowledge_points": payload.get("knowledge_points"),
        "video_prompt": content.get("video_prompt"),
        "storyboard": content.get("storyboard"),
        "html": html,
    }, ensure_ascii=False)
    searchable = semantic_fields.lower()
    generic_markers = (
        "变量强度",
        "系统响应越明显",
        "局部变化走向整体规律",
        "通用波形",
        "通用粒子",
    )
    if any(marker in searchable for marker in generic_markers):
        return False
    profile = _animation_domain_profile(topic, points)
    required = profile.get("required") or ()
    if not required:
        return True
    hits = sum(1 for token in required if token.lower() in searchable)
    return hits >= 2


def _build_llm_lab_payload(
    data: dict,
    *,
    lab_type: str,
    llm_call,
    llm_config: dict,
    logger,
) -> dict | None:
    if llm_call is None:
        return None
    topic = _clean_route_text(data.get("topic"), 160)
    course = _clean_route_text(data.get("course"), 120) or "通用课程"
    points = _clean_route_list(data.get("knowledge_points"))
    try:
        messages = _build_lab_prompt(data, lab_type=lab_type, topic=topic, course=course, points=points)
        raw = llm_call(
            messages,
            model=llm_config.get("content_model", ""),
            api_key=llm_config.get("content_api_key", ""),
            base_url=llm_config.get("content_base_url", ""),
            provider_type=llm_config.get("content_provider_type", ""),
            temperature=0.35,
            max_tokens=6500 if lab_type == "animation" else 3600,
        )
        payload = _parse_llm_lab_payload(raw, lab_type=lab_type, source=data)
        if payload is not None:
            if lab_type == "animation" and not _animation_payload_matches_topic(payload, topic, points):
                logger.warning(
                    "[STUDY-TOOLS] practice_lab_llm_payload_rejected type=%s topic=%s reason=topic_mismatch",
                    lab_type,
                    topic,
                )
                return None
            payload["content"]["generation_mode"] = "llm"
            return payload
        logger.warning(
            "[STUDY-TOOLS] practice_lab_llm_payload_rejected type=%s topic=%s reason=parse_failed raw_len=%s",
            lab_type,
            topic,
            len(str(raw or "")),
        )
    except Exception:
        logger.warning(
            "[STUDY-TOOLS] practice_lab_llm_generation_failed type=%s topic=%s",
            lab_type,
            topic,
            exc_info=True,
        )
    return None


def _build_lab_prompt(
    data: dict,
    *,
    lab_type: str,
    topic: str,
    course: str,
    points: list[str],
) -> list[dict]:
    point_text = "、".join(points) if points else "由主题自动提炼"
    common = (
        "你是智创空间的多智能体学习资源生成器。"
        "请为学生生成一个可直接用于课堂的实操学习资产。"
        "只输出 JSON 对象，不要 markdown，不要代码围栏，不要解释。"
        f"课程：{course}\n主题：{topic}\n知识点：{point_text}\n"
        "必须使用简体中文，内容严谨、适合高校学生。"
    )
    if lab_type == "animation":
        domain_prompt = _animation_domain_profile(topic, points).get("prompt", "")
        return [
            {
                "role": "system",
                "content": common
                + "\n生成类型：动画演示。你需要输出一个离线可运行的 HTML 动画实验。",
            },
            {
                "role": "user",
                "content": (
                    "输出 JSON schema："
                    "{"
                    '"title": string,'
                    '"summary": string,'
                    '"knowledge_points": string[],'
                    '"video_prompt": string,'
                    '"storyboard": [{"shot": number, "title": string, "description": string}],'
                    '"html": string'
                    "}\n"
                    "HTML 要求：完整 <!doctype html> 文档；只用内联 CSS/JS；不得引用外部 URL；"
                    "必须包含 canvas 或 SVG 动画，必须包含至少一个 slider/button 交互控件；"
                    "动画逻辑必须贴合主题，不要使用与主题无关的通用波形占位；"
                    "如果主题是排序或查找算法，必须展示数组、指针、比较、交换或区间收缩等算法状态；"
                    f"{domain_prompt}"
                    "canvas 的 width/height 内部缓冲不得低于 1200x720，CSS 需要响应式适配容器；"
                    "JavaScript 不得使用 // 行注释，注释必须使用 /* ... */，避免压缩成一行后脚本失效；"
                    "画面风格浅色、专业、主色 #0f172a 和 #2D5016。"
                ),
            },
        ]
    starter = _clean_code_text(data.get("starter_code"), 2000).strip()
    starter_hint = f"\n用户提供的 starter_code：\n{starter}" if starter else ""
    return [
        {
            "role": "system",
            "content": common
            + "\n生成类型：代码实操。你需要输出浏览器内 JavaScript 练习配置。",
        },
        {
            "role": "user",
            "content": (
                "输出 JSON schema："
                "{"
                '"title": string,'
                '"summary": string,'
                '"knowledge_points": string[],'
                '"task_description": string,'
                '"starter_code": string,'
                '"test_cases": [{"input": string, "expected": string, "description": string}],'
                '"hints": string[],'
                '"solution": string'
                "}\n"
                "代码要求：starter_code 必须定义 function solve(input)；"
                "test_cases 至少 3 个，expected 必须与 solution 的输出一致；"
                "练习要贴合主题，不能一律生成平方数示例；"
                "只允许 JavaScript，不要 TypeScript、Python、Java、C++。"
                f"{starter_hint}"
            ),
        },
    ]


def _parse_llm_lab_payload(raw: str, *, lab_type: str, source: dict) -> dict | None:
    data = _extract_json_object(raw)
    if not isinstance(data, dict) and lab_type == "animation":
        html = _sanitize_lab_html(_extract_html_document(raw))
        if html:
            topic = _clean_route_text(source.get("topic"), 160)
            course = _clean_route_text(source.get("course"), 120) or "通用课程"
            points = _clean_route_list(source.get("knowledge_points"))
            title = _clean_route_text(source.get("title"), 120) or f"{topic} 动画演示"
            return {
                "type": "animation",
                "title": title,
                "course": course,
                "topic": topic,
                "knowledge_points": points,
                "summary": f"围绕「{topic}」生成的交互式动画实验。",
                "content": {
                    "html": html,
                    "video_prompt": f"生成一段关于「{topic}」的教学动画视频。",
                    "storyboard": [],
                    "duration_seconds": 45,
                    "asset_kind": "interactive_animation",
                },
            }
    if not isinstance(data, dict):
        return None
    topic = _clean_route_text(source.get("topic"), 160)
    course = _clean_route_text(source.get("course"), 120) or "通用课程"
    points = _clean_route_list(data.get("knowledge_points")) or _clean_route_list(source.get("knowledge_points"))
    title = _clean_route_text(data.get("title"), 120) or (
        f"{topic} 代码实操" if lab_type == "code" else f"{topic} 动画演示"
    )
    summary = _clean_route_text(data.get("summary"), 500)

    if lab_type == "animation":
        html = _sanitize_lab_html(str(data.get("html") or ""))
        if not html:
            return None
        storyboard = _normalize_storyboard(data.get("storyboard"))
        return {
            "type": "animation",
            "title": title,
            "course": course,
            "topic": topic,
            "knowledge_points": points,
            "summary": summary or f"围绕「{topic}」生成的交互式动画实验。",
            "content": {
                "html": html,
                "video_prompt": _clean_route_text(data.get("video_prompt"), 1000)
                or f"生成一段关于「{topic}」的教学动画视频。",
                "storyboard": storyboard,
                "duration_seconds": 45,
                "asset_kind": "interactive_animation",
            },
        }

    starter_code = str(data.get("starter_code") or "").strip()
    solution = str(data.get("solution") or "").strip()
    test_cases = _normalize_code_tests(data.get("test_cases"))
    if not starter_code or "function solve" not in starter_code or not test_cases:
        return None
    task_description = _clean_route_text(data.get("task_description"), 800)
    hints = _clean_route_list(data.get("hints"), max_items=5)
    html = _code_lab_html(
        title,
        topic,
        course,
        starter_code,
        test_cases,
        task_description=task_description,
        hints=hints,
    )
    return {
        "type": "code",
        "title": title,
        "course": course,
        "topic": topic,
        "knowledge_points": points,
        "summary": summary or f"通过代码运行和测试用例练习「{topic}」。",
        "content": {
            "html": html,
            "language": "javascript",
            "starter_code": starter_code,
            "solution": solution,
            "test_cases": test_cases,
            "hints": hints,
            "task_description": task_description,
            "asset_kind": "code_playground",
        },
    }


def _extract_json_object(raw: str) -> dict | None:
    text = str(raw or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _extract_html_document(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    text = re.sub(r"^```(?:html)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    lower = text.lower()
    start_candidates = [idx for idx in (lower.find("<!doctype html"), lower.find("<html")) if idx >= 0]
    if not start_candidates:
        return ""
    start = min(start_candidates)
    end = lower.rfind("</html>")
    if end < start:
        return ""
    return text[start:end + len("</html>")]


def _sanitize_lab_html(html: str) -> str:
    text = str(html or "").strip()
    text = re.sub(r"^```(?:html)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = _repair_lab_html_for_display(text)
    if not text.lower().lstrip().startswith("<!doctype html") and "<html" not in text.lower():
        return ""
    lowered = text.lower()
    blocked = [
        "<script src=",
        "<iframe",
        "<object",
        "<embed",
        "http://",
        "https://",
        "fetch(",
        "xmlhttprequest",
        "localstorage",
        "sessionstorage",
        "document.cookie",
    ]
    if any(token in lowered for token in blocked):
        return ""
    if len(re.findall(r"<!doctype html", lowered)) > 1 or len(re.findall(r"<html", lowered)) > 1:
        return ""
    if "</html>" not in lowered:
        return ""
    return text[:120000]


def _prepare_lab_for_response(item: dict) -> dict:
    if not isinstance(item, dict):
        return item
    content = item.get("content")
    if not isinstance(content, dict):
        return item
    html = content.get("html")
    if not isinstance(html, str) or not html:
        return item
    return {
        **item,
        "content": {
            **content,
            "html": _repair_lab_html_for_display(html),
        },
    }


def _repair_lab_html_for_display(html: str) -> str:
    """Repair common LLM HTML issue: one-line scripts with // comments swallow code."""
    text = str(html or "")
    text = _upgrade_canvas_resolution(text)

    def repair_script(match: re.Match) -> str:
        open_tag, script, close_tag = match.group(1), match.group(2), match.group(3)
        return f"{open_tag}{_repair_js_line_comments(script)}{close_tag}"

    return re.sub(
        r"(<script\b[^>]*>)(.*?)(</script>)",
        repair_script,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _upgrade_canvas_resolution(html: str) -> str:
    """Raise tiny LLM canvas buffers so previews look crisp when scaled."""
    text = str(html or "")

    def repl(match: re.Match) -> str:
        tag = match.group(0)

        def read_attr(name: str) -> int | None:
            found = re.search(rf'\b{name}\s*=\s*["\']?(\d+)', tag, flags=re.IGNORECASE)
            return int(found.group(1)) if found else None

        width = read_attr("width")
        height = read_attr("height")
        target_w = max(width or 0, 1200)
        target_h = max(height or 0, 720)
        if width and height and width >= 1000 and height >= 620:
            return tag
        if width:
            tag = re.sub(r'\bwidth\s*=\s*["\']?\d+["\']?', f'width="{target_w}"', tag, flags=re.IGNORECASE)
        else:
            tag = tag[:-1] + f' width="{target_w}">'
        if height:
            tag = re.sub(r'\bheight\s*=\s*["\']?\d+["\']?', f'height="{target_h}"', tag, flags=re.IGNORECASE)
        else:
            tag = tag[:-1] + f' height="{target_h}">'
        return tag

    text = re.sub(r"<canvas\b[^>]*>", repl, text, count=3, flags=re.IGNORECASE)
    responsive_rule = (
        "\ncanvas { max-width: 100% !important; height: auto !important; "
        "image-rendering: auto; }\n"
    )
    if "</style>" in text.lower():
        text = re.sub(r"</style>", responsive_rule + "</style>", text, count=1, flags=re.IGNORECASE)
    else:
        text = re.sub(
            r"</head>",
            f"<style>{responsive_rule}</style></head>",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    return text


def _repair_js_line_comments(script: str) -> str:
    if "//" not in script:
        return script
    boundary = (
        r"(?=(?:function\s+|const\s+|let\s+|var\s+|if\s*\(|else\b|for\s*\(|"
        r"while\s*\(|return\b|document\.|ctx\.|canvas\.|slider\.|uValue\.|"
        r"requestAnimationFrame\s*\(|draw\s*\(|[A-Za-z_$][\w$]*\s*=|//))"
    )

    def repl(match: re.Match) -> str:
        comment = (match.group(1) or "").strip()
        return f"/* {comment} */" if comment else ""

    repaired = re.sub(r"//\s*([^/\n\r]*?)\s*" + boundary, repl, script)
    return repaired


def _normalize_storyboard(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    rows: list[dict] = []
    for idx, raw in enumerate(value[:8], start=1):
        if not isinstance(raw, dict):
            continue
        rows.append({
            "shot": int(raw.get("shot") or idx),
            "title": _clean_route_text(raw.get("title"), 80),
            "description": _clean_route_text(raw.get("description"), 300),
        })
    return rows


def _normalize_code_tests(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    rows: list[dict] = []
    for idx, raw in enumerate(value[:8], start=1):
        if not isinstance(raw, dict):
            continue
        input_text = _clean_route_text(raw.get("input"), 160)
        expected = _clean_route_text(raw.get("expected"), 160)
        if expected == "":
            continue
        rows.append({
            "input": input_text,
            "expected": expected,
            "description": _clean_route_text(raw.get("description"), 160) or f"测试 {idx}",
        })
    return rows


def _build_code_lab_payload(data: dict) -> dict:
    topic = _clean_route_text(data.get("topic"), 160)
    course = _clean_route_text(data.get("course"), 120) or "通用课程"
    points = _clean_route_list(data.get("knowledge_points"))
    title = _clean_route_text(data.get("title"), 120) or f"{topic} 代码实操"
    starter_code = _clean_code_text(data.get("starter_code"), 2000).strip() or (
        "function solve(input) {\n"
        "  const value = Number(input);\n"
        "  // TODO: 修改这里，让函数返回你的答案\n"
        "  return value;\n"
        "}"
    )
    test_cases = data.get("test_cases")
    if not isinstance(test_cases, list) or not test_cases:
        test_cases = [
            {"input": "2", "expected": "4", "description": "示例 1"},
            {"input": "5", "expected": "25", "description": "示例 2"},
        ]
    cleaned_tests = []
    for idx, row in enumerate(test_cases[:8], start=1):
        if not isinstance(row, dict):
            continue
        cleaned_tests.append({
            "input": _clean_route_text(row.get("input"), 120),
            "expected": _clean_route_text(row.get("expected"), 120),
            "description": _clean_route_text(row.get("description"), 120) or f"测试 {idx}",
        })
    html = _code_lab_html(title, topic, course, starter_code, cleaned_tests)
    return {
        "type": "code",
        "title": title,
        "course": course,
        "topic": topic,
        "knowledge_points": points,
        "summary": f"通过浏览器内代码运行和测试用例校验练习「{topic}」。",
        "content": {
            "html": html,
            "language": "javascript",
            "starter_code": starter_code,
            "test_cases": cleaned_tests,
            "asset_kind": "code_playground",
            "generation_mode": "fallback",
        },
    }


def _code_lab_html(
    title: str,
    topic: str,
    course: str,
    starter_code: str,
    test_cases: list[dict],
    task_description: str = "",
    hints: list[str] | None = None,
) -> str:
    safe_title = escape(title)
    safe_topic = escape(topic)
    safe_course = escape(course)
    safe_code = escape(starter_code)
    safe_task = escape(task_description or f"完成 solve(input)，让它通过与「{topic}」相关的测试用例。")
    hints = hints or []
    hints_html = "".join(f"<li>{escape(hint)}</li>" for hint in hints[:5])
    tests_json = json.dumps(test_cases, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{safe_title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8fafc; color: #0f172a; }}
    .wrap {{ min-height: 100vh; display: grid; grid-template-rows: auto 1fr auto; gap: 12px; padding: 18px; }}
    h1 {{ margin: 0; font-size: 20px; }}
    .meta {{ color: #64748b; font-size: 13px; margin-top: 4px; }}
    .grid {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(260px, .8fr); gap: 12px; min-height: 380px; }}
    textarea {{ width: 100%; height: 100%; min-height: 360px; resize: none; border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px; font: 14px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .panel {{ border: 1px solid #dbe3ea; border-radius: 8px; background: #fff; padding: 14px; overflow: auto; }}
    .task {{ border: 1px solid #dbe3ea; border-radius: 8px; background: #fff; padding: 12px; margin-bottom: 12px; color: #334155; font-size: 14px; line-height: 1.65; }}
    .hints {{ margin: 10px 0 0; padding-left: 18px; color: #475569; font-size: 13px; }}
    button {{ border: 1px solid #cbd5e1; background: #0f172a; color: #fff; border-radius: 6px; padding: 8px 12px; cursor: pointer; }}
    .case {{ padding: 10px; border: 1px solid #e2e8f0; border-radius: 6px; margin-top: 8px; }}
    .pass {{ border-color: #86efac; background: #f0fdf4; }}
    .fail {{ border-color: #fecaca; background: #fef2f2; }}
    @media (max-width: 760px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>{safe_title}</h1>
      <div class="meta">{safe_course} · {safe_topic} · JavaScript 浏览器内运行</div>
    </header>
    <div class="grid">
      <textarea id="editor" spellcheck="false">{safe_code}</textarea>
      <div class="panel">
        <div class="task">
          <strong>任务</strong><br />
          {safe_task}
          {"<ul class=\"hints\">" + hints_html + "</ul>" if hints_html else ""}
        </div>
        <button id="run">运行测试</button>
        <div id="output"></div>
      </div>
    </div>
  </div>
  <script>
    const tests = {tests_json};
    const editor = document.getElementById('editor');
    const output = document.getElementById('output');
    document.getElementById('run').onclick = () => {{
      output.innerHTML = '';
      let solve;
      try {{
        const module = {{}};
        new Function('module', editor.value + '; module.solve = typeof solve === "function" ? solve : null;')(module);
        solve = module.solve;
        if (!solve) throw new Error('请定义 function solve(input) {{ ... }}');
      }} catch (err) {{
        output.innerHTML = '<div class="case fail">代码解析失败：' + String(err.message || err) + '</div>';
        return;
      }}
      let passed = 0;
      for (const item of tests) {{
        let actual = '';
        let ok = false;
        try {{
          actual = String(solve(item.input));
          ok = actual.trim() === String(item.expected).trim();
          if (ok) passed += 1;
        }} catch (err) {{
          actual = '运行错误：' + String(err.message || err);
        }}
        const div = document.createElement('div');
        div.className = 'case ' + (ok ? 'pass' : 'fail');
        div.innerHTML = '<strong>' + (ok ? '通过' : '未通过') + ' · ' + item.description + '</strong><br>' +
          '输入：<code>' + item.input + '</code><br>' +
          '期望：<code>' + item.expected + '</code><br>' +
          '实际：<code>' + actual + '</code>';
        output.appendChild(div);
      }}
      const summary = document.createElement('div');
      summary.className = 'case ' + (passed === tests.length ? 'pass' : 'fail');
      summary.innerHTML = '<strong>结果：' + passed + ' / ' + tests.length + ' 通过</strong>';
      output.prepend(summary);
    }};
  </script>
</body>
</html>"""


def _parse_bool(val):
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes")
