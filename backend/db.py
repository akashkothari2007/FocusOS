import os
import logging
import time
import uuid
from collections import Counter, deque
from contextlib import contextmanager
from threading import Lock

from psycopg import connect
from psycopg.rows import dict_row

log = logging.getLogger("db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://focusos:focusos@localhost:5432/focusos")

# Connection setup notes:
#   - Hostname is Supavisor on :6543 → transaction-pool mode
#   - prepare_threshold=None: REQUIRED for transaction mode (statements prepared on
#     one backend won't exist on the next)
#   - connect_timeout=5: don't let a hung Supabase wake-up block requests for 30s

# ---------------------------------------------------------------------------
# Rolling instrumentation
# ---------------------------------------------------------------------------
# We don't have a pool to report stats from, so we keep our own tiny
# rolling window of recent connection lifecycles + a cumulative error counter.
# Surfaced via GET /db so you can inspect from the phone/laptop without
# digging through Railway logs.

_stats_lock = Lock()
_recent_events: deque = deque(maxlen=50)
_error_counts: Counter = Counter()
_totals = {"opens": 0, "ok": 0, "open_failed": 0, "query_failed": 0}

# Live counters used to discriminate hypotheses about why connections die:
#   - in_flight: how many get_conn() blocks are currently open. If failures
#     correlate with a spike, it points at a parallel-burst / Supavisor
#     backend-exhaustion issue.
#   - last_open_at_mono: time.monotonic() of the most recent connection open.
#     A large gap_since_last_open on a failure points at "first request after
#     a long idle period" (e.g. laptop slept for hours, phone wakes it).
_in_flight = 0
_last_open_at_mono = 0.0


def get_stats() -> dict:
    with _stats_lock:
        gap_s = (
            round(time.monotonic() - _last_open_at_mono, 1)
            if _last_open_at_mono > 0 else None
        )
        return {
            "totals": dict(_totals),
            "in_flight": _in_flight,
            "seconds_since_last_open": gap_s,
            "error_counts": dict(_error_counts),
            "recent": list(_recent_events)[:20],
        }


def _record(event: dict) -> None:
    with _stats_lock:
        _recent_events.appendleft(event)
        status = event.get("status")
        if status in _totals:
            _totals[status] += 1
        if status in ("open_failed", "query_failed"):
            _error_counts[event.get("exc_type", "unknown")] += 1


# ---------------------------------------------------------------------------
# get_conn
# ---------------------------------------------------------------------------

@contextmanager
def get_conn():
    """Fresh connection per call through Supavisor (:6543).

    Instrumented so every open/query/error gets a correlated log line and is
    counted in the rolling stats surfaced via GET /db.

    statement_timeout=10s is server-side, so even if our process is somehow
    holding a connection past its lifetime, Postgres itself will kill any
    individual query that runs longer than 10s — preventing leaked transactions
    from holding Supavisor backends hostage (per supabase/supavisor#459).
    """
    global _in_flight, _last_open_at_mono
    cid = uuid.uuid4().hex[:8]
    t_open = time.monotonic()

    # Snapshot the "context" for this connection BEFORE opening it, so even
    # if open fails we know how many were in flight and how long since the
    # last open happened.
    with _stats_lock:
        in_flight_at_open = _in_flight
        gap_since_last_open = (
            round(t_open - _last_open_at_mono, 1)
            if _last_open_at_mono > 0 else None
        )

    try:
        conn = connect(
            DATABASE_URL,
            row_factory=dict_row,
            prepare_threshold=None,
            connect_timeout=5,
            options="-c statement_timeout=10000",  # 10s server-side query timeout
        )
    except Exception as e:
        open_ms = round((time.monotonic() - t_open) * 1000)
        exc_type = type(e).__name__
        log.error(
            f"[db {cid}] OPEN FAILED in {open_ms}ms "
            f"(in_flight={in_flight_at_open}, gap={gap_since_last_open}s): "
            f"{exc_type}: {e}"
        )
        _record({
            "id": cid,
            "status": "open_failed",
            "open_ms": open_ms,
            "in_flight_at_open": in_flight_at_open,
            "gap_since_last_open_s": gap_since_last_open,
            "exc_type": exc_type,
            "exc": str(e)[:300],
        })
        raise

    with _stats_lock:
        _totals["opens"] += 1
        _in_flight += 1
        _last_open_at_mono = t_open
    open_ms = round((time.monotonic() - t_open) * 1000)
    # >1s to open a connection means Supavisor is slow to assign a backend.
    # Could be cold-start, network blip, or backend pool exhaustion.
    if open_ms > 1000:
        log.warning(
            f"[db {cid}] SLOW OPEN: {open_ms}ms "
            f"(in_flight={in_flight_at_open}, gap={gap_since_last_open}s)"
        )

    t_query = time.monotonic()
    original_exc: BaseException | None = None
    try:
        yield conn
        conn.commit()
        query_ms = round((time.monotonic() - t_query) * 1000)
        if query_ms > 2000:
            log.warning(f"[db {cid}] slow query block: {query_ms}ms (open was {open_ms}ms)")
        _record({
            "id": cid,
            "status": "ok",
            "open_ms": open_ms,
            "query_ms": query_ms,
            "in_flight_at_open": in_flight_at_open,
            "gap_since_last_open_s": gap_since_last_open,
        })
    except BaseException as e:
        original_exc = e
        query_ms = round((time.monotonic() - t_query) * 1000)
        exc_type = type(e).__name__
        exc_msg = str(e)[:300]
        log.error(
            f"[db {cid}] QUERY FAILED after {query_ms}ms "
            f"(open={open_ms}ms, in_flight={in_flight_at_open}, gap={gap_since_last_open}s): "
            f"{exc_type}: {exc_msg}"
        )

        # Rollback in its OWN try/except — never let it mask the original error.
        # Previously: rollback() on a dead Supavisor connection raised
        # OperationalError("the connection is lost") which buried the real
        # EDBHANDLEREXITED message in the chain.
        try:
            conn.rollback()
        except Exception as rb_err:
            log.warning(
                f"[db {cid}] rollback also failed ({type(rb_err).__name__}: {rb_err}) "
                f"— connection was already dead, original error above is the real one"
            )

        _record({
            "id": cid,
            "status": "query_failed",
            "open_ms": open_ms,
            "query_ms": query_ms,
            "in_flight_at_open": in_flight_at_open,
            "gap_since_last_open_s": gap_since_last_open,
            "exc_type": exc_type,
            "exc": exc_msg,
        })
        raise
    finally:
        try:
            conn.close()
        except Exception as cl_err:
            log.warning(f"[db {cid}] close failed: {type(cl_err).__name__}: {cl_err}")
        with _stats_lock:
            _in_flight -= 1
        if original_exc is None:
            log.debug(f"[db {cid}] closed cleanly (open={open_ms}ms)")
