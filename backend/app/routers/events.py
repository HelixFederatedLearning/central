# app/routers/events.py
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from starlette.responses import StreamingResponse
from sqlmodel import Session

from ..db.session import get_session
from ..core.events import event_stream, publish as core_publish

router = APIRouter()


@router.get("/events")
async def sse_events(
    request: Request,
    token: Optional[str] = Query(default=None),  # reserved for future auth
    session: Session = Depends(get_session),     # keeps the signature consistent
):
  """
  Server-Sent Events endpoint for the central UI.

  Frontend connects via:
    new EventSource(`${API_BASE}/events`);
  """
  headers = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # for nginx
  }
  return StreamingResponse(
    event_stream(request),       # <-- from core.events
    media_type="text/event-stream",
    headers=headers,
  )


# -------------------------------------------------------------------
# Convenience helpers: these now delegate to core.events.publish
# -------------------------------------------------------------------

async def emit_delta_received(
    *,
    round_id: str,
    client_id: str,
    kind: str,              # "hospital" | "patient"
    num_examples: int,
    received_at: str,
) -> None:
  await core_publish(
    {
      "type": "delta_received",
      "round_id": round_id,
      "client_id": client_id,
      "kind": kind,
      "num_examples": num_examples,
      "received_at": received_at,
    }
  )


async def emit_round_opened(
    *,
    round_id: str,
    opened_at: str,
    window_minutes: int,
) -> None:
  await core_publish(
    {
      "type": "round_opened",
      "round_id": round_id,
      "opened_at": opened_at,
      "window_minutes": window_minutes,
    }
  )


async def emit_round_aggregated(
    *,
    round_id: str,
    aggregated_at: str,
    new_model_id: str,
    new_version: str,
) -> None:
  await core_publish(
    {
      "type": "round_aggregated",
      "round_id": round_id,
      "aggregated_at": aggregated_at,
      "new_model_id": new_model_id,
      "new_version": new_version,
    }
  )


async def emit_current_model_updated(
    *,
    model_id: str,
    version: str,
    at: str,
) -> None:
  await core_publish(
    {
      "type": "current_model_updated",
      "model_id": model_id,
      "version": version,
      "at": at,
    }
  )
