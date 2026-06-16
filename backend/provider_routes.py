from __future__ import annotations

import asyncio
import base64
from typing import Any, Callable

import requests
from deep_translator import GoogleTranslator
from flask import Blueprint, jsonify, request


def create_provider_blueprint(
    *,
    providers: dict,
    tts_providers: dict,
    server_api_keys: dict,
    get_provider_for_model: Callable[[str], tuple[str, dict | None, dict | None]],
) -> Blueprint:
    bp = Blueprint("providers", __name__)

    @bp.route("/api/models", methods=["GET"])
    def get_models():
        models = []
        for pid, provider in providers.items():
            for model in provider["models"]:
                models.append({
                    "id": model["id"],
                    "name": model["name"],
                    "description": f"{provider['name']} · {model['id']}",
                    "provider": pid,
                })
        return jsonify({"models": models})

    @bp.route("/api/providers", methods=["GET"])
    def get_providers():
        result = {}
        for pid, provider in providers.items():
            result[pid] = {
                "id": provider["id"],
                "name": provider["name"],
                "type": provider["type"],
                "defaultBaseUrl": provider["defaultBaseUrl"],
                "models": provider["models"],
                "requiresApiKey": provider["requiresApiKey"],
                "isServerConfigured": pid in server_api_keys,
            }
        return jsonify({"providers": result})

    @bp.route("/api/tts-providers", methods=["GET"])
    def get_tts_providers():
        result = {}
        for pid, provider in tts_providers.items():
            result[pid] = {
                "id": provider["id"],
                "name": provider["name"],
                "type": provider["type"],
                "defaultBaseUrl": provider["defaultBaseUrl"],
                "models": provider["models"],
                "voices": provider.get("voices", []),
                "requiresApiKey": provider["requiresApiKey"],
                "isServerConfigured": pid in server_api_keys,
            }
        return jsonify({"providers": result})

    @bp.route("/api/tts-test", methods=["POST"])
    def tts_test():
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "请求数据为空"}), 400
        provider_id = (data.get("providerId") or data.get("provider") or data.get("provider_id") or "").strip()
        model = (data.get("model") or "").strip()
        voice = (data.get("voice") or "").strip()
        text = (data.get("text") or "").strip()
        api_key = data.get("api_key") or data.get("apiKey") or ""
        base_url = (data.get("base_url") or data.get("baseUrl") or "").strip()

        provider = tts_providers.get(provider_id)
        if not text:
            return jsonify({"success": False, "message": "请输入测试文本"}), 400
        if not provider:
            return jsonify({"success": False, "message": "未知 TTS provider"}), 400
        if not api_key and provider_id in server_api_keys:
            api_key = server_api_keys[provider_id]
        if not base_url:
            base_url = provider.get("defaultBaseUrl", "")
        if not base_url and provider_id != "edge-tts":
            return jsonify({"success": False, "message": "无法确定 API 地址"}), 400
        if not api_key and provider_id not in ("edge-tts",):
            return jsonify({"success": False, "message": "请填写 API Key"}), 400

        if provider_id in {"openai-tts", "glm-tts"}:
            try:
                url = f"{base_url.rstrip('/')}/audio/speech"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": model or provider.get("models", [{}])[0].get("id", ""),
                    "input": text,
                    "voice": voice or "alloy",
                    "response_format": "mp3",
                }
                if provider_id == "glm-tts":
                    payload.update({
                        "voice": voice or "tongtong",
                        "speed": 1.0,
                        "volume": 1.0,
                        "response_format": "wav",
                    })
                resp = requests.post(url, json=payload, headers=headers, timeout=30)
                if resp.status_code == 200:
                    audio_b64 = base64.b64encode(resp.content).decode("utf-8")
                    return jsonify({"success": True, "audio": audio_b64, "format": "wav" if provider_id == "glm-tts" else "mp3"})
                error_data = _safe_json(resp)
                msg = error_data.get("error", {}).get("message", "") or resp.text[:500]
                return jsonify({"success": False, "message": msg})
            except Exception as exc:
                return jsonify({"success": False, "message": str(exc)})

        if provider_id == "mimo-tts":
            try:
                from openai import OpenAI as OpenAIClient

                client = OpenAIClient(api_key=api_key, base_url=base_url)
                response = client.chat.completions.create(
                    model=model or "mimo-v2.5-tts",
                    messages=[
                        {"role": "user", "content": "请朗读以下内容"},
                        {"role": "assistant", "content": text},
                    ],
                    audio={"format": "mp3", "voice": voice or "mimo_default"},
                )
                audio_data = response.choices[0].message.audio.data
                return jsonify({"success": True, "audio": audio_data, "format": "mp3"})
            except Exception as exc:
                return jsonify({"success": False, "message": str(exc)})

        if provider_id == "edge-tts":
            try:
                import edge_tts

                voice_info = next(
                    (item for item in provider.get("voices", []) if item["id"] == voice),
                    None,
                )
                target_lang = voice_info.get("lang", "zh-CN") if voice_info else "zh-CN"
                text_to_speak = text
                if target_lang != "zh-CN":
                    try:
                        text_to_speak = GoogleTranslator(
                            source="zh-CN",
                            target=target_lang,
                        ).translate(text)
                    except Exception:
                        pass

                async def _generate():
                    communicate = edge_tts.Communicate(
                        text_to_speak,
                        voice or "zh-CN-XiaoxiaoNeural",
                    )
                    audio_buffer = b""
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_buffer += chunk["data"]
                    return audio_buffer

                audio_data = asyncio.run(_generate())
                audio_b64 = base64.b64encode(audio_data).decode("utf-8")
                return jsonify({"success": True, "audio": audio_b64, "format": "mp3"})
            except Exception as exc:
                return jsonify({"success": False, "message": str(exc)})

        return jsonify({"success": False, "message": f"不支持的 TTS 类型: {provider_id}"})

    @bp.route("/api/verify-model", methods=["POST"])
    def verify_model():
        data = request.json or {}
        api_key = (data.get("apiKey") or "").strip()
        base_url = (data.get("baseUrl") or "").strip()
        model_id = (data.get("model") or "").strip()
        provider_id = (data.get("providerId") or "").strip()
        provider_type = (data.get("providerType") or "openai").strip()

        if not api_key and provider_id in server_api_keys:
            api_key = server_api_keys[provider_id]
        if not api_key:
            return jsonify({"success": False, "message": "请填写 API Key"}), 400
        if not model_id:
            return jsonify({"success": False, "message": "请选择模型"}), 400
        if not base_url and provider_id in providers:
            base_url = providers[provider_id]["defaultBaseUrl"]
        if not base_url and provider_id in tts_providers:
            base_url = tts_providers[provider_id]["defaultBaseUrl"]
        if not base_url:
            return jsonify({"success": False, "message": "无法确定 API 地址"}), 400

        try:
            if provider_type == "minimax":
                return _verify_minimax(api_key, base_url, model_id)
            if provider_type == "mimo-tts":
                return _verify_minimax_tts(api_key, base_url, model_id)
            if provider_type == "openai-tts":
                return _verify_openai_tts(api_key, base_url, model_id, provider_id)
            if provider_type == "anthropic":
                return _verify_anthropic(api_key, base_url, model_id)
            return _verify_openai_compatible(api_key, base_url, model_id, provider_id)
        except Exception as exc:
            return jsonify({"success": False, "message": str(exc)})

    return bp


def _verify_openai_compatible(api_key: str, base_url: str, model_id: str, provider_id: str = ""):
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=15)
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": 'Say "OK" if you can hear me.'}],
            max_tokens=64,
        )
        text = response.choices[0].message.content or ""
        return jsonify({"success": True, "message": "连接成功", "response": text.strip()})
    except Exception as exc:
        return jsonify({"success": False, "message": _friendly_llm_error(str(exc), provider_id, base_url)})


def _verify_anthropic(api_key: str, base_url: str, model_id: str):
    try:
        resp = requests.post(
            f"{base_url}/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model_id,
                "max_tokens": 64,
                "messages": [{"role": "user", "content": 'Say "OK" if you can hear me.'}],
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            text = "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
            return jsonify({"success": True, "message": "连接成功", "response": text.strip()})
        return jsonify({"success": False, "message": _response_error_message(resp)})
    except requests.exceptions.Timeout:
        return jsonify({"success": False, "message": "连接超时，请检查网络或 Base URL"})
    except requests.exceptions.ConnectionError:
        return jsonify({"success": False, "message": "无法连接到 API 服务器，请检查 Base URL"})
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)})


def _verify_minimax_tts(api_key: str, base_url: str, model_id: str):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "请朗读"},
            {"role": "assistant", "content": "OK"},
        ],
        "max_tokens": 64,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return jsonify({"success": True, "message": "连接成功"})
        if resp.status_code in {401, 403}:
            return jsonify({"success": False, "message": "API Key 无效或已过期"})
        if resp.status_code == 404:
            return jsonify({"success": False, "message": f"端点不存在 (404)，请检查 Base URL: {url}"})
        return jsonify({"success": False, "message": _response_error_message(resp, limit=200)})
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)})


def _verify_openai_tts(api_key: str, base_url: str, model_id: str, provider_id: str = ""):
    url = f"{base_url.rstrip('/')}/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "input": "OK",
        "voice": "alloy",
        "response_format": "mp3",
    }
    if provider_id == "glm-tts":
        payload.update({
            "voice": "tongtong",
            "speed": 1.0,
            "volume": 1.0,
            "response_format": "wav",
        })
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            return jsonify({"success": True, "message": "连接成功"})
        if resp.status_code in {401, 403}:
            return jsonify({"success": False, "message": "API Key 无效或已过期"})
        if resp.status_code == 404:
            return jsonify({"success": False, "message": f"端点不存在 (404)，请检查 Base URL: {url}"})
        return jsonify({"success": False, "message": _response_error_message(resp, limit=200)})
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)})


def _verify_minimax(api_key: str, base_url: str, model_id: str):
    from openai import OpenAI

    base = base_url.rsplit("/chat/completions", 1)[0] if base_url.rstrip("/").endswith("/chat/completions") else base_url
    client = OpenAI(api_key=api_key, base_url=base, timeout=15)
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": 'Say "OK" if you can hear me.'}],
            max_tokens=64,
        )
        text = response.choices[0].message.content or ""
        if not text.strip():
            return jsonify({"success": False, "message": "返回内容为空，请检查 API Key 或模型 ID"})
        return jsonify({"success": True, "message": "连接成功", "response": text.strip()})
    except Exception as exc:
        return jsonify({"success": False, "message": _friendly_llm_error(str(exc), "", base_url)})


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return {}


def _response_error_message(resp, limit: int = 500) -> str:
    error_data = _safe_json(resp)
    return error_data.get("error", {}).get("message", "") or resp.text[:limit]


def _friendly_llm_error(error_str: str, provider_id: str = "", base_url: str = "") -> str:
    if "401" in error_str or "Unauthorized" in error_str or "Incorrect API key" in error_str:
        if provider_id.startswith("xfyun") or "xf-yun.com" in base_url:
            return "讯飞鉴权失败：请填写控制台生成的 APIpassword，或 AK:SK；同时确认当前账号已开通所选 X2/v2 接口权限。"
        return "API Key 无效或已过期"
    if "404" in error_str or "not found" in error_str.lower():
        return "模型未找到，请检查模型 ID 或 Base URL"
    if "429" in error_str:
        return "API 请求频率超限，请稍后再试"
    if "timeout" in error_str.lower() or "timed out" in error_str.lower():
        return "连接超时，请检查网络或 Base URL"
    if "Connection" in error_str or "ENOTFOUND" in error_str or "ECONNREFUSED" in error_str:
        return "无法连接到 API 服务器，请检查 Base URL"
    return error_str
