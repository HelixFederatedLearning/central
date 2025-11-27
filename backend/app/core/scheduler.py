# import asyncio
# from contextlib import asynccontextmanager, suppress
# from datetime import datetime, timezone, timedelta

# from sqlmodel import Session, select

# from ..db.session import engine
# from ..db.models import Round, Setting
# from ..services.aggregate import aggregate_round_if_ready

# CHECK_EVERY_SEC = 10  # how often to scan for rounds


# @asynccontextmanager
# async def scheduler_lifespan(app):
#     """
#     FastAPI lifespan context. Must accept `app`.
#     Spawns a background task that periodically tries to aggregate
#     any rounds whose window has elapsed.
#     """
#     task = asyncio.create_task(_loop())
#     try:
#         yield
#     finally:
#         task.cancel()
#         with suppress(asyncio.CancelledError):
#             await task


# async def _loop():
#     while True:
#         try:
#             _tick()
#         except Exception as e:
#             # keep the loop alive on errors
#             print(f"[scheduler] tick error: {e}")
#         await asyncio.sleep(CHECK_EVERY_SEC)


# def _planned_close_at(session: Session, r: Round) -> datetime:
#     """
#     Compute planned close time as created_at + window.
#     Falls back to 120s if not configured.
#     """
#     st = session.get(Setting, 1)
#     window_sec = getattr(st, "round_window_sec", None) or 120
#     base = r.created_at
#     # created_at should be timezone-aware; if not, assume UTC
#     if base.tzinfo is None:
#         base = base.replace(tzinfo=timezone.utc)
#     return base + timedelta(seconds=window_sec)


# def _tick():
#     now = datetime.now(timezone.utc)
#     with Session(engine) as s:
#         # Match your actual status values; support both "collecting" and "open"
#         rows = list(
#             s.exec(
#                 select(Round).where(Round.status.in_(["collecting", "open"]))
#             ).all()
#         )
#         for r in rows:
#             try:
#                 close_at = _planned_close_at(s, r)
#             except Exception as e:
#                 print(f"[scheduler] failed to compute close_at for round={r.id}: {e}")
#                 continue

#             if now >= close_at:
#                 try:
#                     # aggregate and close as soon as window elapses
#                     aggregate_round_if_ready(s, r.id, force=True)
#                 except Exception as e:
#                     # IMPORTANT: rollback so the session isn't poisoned for next ticks
#                     s.rollback()
#                     print(f"[scheduler] aggregate error round={r.id}: {e}")

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone, timedelta

from sqlmodel import Session, select

from ..db.session import engine
from ..db.models import Round, Setting
from ..services.aggregate import aggregate_round_if_ready

CHECK_EVERY_SEC = 10  # how often to scan for rounds


@asynccontextmanager
async def scheduler_lifespan(app):
    """
    FastAPI lifespan context. Must accept `app`.
    Spawns a background task that periodically tries to aggregate
    any rounds whose window has elapsed.
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
            # keep the loop alive on errors
            print(f"[scheduler] tick error: {e}")
        await asyncio.sleep(CHECK_EVERY_SEC)


def _planned_close_at(session: Session, r: Round) -> datetime:
    """
    Compute planned close time as created_at + window.
    Falls back to 120s if not configured in settings.
    """
    st = session.get(Setting, 1)
    window_sec = getattr(st, "round_window_sec", None) or 120
    base = r.created_at
    if base.tzinfo is None:  # be robust: assume UTC
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(seconds=window_sec)


def _tick():
    now = datetime.now(timezone.utc)
    with Session(engine) as s:
        # Support both status spellings if your DB has old rows
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
                    print(f"[scheduler] aggregate error round={r.id}: {e}")
