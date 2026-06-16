from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Any

import requests


TTS_PROVIDER_DEFAULTS = {
    "mimo-tts": {
        "base_url": "https://api.xiaomimimo.com/v1",
        "model": "mimo-v2.5-tts",
        "voice": "mimo_default",
    },
    "openai-tts": {
        "base_url": "https://api.openai.com/v1",
        "model": "tts-1",
        "voice": "alloy",
    },
    "glm-tts": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-tts",
        "voice": "tongtong",
    },
    "edge-tts": {
        "base_url": "",
        "model": "",
        "voice": "zh-CN-XiaoxiaoNeural",
    },
}


class TTSAdapter:
    """Provider adapter used by classroom speech synthesis."""

    def __init__(self, tts_config: dict[str, Any] | None = None) -> None:
        tts = tts_config or {}
        self.tts_provider = tts.get("provider") or "mimo-tts"
        defaults = TTS_PROVIDER_DEFAULTS.get(self.tts_provider, TTS_PROVIDER_DEFAULTS["mimo-tts"])
        self.tts_api_key = tts.get("api_key", "")
        if not self.tts_api_key and self.tts_provider == "mimo-tts":
            self.tts_api_key = os.environ.get("MIMO_API_KEY", "")
        self.tts_base_url = tts.get("base_url") or defaults["base_url"]
        self.tts_model = tts.get("model") or defaults["model"]
        self.tts_voice = tts.get("voice") or defaults["voice"]

    def file_extension(self) -> str:
        if self.tts_provider == "edge-tts":
            return "mp3"
        return "wav"

    def generate_audio(self, text: str, voice: str = "") -> bytes:
        if self.tts_provider == "mimo-tts":
            return self._generate_mimo_tts(text, voice)
        if self.tts_provider == "glm-tts":
            return self._generate_glm_tts(text, voice)
        if self.tts_provider == "openai-tts":
            return self._generate_openai_tts(text, voice)
        if self.tts_provider == "edge-tts":
            return self._generate_edge_tts(text, voice)
        return self._generate_mimo_tts(text, voice)

    def _generate_mimo_tts(self, text: str, voice: str = "") -> bytes:
        from openai import OpenAI

        client = OpenAI(
            api_key=self.tts_api_key,
            base_url=self.tts_base_url,
        )
        response = client.chat.completions.create(
            model=self.tts_model,
            messages=[
                {"role": "user", "content": "请朗读以下内容"},
                {"role": "assistant", "content": text},
            ],
            audio={
                "format": "wav",
                "voice": voice or self.tts_voice,
            },
        )
        audio_data = response.choices[0].message.audio.data
        return base64.b64decode(audio_data)

    def _generate_openai_tts(self, text: str, voice: str = "") -> bytes:
        url = f"{self.tts_base_url.rstrip('/')}/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.tts_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.tts_model,
            "input": text,
            "voice": voice or self.tts_voice,
            "response_format": "wav",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"TTS API 错误 ({resp.status_code}): {resp.text[:300]}")
        return resp.content

    def _generate_glm_tts(self, text: str, voice: str = "") -> bytes:
        from zai import ZhipuAiClient

        client = ZhipuAiClient(api_key=self.tts_api_key)
        response = client.audio.speech(
            model=self.tts_model,
            input=text,
            voice=voice or self.tts_voice,
            response_format="wav",
            speed=1.0,
            volume=1.0,
        )

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            response.stream_to_file(tmp_path)
            return Path(tmp_path).read_bytes()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _generate_edge_tts(self, text: str, voice: str = "") -> bytes:
        import asyncio

        from deep_translator import GoogleTranslator

        voice_lang_map = {
            "zh-CN": "zh-CN",
            "zh-HK": "zh-TW",
            "zh-TW": "zh-TW",
            "en-US": "en",
            "en-GB": "en",
            "en-AU": "en",
            "ja-JP": "ja",
            "ko-KR": "ko",
        }
        target_lang = "zh-CN"
        for prefix, lang in voice_lang_map.items():
            if (voice or self.tts_voice).startswith(prefix):
                target_lang = lang
                break

        text_to_speak = text
        if target_lang != "zh-CN":
            try:
                text_to_speak = GoogleTranslator(source="zh-CN", target=target_lang).translate(text)
            except Exception:
                pass

        async def _generate() -> bytes:
            import edge_tts

            communicate = edge_tts.Communicate(text_to_speak, voice or self.tts_voice)
            audio_buffer = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer += chunk["data"]
            return audio_buffer

        return asyncio.run(_generate())
