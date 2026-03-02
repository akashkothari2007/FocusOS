from fastapi import APIRouter, HTTPException
from db import get_conn
from models.session_models import EndSession

router = APIRouter(prefix="/api/v1")


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
            # Check todo exists
            cur.execute("SELECT id FROM todos WHERE id = %s;", (todo_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Todo not found")

            # Guard: block if there's already an open session for this todo
            cur.execute(
                "SELECT id FROM sessions WHERE todo_id = %s AND ended_at IS NULL;",
                (todo_id,)
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="A session is already in progress for this todo")

            cur.execute(
                "INSERT INTO sessions (todo_id) VALUES (%s) RETURNING *;",
                (todo_id,)
            )
            row = cur.fetchone()
    return row


# end a session for a todo
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
