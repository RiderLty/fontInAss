import asyncio
import json
import logging
import time
from collections import deque
from fastapi import Request
from fastapi.responses import StreamingResponse


class SSELogHandler(logging.Handler):
    """Custom logging handler that stores recent log lines and notifies SSE subscribers."""

    def __init__(self, ring_size=500):
        super().__init__()
        self._ring = deque(maxlen=ring_size)
        self._subscribers: list[asyncio.Queue] = []

    def emit(self, record):
        try:
            msg = self.format(record)
            entry = {
                "time": time.strftime("%H:%M:%S", time.localtime(record.created)),
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
            }
            self._ring.append(entry)
            for q in self._subscribers:
                try:
                    q.put_nowait(entry)
                except asyncio.QueueFull:
                    pass
        except Exception:
            self.handleError(record)

    def get_recent(self, n=100):
        return list(self._ring)[-n:]

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass


sse_handler = SSELogHandler(ring_size=500)


def format_sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def sse_log_stream(request: Request):
    """SSE endpoint generator function."""
    for entry in sse_handler.get_recent(100):
        if await request.is_disconnected():
            return
        yield format_sse_event(entry)

    queue = sse_handler.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                return
            try:
                entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield format_sse_event(entry)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        sse_handler.unsubscribe(queue)
