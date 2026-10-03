"""SSE hub for /api/events. Everyone (C, D) publishes through publish().

Events: message.scored, incident.created, incident.escalated, incident.updated (NEW),
campaign.updated, containment.done, recovery.updated.
Browser side: EventSource needs addEventListener(<event name>, ...) per type.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()
_clients: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called from the app lifespan so sync endpoints (threadpool) can publish safely."""
    global _loop
    _loop = loop


def publish(event_type: str, payload: Any) -> None:
    """Thread-safe. Drops silently when nobody is listening."""
    if _loop is None:
        return
    msg = {"type": event_type, "data": payload}
    for q in list(_clients):
        _loop.call_soon_threadsafe(q.put_nowait, msg)


@router.get("/api/events")
async def stream(request: Request) -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue()
    _clients.add(queue)

    async def gen():
        try:
            yield "retry: 1000\n\n: connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # keep proxies and the browser connection alive
                    continue
                yield f"event: {msg['type']}\ndata: {json.dumps(msg['data'], default=str)}\n\n"
        finally:
            _clients.discard(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
