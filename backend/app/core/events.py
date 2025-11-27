import asyncio
from typing import AsyncIterator, Dict, Any

_subs: set[asyncio.Queue] = set()

async def publish(event: Dict[str, Any]):
    for q in list(_subs):
        await q.put(event)

async def sse_stream() -> AsyncIterator[str]:
    q: asyncio.Queue = asyncio.Queue()
    _subs.add(q)
    try:
        while True:
            event = await q.get()
            yield f"data: {event}\n\n"
    finally:
        _subs.discard(q)
