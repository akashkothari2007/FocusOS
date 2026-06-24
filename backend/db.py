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


def get_stats() -> dict:
    with _stats_lock:
        return {
            "totals": dict(_totals),
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
    """
    cid = uuid.uuid4().hex[:8]
    t_open = time.monotonic()

    try:
        conn = connect(
            DATABASE_URL,
            row_factory=dict_row,
            prepare_threshold=None,
            connect_timeout=5,
        )
    except Exception as e:
        open_ms = round((time.monotonic() - t_open) * 1000)
        exc_type = type(e).__name__
        log.error(f"[db {cid}] OPEN FAILED in {open_ms}ms: {exc_type}: {e}")
        _record({
            "id": cid,
            "status": "open_failed",
            "open_ms": open_ms,
            "exc_type": exc_type,
            "exc": str(e)[:300],
        })
        raise

    with _stats_lock:
        _totals["opens"] += 1
    open_ms = round((time.monotonic() - t_open) * 1000)
    # >1s to open a connection is the clearest signal of "Supabase is waking up"
    if open_ms > 1000:
        log.warning(f"[db {cid}] SLOW OPEN: {open_ms}ms — supabase may be waking from pause")

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
        })
    except BaseException as e:
        original_exc = e
        query_ms = round((time.monotonic() - t_query) * 1000)
        exc_type = type(e).__name__
        exc_msg = str(e)[:300]
        log.error(
            f"[db {cid}] QUERY FAILED after {query_ms}ms "
            f"(conn was open {open_ms}ms): {exc_type}: {exc_msg}"
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
            "exc_type": exc_type,
            "exc": exc_msg,
        })
        raise
    finally:
        try:
            conn.close()
        except Exception as cl_err:
            log.warning(f"[db {cid}] close failed: {type(cl_err).__name__}: {cl_err}")
        if original_exc is None:
            # Only log clean closes at DEBUG so we don't flood logs
            log.debug(f"[db {cid}] closed cleanly (open={open_ms}ms)")
