from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Query
from db import get_conn
from models.session_models import EndSession, StartFreeformSession, QuickSession

router = APIRouter(prefix="/api/v1")


# Returns the one open session (ended_at IS NULL) if any, with its title
@router.get("/sessions/stats")
def get_session_stats():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Week totals: this week vs same elapsed period last week
            # elapsed = time since Mon 00:00, so last-week same period = last Mon + elapsed
            cur.execute("""
                SELECT
                    SUM(CASE WHEN started_at >= date_trunc('week', NOW())
                             THEN COALESCE(seconds_spent, 0) ELSE 0 END) AS this_week,
                    SUM(CASE WHEN started_at >= date_trunc('week', NOW()) - INTERVAL '7 days'
                              AND started_at <  date_trunc('week', NOW()) - INTERVAL '7 days'
                                              + (NOW() - date_trunc('week', NOW()))
                             THEN COALESCE(seconds_spent, 0) ELSE 0 END) AS last_week_same,
                    EXTRACT(ISODOW FROM NOW())::INT AS days_elapsed
                FROM sessions
                WHERE ended_at IS NOT NULL
                  AND started_at >= date_trunc('week', NOW()) - INTERVAL '7 days';
            """)
            week_row = cur.fetchone()

            # By day of week (last 28 days), 0=Sun…6=Sat
            cur.execute("""
                SELECT
                    EXTRACT(DOW FROM started_at)::INT AS dow,
                    SUM(COALESCE(seconds_spent, 0)) AS total_seconds,
                    COUNT(*) AS session_count
                FROM sessions
                WHERE ended_at IS NOT NULL
                  AND started_at >= CURRENT_TIMESTAMP - INTERVAL '28 days'
                GROUP BY dow
                ORDER BY dow;
            """)
            dow_rows = cur.fetchall()

            # Time-of-day split (last 28 days)
            cur.execute("""
                SELECT
                    SUM(CASE WHEN EXTRACT(HOUR FROM started_at) BETWEEN 5 AND 11 THEN 1 ELSE 0 END) AS morning,
                    SUM(CASE WHEN EXTRACT(HOUR FROM started_at) BETWEEN 12 AND 16 THEN 1 ELSE 0 END) AS afternoon,
                    SUM(CASE WHEN EXTRACT(HOUR FROM started_at) BETWEEN 17 AND 21 THEN 1 ELSE 0 END) AS evening,
                    SUM(CASE WHEN EXTRACT(HOUR FROM started_at) < 5
                               OR EXTRACT(HOUR FROM started_at) >= 22 THEN 1 ELSE 0 END) AS night,
                    COUNT(*) AS total
                FROM sessions
                WHERE ended_at IS NOT NULL
                  AND started_at >= CURRENT_TIMESTAMP - INTERVAL '28 days';
            """)
            tod_row = cur.fetchone()

            # Average session length (last 28 days, skip tiny sessions)
            cur.execute("""
                SELECT AVG(seconds_spent)::INT AS avg_seconds, COUNT(*) AS total
                FROM sessions
                WHERE ended_at IS NOT NULL
                  AND seconds_spent > 60
                  AND started_at >= CURRENT_TIMESTAMP - INTERVAL '28 days';
            """)
            avg_row = cur.fetchone()

            # Deep work days this week (days with >= 4h = 14400s of sessions)
            cur.execute("""
                SELECT COUNT(*) AS deep_days
                FROM (
                    SELECT DATE(started_at) AS d, SUM(seconds_spent) AS day_total
                    FROM sessions
                    WHERE ended_at IS NOT NULL
                      AND started_at >= date_trunc('week', NOW())
                    GROUP BY d
                    HAVING SUM(seconds_spent) >= 14400
                ) sub;
            """)
            deep_row = cur.fetchone()

            # Most worked todo of all time
            cur.execute("""
                SELECT t.title, SUM(s.seconds_spent) AS total_seconds
                FROM sessions s
                JOIN todos t ON t.id = s.todo_id
                WHERE s.ended_at IS NOT NULL AND s.todo_id IS NOT NULL AND s.seconds_spent > 0
                GROUP BY t.id, t.title
                ORDER BY total_seconds DESC
                LIMIT 1;
            """)
            top_todo_row = cur.fetchone()

            # All session dates for streak computation
            cur.execute("""
                SELECT DISTINCT DATE(started_at) AS d
                FROM sessions
                WHERE ended_at IS NOT NULL
                ORDER BY d ASC;
            """)
            all_date_rows = cur.fetchall()

    # Current streak (going back from today)
    today = date.today()
    all_dates = [r["d"] for r in all_date_rows]
    streak = 0
    for i, d in enumerate(reversed(all_dates)):
        if d == today - timedelta(days=i):
            streak += 1
        else:
            break

    # Best streak ever
    best_streak = cur_s = 0
    prev = None
    for d in all_dates:
        cur_s = cur_s + 1 if prev and (d - prev).days == 1 else 1
        if cur_s > best_streak:
            best_streak = cur_s
        prev = d

    dow_map = {r["dow"]: r for r in dow_rows}
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    by_dow = [
        {
            "dow": i,
            "day": day_names[i],
            "total_seconds": int(dow_map.get(i, {}).get("total_seconds") or 0),
            "session_count": int(dow_map.get(i, {}).get("session_count") or 0),
        }
        for i in range(7)
    ]

    tod_total = int(tod_row["total"] or 1)
    time_of_day = {
        "morning":   int(tod_row["morning"] or 0),
        "afternoon": int(tod_row["afternoon"] or 0),
        "evening":   int(tod_row["evening"] or 0),
        "night":     int(tod_row["night"] or 0),
        "total":     tod_total,
    }

    return {
        "this_week_seconds":    int(week_row["this_week"] or 0),
        "last_week_same_seconds": int(week_row["last_week_same"] or 0),
        "days_elapsed_in_week": int(week_row["days_elapsed"] or 1),
        "by_day_of_week":       by_dow,
        "time_of_day":          time_of_day,
        "current_streak_days":  streak,
        "best_streak_days":     best_streak,
        "avg_session_seconds":  int(avg_row["avg_seconds"] or 0) if avg_row else 0,
        "total_sessions_28d":   int(avg_row["total"] or 0) if avg_row else 0,
        "deep_work_days_this_week": int(deep_row["deep_days"] or 0) if deep_row else 0,
        "most_worked_todo": {
            "title": top_todo_row["title"],
            "total_seconds": int(top_todo_row["total_seconds"] or 0),
        } if top_todo_row else None,
    }


@router.get("/sessions/weekly-summary")
def get_weekly_summary():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    date_trunc('week', started_at) AS week_start,
                    SUM(COALESCE(seconds_spent, 0)) AS total_seconds,
                    COUNT(*) AS session_count
                FROM sessions
                WHERE ended_at IS NOT NULL
                  AND started_at >= NOW() - INTERVAL '56 days'
                GROUP BY week_start
                ORDER BY week_start ASC;
            """)
            rows = cur.fetchall()

    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())

    row_map = {}
    for r in rows:
        ws = r["week_start"]
        if hasattr(ws, 'date'):
            ws = ws.date()
        row_map[ws] = r

    result = []
    for i in range(7, -1, -1):
        ws = this_week_start - timedelta(weeks=i)
        r = row_map.get(ws, {})
        result.append({
            "week_start": str(ws),
            "total_seconds": int(r.get("total_seconds") or 0),
            "session_count": int(r.get("session_count") or 0),
            "is_current": ws == this_week_start,
        })

    return {"weeks": result}


@router.get("/sessions/active")
def get_active_session():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.*, COALESCE(s.title, t.title) AS todo_title
                FROM sessions s
                LEFT JOIN todos t ON t.id = s.todo_id
                WHERE s.ended_at IS NULL
                LIMIT 1;
                """
            )
            row = cur.fetchone()
    return row  # None → null in JSON if no active session


# get all sessions for a todo (index was created for this purpose)
@router.get("/todos/{todo_id}/sessions")
def get_sessions(todo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Check todo exists first
            cur.execute("SELECT id FROM todos WHERE id = %s;", (todo_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Todo not found")

            cur.execute(
                "SELECT * FROM sessions WHERE todo_id = %s ORDER BY started_at DESC;",
                (todo_id,)
            )
            rows = cur.fetchall()
    return {"sessions": rows}


# start a new session for a todo
@router.post("/todos/{todo_id}/sessions/start", status_code=201)
def start_session(todo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Check todo exists and fetch its title
            cur.execute("SELECT id, title FROM todos WHERE id = %s;", (todo_id,))
            todo = cur.fetchone()
            if not todo:
                raise HTTPException(status_code=404, detail="Todo not found")

            # Guard: block if there's already any open session globally
            cur.execute("SELECT id FROM sessions WHERE ended_at IS NULL;")
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="A session is already in progress")

            cur.execute(
                "INSERT INTO sessions (todo_id, title) VALUES (%s, %s) RETURNING *;",
                (todo_id, todo["title"])
            )
            row = cur.fetchone()
    return row


# start a freeform session (no todo linked)
@router.post("/sessions/start", status_code=201)
def start_freeform_session(body: StartFreeformSession):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Guard: block if there's already any open session globally
            cur.execute("SELECT id FROM sessions WHERE ended_at IS NULL;")
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="A session is already in progress")

            cur.execute(
                "INSERT INTO sessions (title, notes) VALUES (%s, %s) RETURNING *;",
                (body.title, body.notes)
            )
            row = cur.fetchone()
    return row


# end a session
@router.patch("/sessions/{session_id}/end")
def end_session(session_id: int, body: EndSession):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Fetch the session first to get started_at
            cur.execute("SELECT * FROM sessions WHERE id = %s;", (session_id,))
            session = cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            if session["ended_at"] is not None:
                raise HTTPException(status_code=409, detail="Session already ended")

            cur.execute(
                """
                UPDATE sessions
                SET ended_at = NOW(),
                    seconds_spent = EXTRACT(EPOCH FROM (NOW() - started_at))::INT,
                    notes = %s
                WHERE id = %s
                RETURNING *;
                """,
                (body.notes, session_id)
            )
            row = cur.fetchone()
    return row


# delete a session
@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE id = %s RETURNING id;", (session_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Session not found")


# get sessions for a UTC timestamp range (frontend converts local day → UTC bounds)
@router.get("/sessions/today")
def get_today_sessions(start: str = Query(...), end: str = Query(...)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.*, COALESCE(s.title, t.title) AS todo_title
                FROM sessions s
                LEFT JOIN todos t ON t.id = s.todo_id
                WHERE s.started_at >= %s AND s.started_at < %s
                ORDER BY s.started_at ASC;
                """,
                (start, end)
            )
            rows = cur.fetchall()
    return {"sessions": rows}


# get sessions for a UTC timestamp range spanning a week
@router.get("/sessions/week")
def get_week_sessions(start: str = Query(...), end: str = Query(...)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.*, COALESCE(s.title, t.title) AS todo_title
                FROM sessions s
                LEFT JOIN todos t ON t.id = s.todo_id
                WHERE s.started_at >= %s AND s.started_at < %s
                ORDER BY s.started_at ASC;
                """,
                (start, end)
            )
            rows = cur.fetchall()
    return {"sessions": rows}

#for phone to hit

@router.post("/todos/quick-session")
def quick_session(body: QuickSession):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # check no active session
            cur.execute("SELECT id FROM sessions WHERE ended_at IS NULL LIMIT 1")
            if cur.fetchone():
                return {"status": "skipped", "message": "Session already active"}
            
            # try to find matching todo
            cur.execute(
                "SELECT id, title FROM todos WHERE title ILIKE %s AND status = 'pending' LIMIT 1",
                (f"%{body.project}%",)
            )
            todo = cur.fetchone()

            if todo:
                # linked session
                cur.execute(
                    "INSERT INTO sessions (todo_id, title) VALUES (%s, %s) RETURNING *",
                    (todo["id"], todo["title"])
                )
            else:
                # freeform fallback
                cur.execute(
                    "INSERT INTO sessions (title) VALUES (%s) RETURNING *",
                    (body.project,)
                )
            
            return cur.fetchone()

@router.patch("/sessions/{session_id}/notes")
def update_session_notes(session_id: int, body: EndSession):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET notes = %s WHERE id = %s RETURNING *;",
                (body.notes, session_id)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
    return row


@router.post("/sessions/quick-end")
def quick_end_session():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM sessions WHERE ended_at IS NULL LIMIT 1")
            session = cur.fetchone()
            if not session:
                return {"status": "skipped", "message": "No active session"}
            cur.execute(
                """UPDATE sessions SET ended_at = NOW(),
                   seconds_spent = EXTRACT(EPOCH FROM (NOW() - started_at))::INT
                   WHERE id = %s RETURNING *""",
                (session["id"],)
            )
            return cur.fetchone()