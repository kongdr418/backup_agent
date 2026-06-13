from __future__ import annotations

import glob
import json
import os
import shutil
from collections.abc import Callable
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, jsonify, request, send_file


def create_ppt_routes_blueprint(
    *,
    get_user_id: Callable[[], str],
    get_provider_for_model: Callable[[str], tuple[str, dict | None, Any]],
    providers: dict[str, dict],
    server_api_keys: dict[str, str],
    bool_from_payload: Callable[[Any, bool], bool],
    resolve_ppt_generation_notes: Callable[[dict, str], str | None],
    resolve_svg_job_dir: Callable[[str, str], tuple[str, str]],
    scan_dir: Callable[[str, str], str],
    backend_dir: str,
    logger: Any,
) -> Blueprint:
    bp = Blueprint("ppt_routes", __name__)

    @bp.post("/api/ppt-svg/generate")
    def ppt_svg_generate():
        data = request.json or {}
        topic = data.get("topic", "").strip()
        language = data.get("language", "zh")
        num_slides = data.get("num_slides")
        style = data.get("style", "education")
        detail_level = data.get("detail_level", "normal")
        model = data.get("model", "deepseek-v4-flash")
        api_key = data.get("api_key")
        base_url = data.get("base_url")
        provider_id = (data.get("provider_id") or data.get("providerId") or "").strip()
        canvas_format = data.get("canvas_format", "ppt169")

        inferred_provider_id, inferred_provider, _ = get_provider_for_model(model)
        if not provider_id:
            provider_id = inferred_provider_id or "deepseek"
        provider = providers.get(provider_id) or inferred_provider

        if not api_key:
            if provider_id and provider_id in server_api_keys:
                api_key = server_api_keys[provider_id]
            elif inferred_provider_id and inferred_provider_id in server_api_keys:
                api_key = server_api_keys[inferred_provider_id]
        if not base_url and provider:
            base_url = provider.get("defaultBaseUrl", "")

        deep_research = bool_from_payload(data.get("deep_research"), False)
        visual_critic = bool_from_payload(data.get("visual_critic"), False)
        repair_enabled = bool_from_payload(data.get("repair_enabled"), False)
        template_id = data.get("template_id")
        user_id = get_user_id()
        notes = resolve_ppt_generation_notes(data, user_id)

        if not topic:
            return jsonify({"error": "课程主题不能为空"}), 400

        def generate():
            from ppt_engine.pipeline import PPTPipeline
            from ppt_engine.sse_bridge import SSEBridge

            pipeline = PPTPipeline()
            bridge = SSEBridge()
            bridge.run(pipeline.generate(
                topic,
                provider=provider_id or "deepseek",
                model=model,
                api_key=api_key,
                base_url=base_url,
                user_id=user_id,
                language=language,
                num_slides=num_slides,
                style=style,
                canvas_format=canvas_format,
                detail_level=detail_level,
                deep_research=deep_research,
                visual_critic=visual_critic,
                repair_enabled=repair_enabled,
                template_id=template_id,
                notes=notes,
            ))

            try:
                for event in bridge.events():
                    if isinstance(event, str):
                        yield event
                        continue
                    event_data = {
                        "type": f"ppt_svg_{event.status}",
                        "stage": event.stage,
                        "message": event.message,
                        "progress": event.progress,
                    }
                    if event.data:
                        if "svg" in event.data:
                            event_data["slide"] = {
                                "page": event.data["page"],
                                "svg": event.data["svg"],
                            }
                        for key in (
                            "output_path", "job_id", "total_slides",
                            "slide_count", "pptx_filename", "error",
                        ):
                            if key in event.data:
                                event_data[key] = event.data[key]
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'ppt_svg_error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        response = Response(generate(), mimetype="text/event-stream")
        response.headers["X-Accel-Buffering"] = "no"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @bp.get("/api/ppt-svg/preview/<job_id>/<int:slide_num>")
    def ppt_svg_preview(job_id, slide_num):
        user_id = get_user_id()
        base_dir, _owner_user_id = resolve_svg_job_dir(job_id, user_id)
        if not base_dir:
            return jsonify({"error": "任务不存在"}), 404
        svg_dir = os.path.join(base_dir, "svg_final")
        if not os.path.exists(svg_dir):
            svg_dir = os.path.join(base_dir, "svg_output")
        if not os.path.exists(svg_dir):
            return jsonify({"error": "未找到生成结果"}), 404

        svg_files = sorted(glob.glob(os.path.join(svg_dir, "*.svg")))
        if slide_num < 1 or slide_num > len(svg_files):
            return jsonify({"error": f"页码 {slide_num} 超出范围 (1-{len(svg_files)})"}), 404

        svg_path = svg_files[slide_num - 1]
        with open(svg_path, "r", encoding="utf-8") as f:
            svg_content = f.read()
        return jsonify({
            "job_id": job_id,
            "page": slide_num,
            "total_pages": len(svg_files),
            "svg": svg_content,
            "filename": os.path.basename(svg_path),
        })

    @bp.get("/api/ppt-svg/preview-all/<job_id>")
    def ppt_svg_preview_all(job_id):
        user_id = get_user_id()
        base_dir, _owner_user_id = resolve_svg_job_dir(job_id, user_id)
        if not base_dir:
            return jsonify({"error": "任务不存在"}), 404
        svg_dir = os.path.join(base_dir, "svg_final")
        if not os.path.exists(svg_dir):
            svg_dir = os.path.join(base_dir, "svg_output")
        if not os.path.exists(svg_dir):
            return jsonify({"error": "未找到生成结果"}), 404

        slides = []
        svg_files = sorted(glob.glob(os.path.join(svg_dir, "*.svg")))
        for i, svg_path in enumerate(svg_files, 1):
            with open(svg_path, "r", encoding="utf-8") as f:
                slides.append({
                    "page": i,
                    "svg": f.read(),
                    "filename": os.path.basename(svg_path),
                })
        return jsonify({"job_id": job_id, "total_pages": len(slides), "slides": slides})

    @bp.get("/api/ppt-svg/download/<job_id>")
    def ppt_svg_download(job_id):
        user_id = get_user_id()
        base_dir, _owner_user_id = resolve_svg_job_dir(job_id, user_id)
        if not base_dir:
            return jsonify({"error": "任务不存在"}), 404

        pptist_pptx = os.path.join(base_dir, "pptist", "current.pptx")
        if os.path.isfile(pptist_pptx):
            resp = send_file(
                pptist_pptx,
                as_attachment=True,
                download_name=os.path.basename(pptist_pptx),
                mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            return resp

        exports_dir = os.path.join(base_dir, "exports")
        if not os.path.exists(exports_dir):
            return jsonify({"error": "未找到导出文件"}), 404
        pptx_files = sorted(glob.glob(os.path.join(exports_dir, "*.pptx")), key=os.path.getmtime, reverse=True)
        if not pptx_files:
            return jsonify({"error": "PPTX 文件不存在"}), 404

        pptx_path = next((f for f in pptx_files if "pptist" in os.path.basename(f).lower()), pptx_files[0])
        resp = send_file(
            pptx_path,
            as_attachment=True,
            download_name=os.path.basename(pptx_path),
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resp

    @bp.get("/api/ppt-svg/list")
    def ppt_svg_list():
        user_id = get_user_id()
        base_dir = scan_dir(os.path.join(backend_dir, "generated_svg_ppt"), user_id)
        if not os.path.exists(base_dir):
            return jsonify({"jobs": []})

        jobs = []
        for job_dir in sorted(os.listdir(base_dir), reverse=True):
            meta_path = os.path.join(base_dir, job_dir, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                exports_dir = os.path.join(base_dir, job_dir, "exports")
                has_pptx = os.path.exists(exports_dir) and any(
                    f.endswith(".pptx") for f in os.listdir(exports_dir)
                ) if os.path.exists(exports_dir) else False
                meta["has_pptx"] = has_pptx
                jobs.append(meta)
        return jsonify({"jobs": jobs})

    @bp.get("/api/pptist/preview/<job_id>/deck")
    def pptist_preview_deck(job_id):
        user_id = get_user_id()
        if ".." in job_id or "/" in job_id or "\\" in job_id:
            return jsonify({"error": "非法 job_id"}), 400
        job_dir, owner_user_id = resolve_svg_job_dir(job_id, user_id)
        if not job_dir:
            return jsonify({"error": "任务不存在"}), 404

        deck_path = os.path.join(job_dir, "pptist", "deck.json")
        if os.path.exists(deck_path):
            try:
                with open(deck_path, "r", encoding="utf-8") as f:
                    deck = json.load(f)
                deck.setdefault("source", {})
                deck["source"]["kind"] = "preview"
                deck["source"]["id"] = job_id
                deck["source"]["saved_deck"] = True
                uid_qs = f"?user_id={owner_user_id}" if owner_user_id != "anonymous" else ""
                deck["source"]["source_pptx_url"] = f"/api/ppt-svg/download/{job_id}{uid_qs}"
                return jsonify(deck)
            except (json.JSONDecodeError, OSError):
                pass

        uid_qs = f"?user_id={owner_user_id}" if owner_user_id != "anonymous" else ""
        return jsonify({
            "title": os.path.basename(job_dir),
            "width": 1280,
            "height": 720,
            "theme": None,
            "slides": [],
            "source": {
                "kind": "preview",
                "id": job_id,
                "saved_deck": False,
                "source_pptx_url": f"/api/ppt-svg/download/{job_id}{uid_qs}",
                "fallback_slides": [],
            },
        })

    @bp.put("/api/pptist/preview/<job_id>/deck")
    def pptist_save_deck(job_id):
        user_id = get_user_id()
        if ".." in job_id or "/" in job_id or "\\" in job_id:
            return jsonify({"error": "非法 job_id"}), 400
        job_dir, _owner_user_id = resolve_svg_job_dir(job_id, user_id)
        if not job_dir:
            return jsonify({"error": "任务不存在"}), 404

        payload = request.get_json(silent=True) or {}
        deck = {
            "title": payload.get("title", ""),
            "width": payload.get("width", 1280),
            "height": payload.get("height", 720),
            "theme": payload.get("theme"),
            "slides": payload.get("slides", []),
            "updated_at": datetime.now().isoformat(),
        }
        pptist_dir = os.path.join(job_dir, "pptist")
        os.makedirs(pptist_dir, exist_ok=True)
        deck_path = os.path.join(pptist_dir, "deck.json")

        try:
            with open(deck_path, "w", encoding="utf-8") as f:
                json.dump(deck, f, ensure_ascii=False, indent=2)
            return jsonify({
                "status": "saved",
                "slide_count": len(deck.get("slides", [])),
                "updated_at": deck["updated_at"],
            })
        except Exception as e:
            return jsonify({"error": f"保存失败: {e}"}), 500

    @bp.post("/api/pptist/preview/<job_id>/export")
    def pptist_export_deck(job_id):
        user_id = get_user_id()
        if ".." in job_id or "/" in job_id or "\\" in job_id:
            return jsonify({"error": "非法 job_id"}), 400
        job_dir, _owner_user_id = resolve_svg_job_dir(job_id, user_id)
        if not job_dir:
            return jsonify({"error": "任务不存在"}), 404
        if "file" not in request.files:
            return jsonify({"error": "没有上传文件"}), 400

        file = request.files["file"]
        if file.filename == "" or not file.filename.endswith(".pptx"):
            return jsonify({"error": "需要 PPTX 文件"}), 400

        pptist_dir = os.path.join(job_dir, "pptist")
        os.makedirs(pptist_dir, exist_ok=True)
        current_path = os.path.join(pptist_dir, "current.pptx")
        file.save(current_path)

        exports_dir = os.path.join(job_dir, "exports")
        os.makedirs(exports_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(exports_dir, f"presentation_pptist_{timestamp}.pptx")
        shutil.copy2(current_path, export_path)

        meta_path = os.path.join(job_dir, "metadata.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["output_path"] = export_path
                meta["pptx_filename"] = os.path.basename(export_path)
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return jsonify({"status": "complete", "output_path": export_path, "slide_count": 0})

    @bp.delete("/api/ppt-svg/<job_id>")
    def ppt_svg_delete(job_id):
        user_id = get_user_id()
        base_dir = scan_dir(os.path.join(backend_dir, "generated_svg_ppt"), user_id)
        if ".." in job_id or "/" in job_id or "\\" in job_id:
            return jsonify({"success": False, "error": "非法 job_id"}), 400

        job_path = os.path.join(base_dir, job_id)
        if not os.path.exists(job_path):
            return jsonify({"success": False, "error": "任务不存在"}), 404

        abs_base = os.path.abspath(base_dir)
        abs_job = os.path.abspath(job_path)
        if not abs_job.startswith(abs_base):
            return jsonify({"success": False, "error": "非法路径"}), 403

        try:
            shutil.rmtree(abs_job)
            logger.info(f"[PPT-SVG] 已删除任务目录: {abs_job}")
            return jsonify({"success": True, "message": "已删除"})
        except Exception as e:
            logger.error(f"[PPT-SVG] 删除任务失败: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.post("/api/ppt-svg/clear-all")
    def ppt_svg_clear_all():
        data = request.json or {}
        confirm = data.get("confirm", False)
        if not confirm:
            return jsonify({"success": False, "error": "需要确认清空操作"}), 400
        user_id = get_user_id()

        base_dir = scan_dir(os.path.join(backend_dir, "generated_svg_ppt"), user_id)
        if not os.path.exists(base_dir):
            return jsonify({"success": True, "message": "已清空"})

        try:
            for job_id in os.listdir(base_dir):
                job_path = os.path.join(base_dir, job_id)
                abs_base = os.path.abspath(base_dir)
                abs_job = os.path.abspath(job_path)
                if abs_job.startswith(abs_base) and os.path.isdir(abs_job):
                    shutil.rmtree(abs_job)
            logger.info("[PPT-SVG] 已清空所有 SVG PPT 历史")
            return jsonify({"success": True, "message": "已清空"})
        except Exception as e:
            logger.error(f"[PPT-SVG] 清空失败: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.get("/api/templates/list")
    def templates_list():
        try:
            from ppt_engine.template_manager import list_templates
            templates = list_templates()
            return jsonify({
                "templates": [
                    {
                        "template_id": t.template_id,
                        "label": t.label,
                        "summary": t.summary,
                        "tone": t.tone,
                        "theme_mode": t.theme_mode,
                        "category": t.category,
                        "keywords": t.keywords,
                        "slide_count": t.slide_count,
                    }
                    for t in templates
                ]
            })
        except Exception as e:
            logger.error(f"[TEMPLATES] 列表加载失败: {e}")
            return jsonify({"templates": []})

    @bp.get("/api/templates/preview/<template_id>")
    def template_preview(template_id):
        try:
            from ppt_engine.template_manager import load_template
            tmpl = load_template(template_id)
            if tmpl is None:
                return jsonify({"pages": {}, "label": ""})
            pages = {}
            if tmpl.cover_svg:
                pages["cover"] = tmpl.cover_svg
            if tmpl.chapter_svg:
                pages["chapter"] = tmpl.chapter_svg
            if tmpl.content_svg:
                pages["content"] = tmpl.content_svg
            if tmpl.ending_svg:
                pages["ending"] = tmpl.ending_svg
            if tmpl.toc_svg:
                pages["toc"] = tmpl.toc_svg
            return jsonify({"pages": pages, "label": tmpl.info.label})
        except Exception as e:
            logger.error(f"[TEMPLATES] 预览加载失败: {e}")
            return jsonify({"pages": {}, "label": ""})

    return bp
