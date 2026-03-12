from fastapi import APIRouter, HTTPException, Query
from db import get_conn
from models.session_models import EndSession, StartFreeformSession, QuickSession

router = APIRouter(prefix="/api/v1")


# Returns the one open session (ended_at IS NULL) if any, with its title
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