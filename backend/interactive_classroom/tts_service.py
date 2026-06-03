from __future__ import annotations

import os
from typing import Any

from video_generator import VideoGenerator


class ClassroomTTSService:
    """Thin wrapper that reuses VideoGenerator provider adapters."""

    def __init__(self, output_dir: str, tts_config: dict[str, Any]) -> None:
        self.generator = VideoGenerator(workspace_dir=output_dir, tts_config=tts_config)

    def _file_extension(self) -> str:
        if self.generator.tts_provider == "edge-tts":
            return "mp3"
        return "wav"

    def synthesize_action(self, action_id: str, text: str, output_dir: str) -> str:
        if not text.strip():
            return ""

        os.makedirs(output_dir, exist_ok=True)
        audio_bytes = self.generator._generate_tts_audio(text, self.generator.tts_voice)  # noqa: SLF001
        filename = f"{action_id}.{self._file_extension()}"
        path = os.path.join(output_dir, filename)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        return filename
