import json
from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal, List
from datetime import datetime
import os
from psycopg import connect
from psycopg.rows import dict_row
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_methods=["*"],
    allow_headers=["*"],
)
router = APIRouter(prefix="/api/v1")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://focusos:focusos@localhost:5432/focusos") #default to local database

def get_conn():
    return connect(DATABASE_URL, row_factory=dict_row)

#-----Health Checks-----
#health check
@app.get("/health")
def health():
    return {"ok": True}

#db check

@app.get("/db")
def db_check():
    # proves backend can connect + query
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS one;")
            row = cur.fetchone()
    return {"db": "connected", "result": row}

#-----Base Models-----

#Subtasks are a list of subtasks, each with an id, title, and status
class Subtask(BaseModel):
    id: int
    title: str
    status: Literal["pending", "done"] = "pending"  

#title is required, everyting else optional
class CreateTodo(BaseModel):
    title: str                                        
    description: Optional[str] = None
    subtasks: Optional[List[Subtask]] = []
    due_date: Optional[datetime] = None
#everything optional, only update what changes
class UpdateTodo(BaseModel):
    title: Optional[str] = None                     
    description: Optional[str] = None
    status: Optional[Literal["pending", "done"]] = None
    subtasks: Optional[List[Subtask]] = None
    due_date: Optional[datetime] = None


class EndSession(BaseModel):
    notes: Optional[str] = None


#-----Todos-----

# get all todos either all or by status filtered
@router.get("/todos")
def get_todos(status: Optional[Literal["pending", "done"]] = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT * FROM todos WHERE status = %s ORDER BY due_date ASC NULLS LAST;",
                    (status,)
                )
            else:
                cur.execute("SELECT * FROM todos ORDER BY due_date ASC NULLS LAST;")
            rows = cur.fetchall()
    return {"todos": rows}


# create a new todo 
@router.post("/todos", status_code=201)
def create_todo(todo: CreateTodo):
    subtasks_json = json.dumps([s.model_dump() for s in todo.subtasks])  # serialize list → JSON string so can be stored in database
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO todos (title, description, subtasks, due_date)
                VALUES (%s, %s, %s, %s)
                RETURNING *;
                """,
                (todo.title, todo.description, subtasks_json, todo.due_date)
            )
            row = cur.fetchone()
    return row


# update a todo
@router.patch("/todos/{todo_id}")
def update_todo(todo_id: int, updates: UpdateTodo):
    fields = updates.model_dump(exclude_none=True)  # drops any field that is None (SO ONLY UPDATES CHANGED FIELDS!!! very cool)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # subtasks needs JSON serialization if present
    if "subtasks" in fields:
        fields["subtasks"] = json.dumps([s.model_dump() for s in updates.subtasks])

    set_clause = ", ".join(f"{k} = %s" for k in fields)  # e.g. "title = %s, status = %s"
    values = list(fields.values()) + [todo_id]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE todos SET {set_clause} WHERE id = %s RETURNING *;",
                values
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Todo not found")
    return row


# delete a todo in case of error
@router.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM todos WHERE id = %s RETURNING id;", (todo_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Todo not found")
    return  # 204 = no content


# ─── Sessions ─────────────────────────────────────────────────────────────────

# get all sessions for a todo (indexed was created for this purpose)
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


app.include_router(router)