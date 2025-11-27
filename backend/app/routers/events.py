# app/routers/events.py
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
import asyncio
from ..core.events import bus
from ..core.security import get_current_user_optional  # adjust import to your auth helper

router = APIRouter()

async def sse_format(message: str) -> bytes:
    # data: ...\n\n
    return f"data: {message}\n\n".encode("utf-8")

@router.get("/events")
async def sse_events(request: Request, user=Depends(get_current_user_optional)):
    """
    Server-Sent Events endpoint.
    Accepts either:
      - Authorization header (if your get_current_user_optional reads it), or
      - a ?token=... query param — make sure your auth helper supports it.
    """
    done = asyncio.Event()
    async def event_generator():
        # initial keepalive so the client marks 'connected'
        yield await sse_format('{"type":"hello"}')
        async for msg in bus.subscribe():
            # client disconnected?
            if await request.is_disconnected():
                done.set()
                break
            yield await sse_format(msg)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        background=BackgroundTask(done.wait),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # for proxies
            "Connection": "keep-alive",
        },
    )
