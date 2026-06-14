from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify


def create_basic_blueprint() -> Blueprint:
    bp = Blueprint("basic", __name__)

    @bp.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "service": "ZhichuangSpace API",
            "version": "1.0.0",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    @bp.route("/api/info", methods=["GET"])
    def api_info():
        return jsonify({
            "name": "ZhichuangSpace API",
            "version": "1.0.0",
            "description": "智创空间 - 基于多智能体交互的智慧课堂平台后端服务",
            "endpoints": [
                {"path": "/api/health", "method": "GET", "description": "健康检查"},
                {"path": "/api/info", "method": "GET", "description": "API 信息"},
                {"path": "/api/chat", "method": "POST", "description": "非流式聊天"},
                {"path": "/api/chat/stream", "method": "POST", "description": "流式聊天（SSE）"},
                {"path": "/api/clear", "method": "POST", "description": "清空对话历史"},
                {"path": "/api/history", "method": "GET", "description": "获取对话历史"},
                {"path": "/api/models", "method": "GET", "description": "可用模型列表"},
                {"path": "/api/settings", "method": "GET/POST", "description": "设置读写"},
                {"path": "/api/files", "method": "GET", "description": "文件列表"},
                {"path": "/api/files/delete", "method": "POST", "description": "删除文件"},
                {"path": "/api/files/rename", "method": "POST", "description": "重命名文件"},
                {"path": "/api/files/clear", "method": "POST", "description": "清空所有文件"},
                {"path": "/api/memory", "method": "GET", "description": "记忆摘要"},
                {"path": "/api/memory/save", "method": "POST", "description": "保存记忆"},
                {"path": "/api/memory/clear", "method": "POST", "description": "清除长期记忆"},
                {"path": "/api/memory/clear-daily", "method": "POST", "description": "清除会话记录"},
                {"path": "/api/memory/search", "method": "GET", "description": "搜索记忆"},
                {"path": "/api/graphic/image/<filename>", "method": "GET", "description": "封面图"},
                {"path": "/api/video/audio/<filename>", "method": "GET", "description": "音频文件"},
            ],
        })

    return bp
