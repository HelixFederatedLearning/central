# app/routers/events.py
import asyncio
import json
from fastapi import APIRouter, Request, Response, Depends, Query
from starlette.responses import StreamingResponse
from typing import AsyncIterator, Optional
from ..db.session import get_session
from sqlmodel import Session

router = APIRouter()

# very small in-process pubsub
_subscribers: set[asyncio.Queue] = set()
_heartbeat_seconds = 15

def publish(event_type: str, payload: dict):
    """Call this from other routers to broadcast an event."""
    data = {"type": event_type, "data": payload}
    msg = f"data: {json.dumps(data)}\n\n"
    for q in list(_subscribers):
        try:
            q.put_nowait(msg)
        except Exception:
            pass

async def _event_stream(request: Request) -> AsyncIterator[str]:
    q: asyncio.Queue[str] = asyncio.Queue()
    _subscribers.add(q)
    try:
        # initial hello so the client knows it’s connected
        yield "event: hello\ndata: {}\n\n"
        # periodic heartbeats to keep proxies happy
        async def heartbeats():
            while True:
                await asyncio.sleep(_heartbeat_seconds)
                await q.put("event: ping\ndata: {}\n\n")
        hb_task = asyncio.create_task(heartbeats())

        while True:
            # client disconnected?
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(q.get(), timeout=_heartbeat_seconds + 5)
                yield msg
            except asyncio.TimeoutError:
                # no-op; heartbeat keeps the pipe alive
                pass
        hb_task.cancel()
    finally:
        _subscribers.discard(q)

@router.get("/events")
async def sse_events(
    request: Request,
    token: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    """
    Server-Sent Events stream.
    Optional: `?token=...` (if you want to validate a central JWT later).
    For now we don't block on token to keep EventSource simple.
    """
    # If you later want to validate `token`, do it here and return 401 on failure.
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # for nginx
    }
    return StreamingResponse(_event_stream(request), media_type="text/event-stream", headers=headers)

# Convenience helpers other modules can import:
def sse_publish_delta(delta_row: dict):
    publish("delta_received", delta_row)

def sse_publish_round(round_row: dict):
    publish("round_updated", round_row)

def sse_publish_timer(ticks_left: int):
    publish("timer", {"ticks_left": ticks_left})
