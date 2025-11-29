# app/services/scheduler.py
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone, timedelta

from sqlmodel import Session, select

from ..db.session import engine
from ..db.models import Round, Setting
from ..core.settings import settings
from ..services.aggregate import aggregate_round_if_ready

CHECK_EVERY_SEC = 10  # how often to scan for rounds


@asynccontextmanager
async def scheduler_lifespan(app):
    """
    FastAPI lifespan context. Spawns a background task that periodically
    tries to aggregate any rounds whose window has elapsed.
    """
    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def _loop():
    while True:
        try:
            _tick()
        except Exception as e:
            print(f"[scheduler] tick error: {e}")
        await asyncio.sleep(CHECK_EVERY_SEC)


def _planned_close_at(session: Session, r: Round) -> datetime:
    """
    Compute planned close time as created_at + window_minutes.

    Uses DB Setting.window_minutes if present; otherwise falls back to
    global settings.WINDOW_MINUTES.
    """
    st = session.get(Setting, 1)
    # fallback to global Settings (core.settings)
    window_min = getattr(st, "window_minutes", None) or settings.WINDOW_MINUTES
    window_sec = window_min * 60

    base = r.created_at
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(seconds=window_sec)


def _tick():
    now = datetime.now(timezone.utc)
    with Session(engine) as s:
        rows = list(
            s.exec(
                select(Round).where(Round.status.in_(["collecting", "open"]))
            ).all()
        )
        for r in rows:
            try:
                close_at = _planned_close_at(s, r)
            except Exception as e:
                print(f"[scheduler] failed to compute close_at for round={r.id}: {e}")
                continue

            if now >= close_at:
                try:
                    # Aggregate and close as soon as window elapses
                    aggregate_round_if_ready(s, r.id, force=True)
                except Exception as e:
                    s.rollback()
                    print(f"[scheduler] aggregate error round={r.id}: {e}")
