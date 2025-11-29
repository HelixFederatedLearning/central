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
#     Falls back to 120s if not configured in settings.
#     """
#     st = session.get(Setting, 1)
#     window_sec = getattr(st, "round_window_sec", None) or 120
#     base = r.created_at
#     if base.tzinfo is None:  # be robust: assume UTC
#         base = base.replace(tzinfo=timezone.utc)
#     return base + timedelta(seconds=window_sec)


# def _tick():
#     now = datetime.now(timezone.utc)
#     with Session(engine) as s:
#         # Support both status spellings if your DB has old rows
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
#                     # Aggregate and close as soon as window elapses
#                     aggregate_round_if_ready(s, r.id, force=True)
#                 except Exception as e:
#                     print(f"[scheduler] aggregate error round={r.id}: {e}")
# app/core/scheduler.py
# import asyncio
# from datetime import datetime, timezone

# from sqlmodel import Session, select

# from ..db.session import engine
# from ..db.models import Round, Setting, Delta
# from ..core.settings import settings
# from ..services.aggregate import aggregate_round_if_ready


# CHECK_EVERY_SEC = 10  # how often to scan for rounds


# def _count_kinds(session: Session, round_id: str):
#     """How many hospital vs patient deltas for this round?"""
#     rows = list(
#         session.exec(
#             select(Delta).where(Delta.round_id == round_id)
#         )
#     )
#     hosp = sum(1 for d in rows if d.kind == "hospital")
#     pat = sum(1 for d in rows if d.kind == "patient")
#     return hosp, pat


# async def scheduler_loop() -> None:
#     """
#     Background loop:

#       1) Look for all rounds with status='open'.
#       2) If a round's window_end <= now:
#            - If it has at least MIN_TOTAL deltas, aggregate_round_if_ready().
#            - Otherwise just close it without aggregation.
#     """
#     while True:
#         try:
#             now = datetime.now(timezone.utc)
#             with Session(engine) as session:
#                 q = select(Round).where(Round.status == "open")
#                 rounds = list(session.exec(q))

#                 for r in rounds:
#                     # if no window_end, skip
#                     if not getattr(r, "window_end", None):
#                         continue
#                     if r.window_end > now:
#                         continue

#                     hosp, pat = _count_kinds(session, r.id)
#                     total = hosp + pat

#                     st = session.get(Setting, 1) or Setting()
#                     # use DB setting if present, else global default
#                     min_total = getattr(st, "min_total", None) or settings.MIN_TOTAL

#                     if total >= min_total:
#                         # Enough updates → aggregate + close
#                         try:
#                             aggregate_round_if_ready(session, r.id, force=True)
#                         except Exception as e:
#                             print(f"[scheduler] aggregate error for round={r.id}: {e}")
#                     else:
#                         # Not enough updates → just close round
#                         r.status = "closed"
#                         r.closed_at = now
#                         session.add(r)
#                         session.commit()

#         except Exception as e:
#             # keep scheduler alive even if a tick fails
#             print(f"[scheduler] tick error: {e}")

#         await asyncio.sleep(CHECK_EVERY_SEC)
# app/core/scheduler.py
# import asyncio
# from datetime import datetime, timezone, timedelta
# from typing import Optional, Tuple

# from sqlmodel import Session, select

# from ..db.session import engine
# from ..db.models import Round, Setting, Delta
# from .settings import settings          # same package: .settings
# from ..services.aggregate import aggregate_round_if_ready


# CHECK_EVERY_SEC = 10  # how often to scan for rounds


# def _round_stats(
#     session: Session,
#     round_id: str,
#     min_total_required: int,
# ) -> Tuple[int, int, int, Optional[datetime]]:
#     """
#     For a given round:

#       - Count how many hospital vs patient deltas
#       - Compute total
#       - If total >= min_total_required, define window_start as the
#         timestamp of the min_total_required-th delta (sorted by created_at).
#         Otherwise, window_start = None.

#     This implements the behavior:
#       - "Window will not start if received delta is 1"
#       - "If more than 1, then start"
#     (assuming MIN_TOTAL = 2).
#     """
#     # All deltas for this round, oldest first
#     deltas = list(
#         session.exec(
#             select(Delta)
#             .where(Delta.round_id == round_id)
#             .order_by(Delta.created_at.asc())
#         )
#     )

#     hosp = sum(1 for d in deltas if getattr(d, "kind", "") == "hospital")
#     pat = sum(1 for d in deltas if getattr(d, "kind", "") == "patient")
#     total = hosp + pat

#     # Not enough deltas → window has not started
#     if total < min_total_required or not deltas:
#         return hosp, pat, total, None

#     # Use the time of the MIN_TOTAL-th delta as the start of the window
#     idx = min(min_total_required - 1, len(deltas) - 1)
#     ts = getattr(deltas[idx], "created_at", None)

#     if ts is None:
#         # Fallback: no timestamp on delta; treat as "no window"
#         return hosp, pat, total, None

#     if ts.tzinfo is None:
#         ts = ts.replace(tzinfo=timezone.utc)

#     return hosp, pat, total, ts


# async def scheduler_loop() -> None:
#     """
#     Background loop:

#       1) Look for all rounds with status='open'.
#       2) For each open round:
#            - Gather deltas + stats.
#            - If total < MIN_TOTAL → no window yet → do nothing.
#            - Else:
#                 * window_start = timestamp of MIN_TOTAL-th delta.
#                 * planned end time = window_start + window_minutes.
#                 * If now < end → still collecting.
#                 * If now >= end → aggregate_round_if_ready() and close.
#     """
#     while True:
#         try:
#             now = datetime.now(timezone.utc)
#             with Session(engine) as session:
#                 # Read settings from DB or fall back to defaults
#                 st = session.get(Setting, 1) or Setting()
#                 window_minutes = (
#                     getattr(st, "window_minutes", None)
#                     or settings.WINDOW_MINUTES
#                 )
#                 min_total = getattr(st, "min_total", None) or settings.MIN_TOTAL

#                 min_total_int = int(min_total)
#                 win_minutes_int = int(window_minutes)

#                 # all open rounds
#                 q = select(Round).where(Round.status == "open")
#                 rounds = list(session.exec(q))

#                 for r in rounds:
#                     try:
#                         hosp, pat, total, window_start = _round_stats(
#                             session,
#                             r.id,
#                             min_total_required=min_total_int,
#                         )

#                         # Not enough updates yet → window hasn't started
#                         if total < min_total_int or window_start is None:
#                             continue

#                         end = window_start + timedelta(minutes=win_minutes_int)

#                         # still within its collection window → skip
#                         if now < end:
#                             continue

#                         # window elapsed AND total >= MIN_TOTAL → aggregate + close
#                         try:
#                             aggregate_round_if_ready(session, r.id, force=True)
#                         except Exception as e:
#                             print(f"[scheduler] aggregate error for round={r.id}: {e}")

#                         # ensure round is marked closed / aggregated
#                         r_ref = session.get(Round, r.id)
#                         if r_ref and r_ref.status != "closed":
#                             # aggregate_round_if_ready normally sets aggregated+closed_at,
#                             # but if not, we close here.
#                             if not getattr(r_ref, "closed_at", None):
#                                 r_ref.closed_at = datetime.now(timezone.utc)
#                             if r_ref.status not in ("aggregated", "closed"):
#                                 r_ref.status = "closed"
#                             session.add(r_ref)
#                             session.commit()

#                     except Exception as e:
#                         # keep scheduler alive for other rounds
#                         print(f"[scheduler] tick round={getattr(r, 'id', '?')} error: {e}")

#         except Exception as e:
#             # keep scheduler alive even if a global tick fails
#             print(f"[scheduler] tick error: {e}")

#         await asyncio.sleep(CHECK_EVERY_SEC)
# app/core/scheduler.py
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlmodel import Session, select

from ..db.session import engine
from ..db.models import Round, Setting, Delta
from .settings import settings
from ..services.aggregate import aggregate_round_if_ready

CHECK_EVERY_SEC = 10  # how often to scan for rounds


def _round_stats(
    session: Session,
    round_id: str,
    min_total_required: int,
) -> Tuple[int, int, int, Optional[datetime]]:
    """
    For a given round:

      - Count how many hospital vs patient deltas
      - Compute total
      - If total >= min_total_required, define window_start as the
        timestamp of the min_total_required-th delta (sorted by created_at).
        Otherwise, window_start = None.

    This implements:
      - window does NOT start if total < min_total_required
      - window starts at the MIN_TOTAL-th delta
    """
    deltas = list(
        session.exec(
            select(Delta)
            .where(Delta.round_id == round_id)
            .order_by(Delta.created_at.asc())
        )
    )

    hosp = sum(1 for d in deltas if getattr(d, "kind", "") == "hospital")
    pat = sum(1 for d in deltas if getattr(d, "kind", "") == "patient")
    total = hosp + pat

    if total < min_total_required or not deltas:
        return hosp, pat, total, None

    idx = min(min_total_required - 1, len(deltas) - 1)
    ts = getattr(deltas[idx], "created_at", None)

    if ts is None:
        return hosp, pat, total, None

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    return hosp, pat, total, ts


async def scheduler_loop() -> None:
    """
    Background loop:

      1) Look for all rounds with status='open'.
      2) For each open round:
           - Gather deltas + stats.
           - If total < MIN_TOTAL → no window yet → do nothing.
           - Else:
                * window_start = timestamp of MIN_TOTAL-th delta.
                * planned end time = window_start + window_minutes.
                * If now < end → still collecting.
                * If now >= end → aggregate_round_if_ready() and close.
    """
    while True:
        try:
            now = datetime.now(timezone.utc)
            with Session(engine) as session:
                st = session.get(Setting, 1) or Setting()
                window_minutes = (
                    getattr(st, "window_minutes", None)
                    or settings.WINDOW_MINUTES
                )
                min_total = getattr(st, "min_total", None) or settings.MIN_TOTAL

                min_total_int = int(min_total)
                win_minutes_int = int(window_minutes)

                q = select(Round).where(Round.status == "open")
                rounds = list(session.exec(q))

                for r in rounds:
                    try:
                        hosp, pat, total, window_start = _round_stats(
                            session,
                            r.id,
                            min_total_required=min_total_int,
                        )

                        # Not enough updates yet → window hasn't started
                        if total < min_total_int or window_start is None:
                            continue

                        end = window_start + timedelta(minutes=win_minutes_int)

                        # Still within window: keep collecting
                        if now < end:
                            continue

                        # Window elapsed AND total >= MIN_TOTAL → aggregate + close
                        try:
                            aggregate_round_if_ready(session, r.id, force=True)
                        except Exception as e:
                            print(f"[scheduler] aggregate error for round={r.id}: {e}")

                        # Ensure round is marked closed/aggregated
                        r_ref = session.get(Round, r.id)
                        if r_ref and r_ref.status != "closed":
                            if not getattr(r_ref, "closed_at", None):
                                r_ref.closed_at = datetime.now(timezone.utc)
                            if r_ref.status not in ("aggregated", "closed"):
                                r_ref.status = "closed"
                            session.add(r_ref)
                            session.commit()

                    except Exception as e:
                        print(f"[scheduler] tick round={getattr(r, 'id', '?')} error: {e}")

        except Exception as e:
            print(f"[scheduler] tick error: {e}")

        await asyncio.sleep(CHECK_EVERY_SEC)
