from __future__ import annotations

import glob
import json
import os
import shutil
from collections.abc import Callable
from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, request, send_file


def _generated_dirs() -> list[str]:
    return [
        "generated_ppt",
        "generated_lectures",
        "generated_content",
        "generated_outlines",
        "generated_speeches",
        "generated_exercises",
        "generated_quizzes",
        "generated_cards",
        "generated_mindmaps",
    ]


def create_file_library_blueprint(
    *,
    get_user_id: Callable[[], str],
    backend_dir: str,
    generators_dir: str,
    scan_dir: Callable[[str, str], str],
    logger: Any,
) -> Blueprint:
    bp = Blueprint("file_library", __name__, url_prefix="/api/files")

    def authorized_file(file_path: str) -> tuple[str, bool]:
        """Resolve a path and require it to live under this user's generated roots."""
        candidate = os.path.realpath(os.path.abspath(file_path or ""))
        user_id = get_user_id()
        roots = [scan_dir(os.path.join(generators_dir, d), user_id) for d in _generated_dirs()]
        roots.append(scan_dir(os.path.join(backend_dir, "generated_svg_ppt"), user_id))
        for root in roots:
            resolved_root = os.path.realpath(os.path.abspath(root))
            try:
                if os.path.commonpath([candidate, resolved_root]) == resolved_root:
                    return candidate, True
            except ValueError:
                continue
        return candidate, False

    @bp.get("")
    def get_files():
        """获取所有生成的文件列表"""
        logger.info("[FILES] 获取文件列表")
        user_id = get_user_id()
        files = []

        ppt_dir = scan_dir(os.path.join(generators_dir, "generated_ppt"), user_id)
        if os.path.exists(ppt_dir):
            for f in os.listdir(ppt_dir):
                if f.endswith(".pptx") and not f.startswith("~$"):
                    filepath = os.path.join(ppt_dir, f)
                    stat = os.stat(filepath)
                    files.append({
                        "id": f"ppt_{f}",
                        "name": f,
                        "type": "ppt",
                        "type_label": "PPT",
                        "path": filepath,
                        "size": stat.st_size,
                        "size_formatted": f"{stat.st_size / 1024:.1f} KB",
                        "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "icon": "📊",
                        "slide_count": None,
                    })

        svg_ppt_dir = scan_dir(os.path.join(backend_dir, "generated_svg_ppt"), user_id)
        if os.path.exists(svg_ppt_dir):
            for job_dir in os.listdir(svg_ppt_dir):
                job_path = os.path.join(svg_ppt_dir, job_dir)
                if not os.path.isdir(job_path) or job_dir.startswith("temp_"):
                    continue
                exports_dir = os.path.join(job_path, "exports")
                if not os.path.exists(exports_dir):
                    continue
                pptx_files = [
                    f for f in os.listdir(exports_dir)
                    if f.endswith(".pptx") and not f.startswith("~$")
                ]
                if not pptx_files:
                    continue
                f = pptx_files[0]
                filepath = os.path.join(exports_dir, f)
                stat = os.stat(filepath)
                topic = None
                meta_path = os.path.join(job_path, "metadata.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as mf:
                            meta = json.load(mf)
                        topic = meta.get("topic")
                    except Exception:
                        pass
                display_name = f"{topic}.pptx" if topic else f
                slide_count = None
                svg_final_dir = os.path.join(job_path, "svg_final")
                if os.path.exists(svg_final_dir):
                    slide_count = len([x for x in os.listdir(svg_final_dir) if x.endswith(".svg")])
                elif os.path.exists(exports_dir):
                    slide_count = len(glob.glob(os.path.join(exports_dir, "*.pptx"))) or None
                files.append({
                    "id": f"svg_ppt_{job_dir}",
                    "name": display_name,
                    "type": "ppt",
                    "type_label": "PPT",
                    "job_id": job_dir,
                    "path": filepath,
                    "size": stat.st_size,
                    "size_formatted": f"{stat.st_size / 1024:.1f} KB",
                    "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "icon": "📊",
                    "slide_count": slide_count,
                })

        scan_specs = [
            ("generated_lectures", (".md",), "lecture", "讲义", "📚"),
            ("generated_outlines", (".md", ".docx"), "outline", "课程大纲", "📋"),
            ("generated_speeches", (".md", ".docx"), "speech", "讲稿", "🎤"),
            ("generated_exercises", (".md", ".docx"), "exercise", "习题集", "✏️"),
            ("generated_quizzes", (".md", ".docx"), "quiz", "课堂测验", "❓"),
            ("generated_cards", (".md", ".docx"), "card", "知识卡片", "🃏"),
            ("generated_mindmaps", (".md",), "mindmap", "思维导图", "🧠"),
        ]
        for dir_name, suffixes, item_type, type_label, icon in scan_specs:
            target_dir = scan_dir(os.path.join(generators_dir, dir_name), user_id)
            if not os.path.exists(target_dir):
                continue
            for f in os.listdir(target_dir):
                if f.endswith(suffixes):
                    filepath = os.path.join(target_dir, f)
                    stat = os.stat(filepath)
                    files.append({
                        "id": f"{item_type}_{f}",
                        "name": f,
                        "type": "knowledge_card" if item_type == "card" else item_type,
                        "type_label": type_label,
                        "path": filepath,
                        "size": stat.st_size,
                        "size_formatted": f"{stat.st_size / 1024:.1f} KB",
                        "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "icon": icon,
                    })

        content_text_dir = scan_dir(os.path.join(generators_dir, "generated_content/text"), user_id)
        if os.path.exists(content_text_dir):
            for f in os.listdir(content_text_dir):
                if f.endswith(".md"):
                    filepath = os.path.join(content_text_dir, f)
                    stat = os.stat(filepath)
                    type_label = "视频脚本" if f.startswith("video_script") else "小红书文案"
                    files.append({
                        "id": f"content_text_{f}",
                        "name": f,
                        "type": "content_text",
                        "type_label": type_label,
                        "path": filepath,
                        "size": stat.st_size,
                        "size_formatted": f"{stat.st_size / 1024:.1f} KB",
                        "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "icon": "📝",
                    })

        content_audio_dir = scan_dir(os.path.join(generators_dir, "generated_content/audio"), user_id)
        if os.path.exists(content_audio_dir):
            for f in os.listdir(content_audio_dir):
                if f.endswith(".wav"):
                    filepath = os.path.join(content_audio_dir, f)
                    stat = os.stat(filepath)
                    files.append({
                        "id": f"content_audio_{f}",
                        "name": f,
                        "type": "content_audio",
                        "type_label": "音频",
                        "path": filepath,
                        "size": stat.st_size,
                        "size_formatted": f"{stat.st_size / 1024:.1f} KB",
                        "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "icon": "🔊",
                    })

        content_image_dir = scan_dir(os.path.join(generators_dir, "generated_content/images"), user_id)
        if os.path.exists(content_image_dir):
            for f in os.listdir(content_image_dir):
                if f.endswith((".jpeg", ".jpg", ".png")):
                    filepath = os.path.join(content_image_dir, f)
                    stat = os.stat(filepath)
                    files.append({
                        "id": f"content_image_{f}",
                        "name": f,
                        "type": "content_image",
                        "type_label": "封面图",
                        "path": filepath,
                        "size": stat.st_size,
                        "size_formatted": f"{stat.st_size / 1024:.1f} KB",
                        "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "icon": "🖼️",
                    })

        files.sort(key=lambda x: x["created"], reverse=True)
        logger.info(f"[FILES] 找到 {len(files)} 个文件")
        return jsonify({"files": files})

    @bp.post("/delete")
    def delete_file():
        data = request.json or {}
        file_path = data.get("path", "")
        logger.info(f"[FILES] 删除文件请求: {file_path}")

        if not file_path or not os.path.exists(file_path):
            return jsonify({"success": False, "error": "文件不存在"}), 404

        abs_path, is_allowed = authorized_file(file_path)

        if not is_allowed:
            logger.warning(f"[FILES] 非法删除路径: {file_path}")
            return jsonify({"success": False, "error": "无权删除此文件"}), 403

        try:
            os.remove(abs_path)
            logger.info(f"[FILES] 文件已删除: {file_path}")
            return jsonify({"success": True, "message": "文件已删除"})
        except Exception as e:
            logger.error(f"[FILES] 删除失败: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.post("/rename")
    def rename_file():
        data = request.json or {}
        old_path = data.get("path", "")
        new_name = data.get("new_name", "")
        user_id = get_user_id()
        logger.info(f"[FILES] 重命名文件: {old_path} -> {new_name} (user: {user_id})")

        if not old_path or not os.path.exists(old_path):
            return jsonify({"success": False, "error": "文件不存在"}), 404
        if not new_name or "/" in new_name or "\\" in new_name:
            return jsonify({"success": False, "error": "无效的文件名"}), 400

        abs_old, is_allowed = authorized_file(old_path)

        if not is_allowed:
            logger.warning(f"[FILES] 非法重命名路径: {old_path}")
            return jsonify({"success": False, "error": "无权重命名此文件"}), 403

        try:
            old_ext = os.path.splitext(abs_old)[1]
            if not new_name.endswith(old_ext):
                new_name += old_ext
            new_path = os.path.join(os.path.dirname(abs_old), new_name)
            if os.path.exists(new_path):
                return jsonify({"success": False, "error": "目标文件已存在"}), 400
            os.rename(abs_old, new_path)
            logger.info(f"[FILES] 文件已重命名: {abs_old} -> {new_path}")
            return jsonify({"success": True, "message": "文件已重命名", "new_path": new_path})
        except Exception as e:
            logger.error(f"[FILES] 重命名失败: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @bp.post("/clear")
    def clear_all_files():
        data = request.json or {}
        confirm = data.get("confirm", False)
        user_id = get_user_id()
        if not confirm:
            return jsonify({"success": False, "error": "需要确认清空操作"}), 400

        logger.info(f"[FILES] 收到清空文件请求 (user: {user_id})")
        allowed_dirs = [
            "generated_ppt", "generated_lectures", "generated_content",
            "generated_outlines", "generated_speeches", "generated_exercises",
            "generated_quizzes", "generated_cards", "generated_mindmaps",
            "generated_svg_ppt",
        ]
        deleted_count = 0
        errors = []
        for dir_name in allowed_dirs:
            if dir_name == "generated_svg_ppt":
                dir_path = scan_dir(os.path.join(backend_dir, "generated_svg_ppt"), user_id)
            else:
                dir_path = scan_dir(os.path.join(generators_dir, dir_name), user_id)
            if os.path.exists(dir_path):
                try:
                    if dir_name == "generated_svg_ppt":
                        for job_id in os.listdir(dir_path):
                            job_path = os.path.join(dir_path, job_id)
                            abs_job = os.path.abspath(job_path)
                            if os.path.isdir(abs_job) and abs_job.startswith(os.path.abspath(dir_path)):
                                shutil.rmtree(abs_job)
                                deleted_count += 1
                    else:
                        for root, _dirs, files in os.walk(dir_path):
                            for f in files:
                                file_path = os.path.join(root, f)
                                if os.path.isfile(file_path):
                                    try:
                                        os.remove(file_path)
                                        deleted_count += 1
                                    except Exception as e:
                                        errors.append(f"删除 {file_path} 失败: {e}")
                except Exception as e:
                    errors.append(f"清空目录 {dir_path} 失败: {e}")

        logger.info(f"[FILES] 清空完成，共删除 {deleted_count} 个文件")
        if errors:
            logger.error(f"[FILES] 清空过程中的错误: {errors}")
        return jsonify({
            "success": True,
            "message": f"已清空 {deleted_count} 个文件",
            "deleted_count": deleted_count,
            "errors": errors,
        })

    @bp.get("/download")
    def download_file():
        filepath = request.args.get("path", "")
        if not filepath:
            return jsonify({"error": "缺少 path 参数"}), 400

        abs_path, is_allowed = authorized_file(filepath)
        if not is_allowed:
            return jsonify({"error": "文件不在允许的目录中"}), 403
        if not os.path.isfile(abs_path):
            return jsonify({"error": "文件不存在"}), 404
        return send_file(abs_path, as_attachment=True, download_name=os.path.basename(abs_path))

    @bp.get("/read")
    def read_file():
        filepath = request.args.get("path", "")
        if not filepath:
            return jsonify({"error": "缺少 path 参数"}), 400

        abs_path, is_allowed = authorized_file(filepath)
        if not is_allowed:
            return jsonify({"error": "非法路径"}), 403
        if not os.path.isfile(abs_path):
            return jsonify({"error": "文件不存在"}), 404

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            return jsonify({"content": content, "filename": os.path.basename(abs_path)})
        except UnicodeDecodeError:
            return jsonify({"error": "文件不是文本格式"}), 400

    return bp
