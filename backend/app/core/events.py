# app/core/events.py
import asyncio
import json
from typing import AsyncIterator, Dict, Any

from fastapi import Request

# Single global subscriber registry for ALL SSE users
_subscribers: set[asyncio.Queue[str]] = set()
_HEARTBEAT_SEC = 15


async def publish(event: Dict[str, Any]) -> None:
    """
    Broadcast a JSON-serializable event dict to all SSE subscribers.

    The dict MUST already be in the shape the frontend expects, e.g.:

      {
        "type": "delta_received",
        "round_id": "...",
        "client_id": "...",
        "kind": "hospital",
        "num_examples": 10,
        "received_at": "2025-01-01T00:00:00Z"
      }

    FedEventsProvider does: JSON.parse(msg.data) and treats
    that as the event object.
    """
    try:
        payload = json.dumps(event, default=str)
    except TypeError:
        # best-effort: stringify non-serializable parts
        payload = json.dumps(
            {k: str(v) for k, v in event.items()},
            default=str,
        )

    msg = f"data: {payload}\n\n"

    # Fan-out to all connected EventSource clients
    for q in list(_subscribers):
        try:
            q.put_nowait(msg)
        except Exception:
            # if queue is dead/full, ignore — others still get it
            pass


async def event_stream(request: Request) -> AsyncIterator[str]:
    """
    Shared SSE generator used by /v1/events.
    """
    q: asyncio.Queue[str] = asyncio.Queue()
    _subscribers.add(q)

    try:
        # Initial hello so the client knows it's connected
        yield "event: hello\ndata: {}\n\n"

        async def heartbeats() -> None:
            while True:
                await asyncio.sleep(_HEARTBEAT_SEC)
                await q.put("event: ping\ndata: {}\n\n")

        hb_task = asyncio.create_task(heartbeats())

        while True:
            # client disconnected?
            if await request.is_disconnected():
                break

            try:
                msg = await asyncio.wait_for(
                    q.get(),
                    timeout=_HEARTBEAT_SEC + 5,
                )
                yield msg
            except asyncio.TimeoutError:
                # heartbeat coroutine keeps pipe alive
                pass

        hb_task.cancel()
    finally:
        _subscribers.discard(q)
