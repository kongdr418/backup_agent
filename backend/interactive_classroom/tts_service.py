from __future__ import annotations

import asyncio
import os
from typing import Any, Awaitable, Callable

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
        """同步版本：合成单个 action 的 TTS，写到 output_dir。

        保留是因为 /api/interactive-classroom/<id>/answer 路由在评分后还会
        单独合成 quiz_feedback，不在并行批里。
        """
        if not text.strip():
            return ""

        os.makedirs(output_dir, exist_ok=True)
        audio_bytes = self.generator._generate_tts_audio(text, self.generator.tts_voice)  # noqa: SLF001
        filename = f"{action_id}.{self._file_extension()}"
        path = os.path.join(output_dir, filename)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        return filename

    async def synthesize_action_async(
        self,
        action_id: str,
        text: str,
        output_dir: str,
    ) -> str:
        """异步版本：在线程池里跑同步 TTS 调用，避免阻塞 event loop。"""
        if not text.strip():
            return ""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.synthesize_action,
            action_id,
            text,
            output_dir,
        )


# ---------- 并行批 ----------

# 默认并发上限：edge-tts 内部已经做并发，按这个数 4 已经很快；
# openai/glm 受 RPM 限制可降到 2。
DEFAULT_TTS_MAX_CONCURRENCY = 4

# 单个 action 合成结果类型
# (action_id, filename_or_empty, error_or_none)
TTSParallelItem = tuple[str, str, Exception | None]

# 进度回调签名：每个 action 完成时调一次，idx 从 1 开始
TTSProgressHook = Callable[[int, int, str, str | None, Exception | None], None]
#                       total done action_id filename        error

# 取消检查签名：与 generator._raise_if_cancelled 保持一致
CancelCheck = Callable[[], bool]


async def synthesize_actions_parallel_with_progress(
    service: ClassroomTTSService,
    actions: list[tuple[str, str]],
    output_dir: str,
    *,
    max_concurrency: int = DEFAULT_TTS_MAX_CONCURRENCY,
    cancel_check: CancelCheck | None = None,
    on_action_done: TTSProgressHook | None = None,
) -> list[TTSParallelItem]:
    """并发合成所有 action 的 TTS，写到 output_dir。

    - 并发上限默认 4
    - 失败容忍：单个 action 失败不影响其他（on_action_done 收到 error）
    - 取消：cancel_check 返回 True 时，未开始的任务被早退；已开始的任务等
      gather 统一取消；抛 ClassroomGenerationCancelled
    - 进度：每个 action 完成（成功或失败）按完成顺序调 on_action_done(
      done_idx, total, action_id, filename, error)；done_idx 从 1 开始
    """
    if not actions:
        return []

    sem = asyncio.Semaphore(max_concurrency)
    os.makedirs(output_dir, exist_ok=True)

    total = len(actions)
    done_order: list[str] = []

    async def _run_one(action_id: str, text: str) -> TTSParallelItem:
        async with sem:
            if cancel_check and cancel_check():
                return (action_id, "", None)
            try:
                filename = await service.synthesize_action_async(action_id, text, output_dir)
                return (action_id, filename, None)
            except Exception as exc:  # noqa: BLE001
                return (action_id, "", exc)

    tasks = [asyncio.create_task(_run_one(aid, txt)) for aid, txt in actions]

    async def _tracked(t: asyncio.Task) -> TTSParallelItem:
        item: TTSParallelItem = await t
        done_order.append(item[0])
        if on_action_done:
            try:
                on_action_done(len(done_order), total, item[0], item[1], item[2])
            except Exception:
                # 进度回调永远不能破坏并行合成
                pass
        return item

    try:
        tracked_results = await asyncio.gather(*[_tracked(t) for t in tasks])
    finally:
        # 取消或异常时确保未完成任务被关闭
        for t in tasks:
            if not t.done():
                t.cancel()

    return list(tracked_results)

