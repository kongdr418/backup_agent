"""Async-to-SSE bridge for Flask.

Runs an async generator in a background thread and transfers events
to Flask's synchronous SSE generator via queue.Queue.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any, Iterator

# Send a heartbeat SSE comment every N seconds while waiting for events
SSE_HEARTBEAT_INTERVAL_SEC = 15.0


class SSEBridge:
    """Bridges an async generator to a synchronous iterator for Flask SSE."""

    def __init__(self) -> None:
        self._event_queue: queue.Queue[Any] = queue.Queue()
        self._error: BaseException | None = None
        self._done = threading.Event()

    def run(self, async_gen) -> None:
        """Start consuming the async generator in a background thread."""
        def _thread_target():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._consume(async_gen))
            except Exception as e:
                self._error = e
            finally:
                self._event_queue.put(None)  # sentinel
                self._done.set()
                loop.close()

        thread = threading.Thread(target=_thread_target, daemon=True)
        thread.start()

    async def _consume(self, async_gen) -> None:
        async for event in async_gen:
            self._event_queue.put(event)

    def events(self) -> Iterator[Any]:
        """Yield events synchronously for Flask SSE.

        Yields heartbeat comments (":heartbeat\n\n") when no events arrive
        within SSE_HEARTBEAT_INTERVAL_SEC to keep the HTTP connection alive.
        """
        while True:
            try:
                event = self._event_queue.get(timeout=SSE_HEARTBEAT_INTERVAL_SEC)
            except queue.Empty:
                # No event arrived within the interval — emit SSE comment to keep connection alive
                yield ":heartbeat\n\n"
                continue

            if event is None:
                if self._error:
                    raise self._error
                break
            yield event
